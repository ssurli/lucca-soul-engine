"""Spiegabilità: composizione del `reason` in italiano.

`reason` è obbligatorio ovunque compaia una raccomandazione (vedi
`docs/DATA_CONTRACTS.md`): questo modulo lo compone leggendo il profilo, un
candidato del grafo (`GraphCandidate`, che PROPONE connessioni ma non
decide) e gli eventuali segnali dell'Experience Engine. La scelta delle
tappe resta sempre dell'AI Experience Engine: qui si scrive solo il perché,
mai il cosa.

Il percorso principale è deterministico e non richiede alcun LLM.
`enrich_with_llm` è un arricchimento opzionale, dietro `ANTHROPIC_API_KEY`,
che degrada silenziosamente quando la chiave o il pacchetto `anthropic` non
ci sono: non è mai richiesto dai test.
"""

from __future__ import annotations

from contracts import EmotionalProfile, GraphCandidate

__all__ = ["compose_reason", "adapt_reason", "enrich_with_llm"]


_FRASI_SEGNALE: dict[str, str] = {
    "pioggia": "con la pioggia si sta al chiuso",
    "sereno": "con il cielo sereno conviene stare all'aperto",
    "caldo": "con questo caldo un luogo fresco si apprezza di più",
    "freddo": "con il freddo un luogo al chiuso è più comodo",
    "affollamento": "in questo momento è meno affollato",
    "stanchezza": "è una tappa più breve, per non stancarti troppo",
}


def _normalizza_chiave(s: str) -> str:
    return s.strip().lower()


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _lower_first(s: str) -> str:
    return s[:1].lower() + s[1:] if s else s


def _pulisci(s: str) -> str:
    return s.strip().rstrip(".;,")


def _e_o_ed(testo_seguente: str) -> str:
    """Restituisce "ed" (d eufonica) se `testo_seguente` inizia per e/è,
    altrimenti "e". Applicata in modo conservativo: solo davanti a e/è (es.
    "ed è legato"), non davanti alle altre vocali (es. "e ami", "e hai
    voglia" restano con "e")."""
    t = testo_seguente.lstrip()
    if not t:
        return "e"
    primo = t[0].lower()
    if primo in ("e", "è", "é"):
        return "ed"
    return "e"


def _frase_segnale(segnale: str) -> str | None:
    if not segnale:
        return None
    chiave = _normalizza_chiave(segnale)
    if chiave in _FRASI_SEGNALE:
        return _FRASI_SEGNALE[chiave]
    # Il chiamante può già passare una frase leggibile (es. "affollamento
    # sulle Mura"): la usiamo così com'è invece di scartarla.
    return segnale.strip()


def _tratto_dominante(profile: EmotionalProfile) -> str | None:
    """Sceglie il tratto del profilo più marcato, per intrecciarlo nel
    `reason`. I flag booleani (bambini, accessibilità) hanno priorità perché
    sono vincoli espliciti, non sfumature; tra i tratti 0..1 vince quello più
    lontano dal valore neutro (0.5). Un profilo troppo neutro non forza un
    tratto inventato: ritorna `None`."""
    if profile.con_bambini:
        return "è pensata anche per chi viaggia con bambini"
    if profile.accessibilita_richiesta:
        return "rispetta il bisogno di un percorso accessibile"

    candidati: list[tuple[float, str]] = [
        (
            abs(profile.contemplazione - 0.5),
            "cerchi silenzio e raccoglimento"
            if profile.contemplazione >= 0.5
            else "ami i luoghi vivi, con musica e movimento",
        ),
        (
            abs(profile.arte - 0.5),
            "ti lasci conquistare dalla bellezza"
            if profile.arte >= 0.5
            else "preferisci le storie che un luogo racconta",
        ),
        (
            abs(profile.curiosita - 0.5),
            "hai voglia di perderti e lasciarti sorprendere"
            if profile.curiosita >= 0.5
            else "preferisci un percorso chiaro, senza troppe sorprese",
        ),
    ]
    candidati.sort(key=lambda c: c[0], reverse=True)
    punteggio, frase = candidati[0]
    if punteggio < 0.1:
        return None
    return frase


def compose_reason(
    candidate: GraphCandidate,
    profile: EmotionalProfile,
    segnali: list[str] | None = None,
) -> str:
    """Compone un `reason` in italiano (1-2 frasi) intrecciando:
    (a) una connessione dal grafo (`candidate.connessioni`, se presente),
    (b) il tratto del profilo che l'ha resa pertinente,
    (c) l'eventuale segnale attivo (meteo, affollamento, stanchezza).

    Compone solo le parti disponibili: niente placeholder vuoti, niente
    template robotici. Se nessuna parte è disponibile, ricade su una frase
    minima ma comunque leggibile e vera (titolo + luogo)."""
    parti: list[str] = []

    if candidate.connessioni:
        connessione = _pulisci(candidate.connessioni[0])
        if connessione:
            parti.append(connessione)

    tratto = _tratto_dominante(profile)
    if tratto:
        parti.append(tratto)

    if segnali:
        frase_segnale = _frase_segnale(segnali[0])
        if frase_segnale:
            parti.append(_pulisci(frase_segnale))

    if not parti:
        return (
            f"{candidate.experience.titolo} è una tappa adatta al tuo percorso "
            f"a {candidate.place_nome}."
        )

    if len(parti) == 1:
        testo = parti[0]
    elif len(parti) == 2:
        congiunzione = _e_o_ed(parti[1])
        testo = f"{parti[0]}, {congiunzione} {_lower_first(parti[1])}"
    else:
        congiunzione = _e_o_ed(parti[1])
        testo = (
            f"{parti[0]}, {congiunzione} {_lower_first(parti[1])}; "
            f"inoltre, {_lower_first(parti[2])}"
        )

    testo = _cap(testo)
    if not testo.endswith("."):
        testo += "."
    return testo


def adapt_reason(motivo: str, segnale: str) -> str:
    """Riscrive un `reason` per una tappa sostituita dall'Experience Engine
    in risposta a un segnale (pioggia, affollamento, stanchezza...).

    Esempio: `adapt_reason("qui si respira la tradizione liutaia",
    "l'affollamento sulle Mura")` ->
    "Sostituita per l'affollamento sulle Mura: qui si respira la tradizione liutaia."
    """
    segnale_pulito = segnale.strip()
    motivo_pulito = _pulisci(motivo)
    prefisso = f"Sostituita per {segnale_pulito}" if segnale_pulito else "Sostituita"
    if motivo_pulito:
        return f"{prefisso}: {_lower_first(motivo_pulito)}."
    return f"{prefisso}."


def enrich_with_llm(
    motivo: str,
    profile: EmotionalProfile,
    *,
    model: str = "claude-3-5-haiku-latest",
) -> str:
    """Arricchimento OPZIONALE di un `reason` già valido, in tono più
    narrativo, tramite LLM. Il modello è una commodity intercambiabile: qui
    dialoga soltanto, non decide nulla (la frase di partenza `motivo` è già
    valida e non viene mai sostituita da fatti inventati).

    Attivo SOLO se `ANTHROPIC_API_KEY` è impostata e il pacchetto opzionale
    `anthropic` è installato. In ogni altro caso — chiave assente, pacchetto
    assente, errore di rete, risposta vuota — degrada silenziosamente
    ritornando `motivo` invariato. Non solleva mai un'eccezione e non è mai
    richiesto dal percorso di test principale."""
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return motivo

    try:
        import anthropic
    except ImportError:
        return motivo

    try:
        client = anthropic.Anthropic(api_key=api_key)
        lingua = profile.lingue[0] if profile.lingue else "it"
        risposta = client.messages.create(
            model=model,
            max_tokens=120,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Riscrivi in lingua '{lingua}', in modo naturale, conciso "
                        "(massimo 2 frasi) e senza inventare fatti nuovi, questo "
                        f"motivo di raccomandazione turistica: {motivo}"
                    ),
                }
            ],
        )
        blocco = risposta.content[0] if risposta.content else None
        testo = getattr(blocco, "text", "").strip() if blocco else ""
        return testo or motivo
    except Exception:
        return motivo
