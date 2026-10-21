"""Frasi delle `connessioni` — UN SOLO punto di costruzione e di ordinamento.

Condiviso da `SeedCandidateSource` e `Neo4jCandidateSource` (come
`graph.attribuzione` per l'attribuzione): le due sorgenti non possono divergere
né nel testo né nell'ordine. Il `reason` usa `connessioni[0]`, quindi un ordine
non deterministico farebbe cambiare la spiegazione senza che cambino i dati.

L'ordine canonico lo impone QUESTO modulo, non la query:
  a) artisti legati al luogo, per nome (casefold);
  b) temi dell'esperienza, nell'ordine di `ExperienceNode.temi`;
  c) racconti `ISPIRATA_DA`, per id dell'artista;
  d) temi della bottega non già evocati dall'esperienza, per id del tema;
  e) per ultima, la prossimità al luogo già visitato (se applicabile).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence


def frasi_connessioni(
    *,
    luogo_nome: str,
    artisti_nomi: Iterable[str],
    temi_esperienza: Sequence[str],
    nomi_temi: Mapping[str, str],
    racconti_ispirazione: Iterable[tuple[str, str]],
    temi_bottega: Iterable[tuple[str, str]],
    riferimento: tuple[int, str] | None,
) -> list[str]:
    """`temi_esperienza`: id dei temi nell'ordine dell'esperienza; `nomi_temi`:
    id -> nome (un id senza nome viene saltato). `racconti_ispirazione`:
    (id artista, racconto). `temi_bottega`: (id tema, nome). `riferimento`:
    (metri, nome del luogo già visitato) solo se il luogo è VICINO ad esso e
    non coincide con esso; la decisione spetta a chi chiama."""
    frasi: list[str] = []

    for nome in sorted(set(artisti_nomi), key=lambda n: (n.casefold(), n)):
        frasi.append(f"{nome} è legato a {luogo_nome}.")

    for tema_id in temi_esperienza:
        nome_tema = nomi_temi.get(tema_id)
        if nome_tema is not None:
            frasi.append(f'Evoca il tema "{nome_tema}".')

    for _artista_id, racconto in sorted(set(racconti_ispirazione)):
        frasi.append(racconto)

    gia_evocati = set(temi_esperienza)
    for tema_id, nome_tema in sorted(set(temi_bottega)):
        if tema_id not in gia_evocati:
            frasi.append(f'La bottega evoca anche il tema "{nome_tema}".')

    if riferimento is not None:
        metri, nome_riferimento = riferimento
        frasi.append(f"A {metri} m da {nome_riferimento}, già visitato.")

    return frasi


# ---------------------------------------------------------------------------
# Campi di SOLO TESTO per il motivo (`GraphCandidate.racconti`,
# `temi_etichette`). Stesso principio di `frasi_connessioni`: un solo punto
# di costruzione e di ordinamento per le due sorgenti. NON toccano
# `connessioni` (che alimenta lo score): il motivo non la legge più.
# ---------------------------------------------------------------------------


def etichette_temi(temi_esperienza: Sequence[str], etichette: Mapping[str, str]) -> list[str]:
    """Etichette leggibili dei temi, nell'ordine di `ExperienceNode.temi`
    (un id senza etichetta viene saltato, come in `frasi_connessioni`)."""
    return [etichette[t] for t in temi_esperienza if etichette.get(t)]


def racconti_con_fonte(
    *,
    legati: Iterable[tuple[str, str | None, str | None]],
    temi_esperienza: Sequence[str],
    frasi_temi: Mapping[str, tuple[str | None, str | None]],
) -> list[str]:
    """Racconti CON FONTE pertinenti a un'esperienza: prima quelli dei
    `LEGATO_A` del suo luogo (`legati`: (nome artista, racconto, fonte), ordine
    nome casefold), poi le frasi dei suoi temi (`frasi_temi`: id ->
    (frase, fonte), ordine di `ExperienceNode.temi`). Un testo senza fonte non
    entra mai: la fonte è la condizione, non un'etichetta facoltativa."""
    risultato: list[str] = []
    con_fonte = {
        (nome, racconto)
        for nome, racconto, fonte in legati
        if racconto and racconto.strip() and fonte and fonte.strip()
    }
    for _nome, racconto in sorted(con_fonte, key=lambda x: (x[0].casefold(), x[0], x[1])):
        if racconto not in risultato:
            risultato.append(racconto)
    for tema_id in temi_esperienza:
        frase, fonte = frasi_temi.get(tema_id, (None, None))
        if frase and frase.strip() and fonte and fonte.strip() and frase not in risultato:
            risultato.append(frase)
    return risultato
