import '../models/itinerary.dart';

/// Confronta due liste di tappe e restituisce gli indici (nella lista
/// `dopo`) che sono cambiati rispetto a `prima` — è così che la card
/// adattiva sa quali tappe evidenziare dopo una riscrittura da segnale.
///
/// Logica pura, senza Flutter: testabile a riga di comando anche senza SDK.
Set<int> tappeCambiate({required List<ItineraryStop> prima, required List<ItineraryStop> dopo}) {
  final cambiate = <int>{};
  for (var i = 0; i < dopo.length; i++) {
    if (i >= prima.length) {
      cambiate.add(i);
      continue;
    }
    final a = prima[i];
    final b = dopo[i];
    if (a.experienceId != b.experienceId || a.arrivo != b.arrivo || a.reason != b.reason) {
      cambiate.add(i);
    }
  }
  return cambiate;
}
