import '../models/itinerary.dart';

/// Riga di una tappa esclusa: `experience_id` davanti al `reason`.
///
/// Le schede delle tappe mostrano lo slug `experienceId` come unico
/// identificativo (l'app non ha nomi leggibili); le note "Rimaste fuori oggi"
/// fanno lo stesso, così tappe tagliate per lo stesso motivo restano
/// distinguibili. Nessuna euristica sullo slug: è mostrato com'è.
///
/// Logica pura, senza Flutter.
String rigaTappaEsclusa(TappaEsclusa tappa) => '${tappa.experienceId}: ${tappa.reason}';
