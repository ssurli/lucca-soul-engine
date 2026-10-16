"""Dataset "borgo-esempio": inventato per test, non una citta' reale, mai
caricato su Aura.

Serve a provare che il motore e' replicabile cambiando SOLO il contenuto
locale: ogni nome qui e' palesemente fittizio, nessuna persona, bottega o
partner e' reale. Gli id hanno prefisso `be-` e non collidono con quelli di
Lucca (verificato da `test_borgo_esempio.py`). Vive solo nei test: il
registro lo trova perche' la fixture lo registra in `sys.modules` come
`graph.seed_borgo_esempio`, mai come file in `services/graph/graph`.
"""

from __future__ import annotations

from contracts import ExperienceNode, Partner, VocabolarioTemi
from graph.dataset import (
    VICINO_EPOCA_PREDEFINITA,
    Artista,
    Bottega,
    DatasetCitta,
    Luogo,
    RelazioneBottegaEvoca,
    RelazioneHaAbbonamento,
    RelazioneIspirataDa,
    RelazioneLegatoA,
    RelazioneVicino,
    Tema,
)

SLUG = "borgo-esempio"

LUOGHI = [
    Luogo("be-piazza-pozzo", "Piazza del Pozzo Immaginario", "piazza"),
    Luogo("be-torre-venti", "Torre dei Venti Finti", "torre"),
    Luogo("be-museo-sassi", "Museo dei Sassi Parlanti Finti", "museo"),
    Luogo("be-giardino-nebbie", "Giardino delle Nebbie Inventate", "giardino"),
    Luogo("be-chiesa-campana", "Chiesa della Campana Muta di Prova", "chiesa"),
    Luogo("be-via-lanterne", "Via delle Lanterne Spente", "via"),
    Luogo("be-teatro-cartapesta", "Teatro di Cartapesta Esempio", "teatro"),
]

ARTISTI = [
    Artista("be-artista-uno", "Orsolo Finto di Prova"),
    Artista("be-artista-due", "Ginevra Inesistente"),
]

LEGATO_A = [
    RelazioneLegatoA("be-artista-uno", "be-museo-sassi"),
    RelazioneLegatoA("be-artista-due", "be-teatro-cartapesta"),
]

BOTTEGHE = [
    Bottega(
        "be-bottega-ceramica",
        "Bottega Esempio di Prova",
        "ceramica",
        "be-via-lanterne",
        fittizio=True,
    ),
    Bottega(
        "be-bottega-stampa",
        "Stamperia Esempio Inattiva",
        "stampa",
        "be-piazza-pozzo",
        fittizio=True,
    ),
]

TEMI = [
    Tema("be-quiete", "Quiete del borgo di prova"),
    Tema("be-giardini", "Orti e giardini di prova"),
    Tema("be-vedute", "Vedute dall'alto di prova"),
    Tema("be-pittura", "Pittura inventata"),
    Tema("be-musica", "Musica di cartapesta"),
    Tema("be-ceramica", "Ceramica di prova"),
    Tema("be-giochi", "Giochi per i piccoli di prova"),
    Tema("be-leggende", "Leggende del pozzo finto"),
    Tema("be-mercato", "Mercatino immaginario"),
]

BOTTEGA_EVOCA = [RelazioneBottegaEvoca("be-bottega-ceramica", "be-ceramica")]

BOTTEGA_ISPIRATA_DA = [
    RelazioneIspirataDa(
        "be-bottega-ceramica",
        "be-artista-uno",
        "Il lavoro di Orsolo Finto di Prova ispira questa bottega di prova.",
    )
]

PARTNERS = [
    Partner(id="be-partner-ceramica", nome="Partner Esempio Attivo", abbonamento_attivo=True),
    Partner(id="be-partner-stampa", nome="Partner Esempio Sospeso", abbonamento_attivo=False),
]

HA_ABBONAMENTO = [
    RelazioneHaAbbonamento("be-bottega-ceramica", "be-partner-ceramica"),
    RelazioneHaAbbonamento("be-bottega-stampa", "be-partner-stampa"),
]


def _exp(
    id_: str,
    titolo: str,
    place_id: str,
    temi: list[str],
    durata_min: int,
    *,
    al_chiuso: bool,
    accessibile: bool,
    partner_id: str | None = None,
    prezzo_eur: float | None = None,
) -> ExperienceNode:
    return ExperienceNode(
        id=id_,
        titolo=titolo,
        place_id=place_id,
        temi=temi,
        durata_min=durata_min,
        al_chiuso=al_chiuso,
        accessibile=accessibile,
        partner_id=partner_id,
        prezzo_eur=prezzo_eur,
    )


ESPERIENZE = [
    _exp("be-exp-giro-piazza", "Giro attorno al pozzo finto", "be-piazza-pozzo",
         ["be-mercato", "be-leggende"], 30, al_chiuso=False, accessibile=True),
    _exp("be-exp-salita-torre", "Salita alla Torre dei Venti Finti", "be-torre-venti",
         ["be-vedute", "be-giardini"], 40, al_chiuso=False, accessibile=False),
    _exp("be-exp-museo-sassi", "I sassi che parlano (per finta)", "be-museo-sassi",
         ["be-pittura", "be-leggende"], 45, al_chiuso=True, accessibile=True),
    _exp("be-exp-museo-piccoli", "Il museo dei sassi per i piccoli", "be-museo-sassi",
         ["be-giochi", "be-pittura"], 40, al_chiuso=True, accessibile=True),
    _exp("be-exp-orto-nebbie", "Un'ora tra le nebbie inventate", "be-giardino-nebbie",
         ["be-giardini", "be-quiete"], 45, al_chiuso=False, accessibile=True),
    _exp("be-exp-giochi-giardino", "Giochi nel giardino di prova", "be-giardino-nebbie",
         ["be-giochi", "be-giardini"], 35, al_chiuso=False, accessibile=True),
    _exp("be-exp-chiesa-quiete", "Quiete sotto la campana muta", "be-chiesa-campana",
         ["be-quiete", "be-musica"], 30, al_chiuso=True, accessibile=True),
    _exp("be-exp-cripta", "La cripta delle leggende di prova", "be-chiesa-campana",
         ["be-leggende", "be-quiete"], 25, al_chiuso=True, accessibile=False),
    _exp("be-exp-teatro", "Un'aria nel teatro di cartapesta", "be-teatro-cartapesta",
         ["be-musica", "be-pittura"], 60, al_chiuso=True, accessibile=True),
    _exp("be-exp-lanterne", "Le lanterne spente di sera", "be-via-lanterne",
         ["be-leggende", "be-mercato"], 30, al_chiuso=False, accessibile=False),
    # Partner con abbonamento ATTIVO: deve poter comparire.
    _exp("be-exp-lab-ceramica", "Laboratorio di ceramica di prova", "be-via-lanterne",
         ["be-ceramica", "be-giochi"], 50, al_chiuso=True, accessibile=True,
         partner_id="be-bottega-ceramica", prezzo_eur=12.0),
    # Partner con abbonamento NON attivo: non deve comparire MAI.
    _exp("be-exp-stampa-sospesa", "Stampa a mano di prova", "be-piazza-pozzo",
         ["be-pittura", "be-ceramica"], 40, al_chiuso=True, accessibile=True,
         partner_id="be-bottega-stampa", prezzo_eur=9.0),
]

VICINO = [
    RelazioneVicino("be-piazza-pozzo", "be-torre-venti", 200),
    RelazioneVicino("be-piazza-pozzo", "be-museo-sassi", 150),
    RelazioneVicino("be-piazza-pozzo", "be-via-lanterne", 120),
    RelazioneVicino("be-museo-sassi", "be-giardino-nebbie", 300),
    RelazioneVicino("be-giardino-nebbie", "be-chiesa-campana", 250),
    RelazioneVicino("be-chiesa-campana", "be-via-lanterne", 180),
    RelazioneVicino("be-via-lanterne", "be-teatro-cartapesta", 220),
    RelazioneVicino("be-torre-venti", "be-chiesa-campana", 400),
]

VOCABOLARIO = VocabolarioTemi(
    contemplativi=frozenset({"be-quiete", "be-vedute"}),
    arte=frozenset({"be-pittura", "be-musica"}),
    insoliti=frozenset({"be-leggende", "be-ceramica"}),
    verde=frozenset({"be-giardini", "be-vedute"}),
    bambini="be-giochi",
)

DATASET = DatasetCitta(
    nome=SLUG,
    luoghi=LUOGHI,
    artisti=ARTISTI,
    legato_a=LEGATO_A,
    botteghe=BOTTEGHE,
    temi=TEMI,
    bottega_evoca=BOTTEGA_EVOCA,
    bottega_ispirata_da=BOTTEGA_ISPIRATA_DA,
    partners=PARTNERS,
    ha_abbonamento=HA_ABBONAMENTO,
    esperienze=ESPERIENZE,
    vicino=VICINO,
    vicino_epoca=VICINO_EPOCA_PREDEFINITA,
    id_esempio_memoria="be-bottega-ceramica",
    vocabolario=VOCABOLARIO,
)
