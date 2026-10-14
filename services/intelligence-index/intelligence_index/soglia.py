"""Gate di privacy k-anonimato — CLAUDE.md: "Privacy by design".

VINCOLO TRASVERSALE NON NEGOZIABILE (prescritto per questa wave): ogni
aggregazione dell'Urban Intelligence Index, a QUALUNQUE livello di dettaglio
(per luogo, per profilo, per fascia oraria, per l'intero periodo), deve
coinvolgere almeno `SOGLIA_MINIMA_PERSONE` `person_id` DISTINTI prima di
essere pubblicata. Sotto soglia: MAI un numero calcolato su meno di k
persone, anche se tecnicamente disponibile — è un bug bloccante di privacy,
non un dettaglio implementativo.

Questo modulo è l'UNICO punto in cui la soglia è definita e verificata:
`intelligence_index.indicatori` e `intelligence_index.index` chiamano
SEMPRE `richiedi_soglia`/`valore_se_soglia`, mai un controllo `len(...) >= N`
scritto localmente in una funzione indicatore — un vincolo di privacy
verificato in un solo punto è verificabile, ripetuto a mano in ogni funzione
non lo è (stesso principio di "decide un solo componente", CLAUDE.md).

Due modi d'uso, per due situazioni diverse:

- `richiedi_soglia` (solleva `DatiInsufficientiError`): usato dal calcolo
  dell'aggregato dell'INTERO periodo (`intelligence_index.index.
  calcola_index`). `UrbanIntelligenceIndex` (`packages/contracts`, contratto
  CONGELATO) ha campi `float`/`int` NON opzionali per la maggior parte degli
  indicatori: non esiste un modo di "pubblicare comunque, ma con un valore
  vuoto" dentro quel tipo. Sollevare un'eccezione di dominio esplicita, che
  il chiamante (BFF, in una wave successiva) può mappare in una risposta
  "dato insufficiente" (stesso pattern già in uso per gli altri errori di
  dominio del repo: `ConsentRequiredError`, `InvalidTargetsError`...), è
  l'unica alternativa onesta a fabbricare un numero.
- `valore_se_soglia` (ritorna `None`, non solleva): pensato per future
  aggregazioni a grana più fine (drill-down della dashboard: per luogo, per
  profilo, per fascia oraria — fuori dal perimetro di questa wave, che
  produce solo l'aggregato a 8 campi) dove "omettere la cella" è
  un'alternativa sensata a "interrompere l'intero calcolo".
"""

from __future__ import annotations

from collections.abc import Collection, Iterable

__all__ = [
    "SOGLIA_MINIMA_PERSONE",
    "DatiInsufficientiError",
    "persone_sufficienti",
    "richiedi_soglia",
    "valore_se_soglia",
]

#: Numero minimo di `person_id` DISTINTI che un'aggregazione deve coinvolgere
#: prima di essere pubblicata (CLAUDE.md — "Privacy by design"; vincolo
#: esplicito di questa wave). k=10 è il valore concordato col committente:
#: non è negoziabile a livello di singola funzione indicatore, solo qui.
SOGLIA_MINIMA_PERSONE: int = 10


def persone_sufficienti(
    person_ids: Iterable[str], soglia: int = SOGLIA_MINIMA_PERSONE
) -> bool:
    """`True` se l'insieme DISTINTO di `person_id` raggiunge `soglia`.

    Deduplica sempre (`set(...)`): un `person_id` che compare 1000 volte
    nella stessa aggregazione (es. mille eventi della stessa persona) conta
    UNA volta sola ai fini della soglia di privacy — è il numero di persone
    distinte coinvolte che conta, non il numero di eventi.
    """
    return len(set(person_ids)) >= soglia


class DatiInsufficientiError(Exception):
    """Un'aggregazione coinvolge meno di `soglia` `person_id` distinti.

    Sollevato da `richiedi_soglia`: è un errore di DOMINIO (violazione del
    vincolo di privacy k-anonimato), non un errore infrastrutturale — il
    chiamante può distinguerlo da un `psycopg.Error`/`RecommenderStorageError`
    e mapparlo in una risposta "dato insufficiente" esplicita, invece di un
    500 opaco (stesso principio delle altre eccezioni di dominio del repo,
    es. `urban_memory.ConsentRequiredError`).
    """

    def __init__(self, contesto: str, n_persone: int, soglia: int = SOGLIA_MINIMA_PERSONE) -> None:
        self.contesto = contesto
        self.n_persone = n_persone
        self.soglia = soglia
        super().__init__(
            f"dato insufficiente per {contesto!r}: {n_persone} persone distinte "
            f"coinvolte, soglia minima di aggregazione k={soglia} (privacy by "
            "design, CLAUDE.md) — questa cella non viene pubblicata."
        )


def richiedi_soglia(
    person_ids: Collection[str], contesto: str, soglia: int = SOGLIA_MINIMA_PERSONE
) -> None:
    """Solleva `DatiInsufficientiError` se `person_ids` non raggiunge `soglia`
    `person_id` distinti. `contesto` è una stringa leggibile (es. il nome
    dell'indicatore: `"attivazione_locale"`) che finisce nel messaggio
    d'errore, per capire SUBITO quale aggregazione ha fallito il gate senza
    dover riprodurre il calcolo."""
    ids = set(person_ids)
    if len(ids) < soglia:
        raise DatiInsufficientiError(contesto, len(ids), soglia)


def valore_se_soglia[T](
    person_ids: Collection[str], valore: T, *, soglia: int = SOGLIA_MINIMA_PERSONE
) -> T | None:
    """Ritorna `valore` se `person_ids` raggiunge `soglia`, altrimenti `None`
    ("dato insufficiente" esplicito, mai un valore fabbricato). A differenza
    di `richiedi_soglia`, NON interrompe il chiamante: adatto ad aggregazioni
    a grana fine dove una cella mancante non deve far fallire l'intero
    calcolo (vedi docstring di modulo)."""
    return valore if persone_sufficienti(person_ids, soglia) else None
