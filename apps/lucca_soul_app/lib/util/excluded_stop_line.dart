import '../models/itinerary.dart';
import 'app_strings.dart';

/// Nome da mostrare per una tappa: il `titolo` del catalogo, oppure
/// un'etichetta generica. L'identificativo (`experienceId`) non e' mai
/// mostrato all'utente.
String titoloTappa(String? titolo, AppStrings strings) {
  final t = titolo?.trim();
  return (t == null || t.isEmpty) ? strings.genericStop : t;
}

/// Riga di una tappa esclusa: titolo (o etichetta generica) davanti al `reason`.
///
/// Logica pura, senza Flutter.
String rigaTappaEsclusa(TappaEsclusa tappa, AppStrings strings) =>
    '${titoloTappa(tappa.titolo, strings)}: ${tappa.reason}';
