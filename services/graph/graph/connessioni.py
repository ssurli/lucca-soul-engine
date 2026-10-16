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
