/// Luoghi noti del seed di Lucca
/// (`services/graph/cypher/01_seed_lucca.cypher`, nodi `Luogo`).
///
/// Convenienza SOLO lato UI: il grafo (via BFF) resta l'unica fonte di
/// verità su Luogo/Bottega/Artista. Questa lista serve a precompilare il
/// selettore di luogo nella vista Cittadino e a mappare un'esperienza
/// dell'itinerario al luogo che "riguarda" quando si apre un conferimento a
/// Urban Memory da una tappa (l'itinerario, in Wave 1/2, espone solo
/// `experience_id`, non `place_id`).
const List<String> kKnownPlaceIds = [
  'mura-urbane',
  'piazza-anfiteatro',
  'torre-guinigi',
  'duomo-san-martino',
  'casa-puccini',
  'san-michele-in-foro',
  'orto-botanico',
  'teatro-del-giglio',
  'palazzo-pfanner',
  'san-frediano',
  'torre-delle-ore',
  'piazza-napoleone',
  'via-fillungo',
  'baluardo-san-paolino',
  'museo-nazionale-guinigi',
];

/// Nome leggibile di ogni luogo di [kKnownPlaceIds] (proprieta' `nome` del
/// seed). Mostrato nel menu della vista Cittadino; il valore resta l'id.
const Map<String, String> kKnownPlaceNames = {
  'mura-urbane': 'Mura di Lucca',
  'piazza-anfiteatro': "Piazza dell'Anfiteatro",
  'torre-guinigi': 'Torre Guinigi',
  'duomo-san-martino': 'Duomo di San Martino',
  'casa-puccini': 'Casa Natale di Giacomo Puccini',
  'san-michele-in-foro': 'Chiesa di San Michele in Foro',
  'orto-botanico': 'Orto Botanico di Lucca',
  'teatro-del-giglio': 'Teatro del Giglio',
  'palazzo-pfanner': 'Palazzo Pfanner',
  'san-frediano': 'Basilica di San Frediano',
  'torre-delle-ore': 'Torre delle Ore',
  'piazza-napoleone': 'Piazza Napoleone',
  'via-fillungo': 'Via Fillungo',
  'baluardo-san-paolino': 'Baluardo San Paolino',
  'museo-nazionale-guinigi': 'Museo Nazionale di Villa Guinigi',
};

/// Gli id di [kKnownPlaceIds] in ordine alfabetico di nome (senza distinguere
/// maiuscole), per il menu della vista Cittadino.
List<String> kKnownPlaceIdsPerNome() => [...kKnownPlaceIds]
  ..sort((a, b) => kKnownPlaceNames[a]!.toLowerCase().compareTo(kKnownPlaceNames[b]!.toLowerCase()));

/// Rispecchia (un sottoinsieme delle) relazioni `SI_SVOLGE_A`
/// (Esperienza -> Luogo) del seed. Se un'esperienza non compare qui, non è
/// un errore: si userà il suo stesso `experience_id` come unico
/// riferimento in `riguarda` (vedi `riguardaPerEsperienza`).
const Map<String, String> kExperienceIdToPlaceId = {
  'exp-passeggiata-mura': 'mura-urbane',
  'exp-bici-mura': 'mura-urbane',
  'exp-mercato-anfiteatro': 'piazza-anfiteatro',
  'exp-salita-torre-guinigi': 'torre-guinigi',
  'exp-duomo-volto-santo': 'duomo-san-martino',
  'exp-casa-puccini-visita': 'casa-puccini',
  'exp-concerto-giglio': 'teatro-del-giglio',
  'exp-facciata-san-michele': 'san-michele-in-foro',
  'exp-orto-botanico-silenzio': 'orto-botanico',
  'exp-orto-botanico-bambini': 'orto-botanico',
  'exp-giardino-pfanner': 'palazzo-pfanner',
  'exp-mosaico-san-frediano': 'san-frediano',
  'exp-meccanismo-torre-ore': 'torre-delle-ore',
  'exp-piazza-napoleone': 'piazza-napoleone',
  'exp-struscio-fillungo': 'via-fillungo',
  'exp-tramonto-baluardo': 'baluardo-san-paolino',
  'exp-collezione-villa-guinigi': 'museo-nazionale-guinigi',
  'exp-laboratorio-liuteria': 'san-michele-in-foro',
  'exp-decorazione-ceramica': 'via-fillungo',
  'exp-torchio-stamperia': 'piazza-anfiteatro',
  'exp-buccellato-pasticceria': 'piazza-napoleone',
  'exp-telaio-tessitura': 'san-frediano',
};

/// Gli id (di Luogo/Bottega/Artista) che un conferimento aperto da una
/// tappa dell'itinerario "riguarda". Se l'esperienza non è nella mappa
/// nota, il fallback onesto è l'id dell'esperienza stessa: il BFF resta
/// comunque l'autorità su cosa quell'id rappresenti nel grafo.
List<String> riguardaPerEsperienza(String experienceId) {
  final placeId = kExperienceIdToPlaceId[experienceId];
  return [placeId ?? experienceId];
}
