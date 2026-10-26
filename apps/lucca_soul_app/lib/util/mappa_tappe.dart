import 'package:latlong2/latlong.dart';

import '../models/itinerary.dart';

/// Un segnaposto della mappa: il numero è quello della card della tappa
/// (posizione 1-based nell'itinerario, NON nella sola lista dei punti).
class SegnapostoMappa {
  final int numero;
  final LatLng punto;
  const SegnapostoMappa(this.numero, this.punto);
}

/// Segnaposti per le sole tappe con `punto_arrivo` (il punto scelto dal
/// motore), con la STESSA numerazione delle card: se la tappa 3 non ha punto
/// restano 1, 2, 4. Le tappe senza punto (botteghe dimostrative, tappe in coda
/// fluttuanti) non compaiono. Logica pura.
List<SegnapostoMappa> segnapostiMappa(List<ItineraryStop> tappe) => [
      for (var i = 0; i < tappe.length; i++)
        if (tappe[i].puntoArrivo != null)
          SegnapostoMappa(i + 1, LatLng(tappe[i].puntoArrivo!.lat, tappe[i].puntoArrivo!.lon)),
    ];
