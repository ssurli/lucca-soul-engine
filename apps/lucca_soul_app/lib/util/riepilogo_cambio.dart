import '../models/itinerary.dart';
import 'app_strings.dart';
import 'itinerary_diff.dart';

/// Fascia di riepilogo dopo un cambio, calcolata SOLO dagli esiti del motore:
/// `esito_adattamento` delle tappe (sostituita / mantenuta_senza_alternativa)
/// e `tappe_escluse` comparse rispetto all'itinerario originale.
/// Es. «Piove: 2 tappe cambiate, 1 senza alternativa adatta.»
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

String _hhmm(int minuti) {
  final m = minuti % (24 * 60);
  return '${(m ~/ 60).toString().padLeft(2, '0')}:${(m % 60).toString().padLeft(2, '0')}';
}

int _inizioMin(ItineraryStop s) => s.arrivo.hour * 60 + s.arrivo.minute;

/// Regola unica della "fine" della giornata, condivisa da
/// [fasciaOrariaGiornata] e [confrontoPrimaOra]: massimo di arrivo + durata,
/// in minuti, formattato HH:MM (minuti mod 24h). [tappe] non vuota.
String _fineGiornata(List<ItineraryStop> tappe) {
  final fine = tappe
      .map((s) => _inizioMin(s) + s.durataMin)
      .reduce((a, b) => a > b ? a : b);
  return _hhmm(fine);
}

/// Fascia oraria della giornata, es. "09:00–13:10": dall'arrivo della prima
/// tappa alla fine dell'ultima. Null senza tappe. Logica pura.
String? fasciaOrariaGiornata(List<ItineraryStop> tappe) {
  if (tappe.isEmpty) return null;
  final primo = tappe.map(_inizioMin).reduce((a, b) => a < b ? a : b);
  return '${_hhmm(primo)}–${_fineGiornata(tappe)}';
}

/// Confronto tra l'itinerario originale e quello mostrato dopo un adattamento,
/// in DUE righe: «Prima: 5 tappe, fine 12:50» e «Ora: 3 tappe, fine 11:34».
/// La "fine" usa la stessa regola di [fasciaOrariaGiornata]. Se l'originale
/// non ha tappe restituisce null (niente da confrontare); se è il mostrato a
/// non averne, la parte «Ora» dice «nessuna tappa» senza orario. Pura.
({String prima, String ora})? confrontoPrimaOra({
  required Itinerary originale,
  required Itinerary mostrato,
  required AppStrings strings,
}) {
  if (originale.stops.isEmpty) return null;
  String parte(List<ItineraryStop> tappe) => tappe.isEmpty
      ? strings.noStopsShort
      : strings.stopsAndEnd(tappe.length, _fineGiornata(tappe));
  return (
    prima: strings.beforeLine(parte(originale.stops)),
    ora: strings.nowLine(parte(mostrato.stops)),
  );
}
