import '../models/itinerary.dart';

/// Minuti "liberi" tra la fine di [a] e l'arrivo di [b], da mostrare come
/// "circa N min a piedi". Solo tra due tappe consecutive che hanno ENTRAMBE
/// `puntoArrivo`; N = arrivo[b] - (arrivo[a] + durata[a]), dagli orari gia'
/// presenti nel modello (nessun calcolo di distanza). Se N <= 0 (anche per un
/// passaggio della mezzanotte) o manca un punto: null = nessuna riga.
int? minutiAPiedi(ItineraryStop a, ItineraryStop b) {
  if (a.puntoArrivo == null || b.puntoArrivo == null) return null;
  int minuti(ItineraryStop s) => s.arrivo.hour * 60 + s.arrivo.minute;
  final n = minuti(b) - (minuti(a) + a.durataMin);
  return n > 0 ? n : null;
}
