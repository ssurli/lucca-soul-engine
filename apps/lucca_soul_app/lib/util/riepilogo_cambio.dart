import '../models/itinerary.dart';
import 'app_strings.dart';
import 'itinerary_diff.dart';

/// Fascia di riepilogo dopo un cambio, calcolata SOLO dagli esiti del motore:
/// `esito_adattamento` delle tappe (sostituita / mantenuta_senza_alternativa)
/// e `tappe_escluse` comparse rispetto all'itinerario originale.
/// Es. «Piove: 2 tappe cambiate, 1 resta in programma.»
///
/// [segnali] sono le etichette degli interruttori accesi. Logica pura.
String riepilogoCambio({
  required List<String> segnali,
  required Itinerary adattato,
  required Itinerary originale,
  required AppStrings strings,
}) {
  final cambiate = adattato.stops.where(tappaSostituita).length;
  final mantenute = adattato.stops.where(tappaMantenutaSenzaAlternativa).length;
  final giaEscluse = originale.tappeEscluse.map((t) => t.experienceId).toSet();
  final tolte = adattato.tappeEscluse
      .where((t) => !giaEscluse.contains(t.experienceId))
      .length;
  final parti = [
    if (cambiate > 0) strings.changedStopsPart(cambiate),
    if (mantenute > 0) strings.keptStopsPart(mantenute),
    if (tolte > 0) strings.removedStopsPart(tolte),
  ];
  final corpo =
      parti.isEmpty ? strings.nothingChangedSummary : parti.join(', ');
  return '${segnali.join(', ')}: $corpo.';
}

/// Fascia oraria della giornata, es. "09:00–13:10": dall'arrivo della prima
/// tappa alla fine dell'ultima. Null senza tappe. Logica pura.
String? fasciaOrariaGiornata(List<ItineraryStop> tappe) {
  if (tappe.isEmpty) return null;
  String hhmm(int minuti) {
    final m = minuti % (24 * 60);
    return '${(m ~/ 60).toString().padLeft(2, '0')}:${(m % 60).toString().padLeft(2, '0')}';
  }

  int inizio(ItineraryStop s) => s.arrivo.hour * 60 + s.arrivo.minute;
  final primo = tappe.map(inizio).reduce((a, b) => a < b ? a : b);
  final fine =
      tappe.map((s) => inizio(s) + s.durataMin).reduce((a, b) => a > b ? a : b);
  return '${hhmm(primo)}–${hhmm(fine)}';
}
