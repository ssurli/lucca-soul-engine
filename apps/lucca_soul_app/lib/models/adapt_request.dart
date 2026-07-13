import 'itinerary.dart';
import 'signal.dart';

/// Rispecchia `AdaptRequest` in `docs/DATA_CONTRACTS.md` §7.
/// Input di `POST /itinerary/adapt`: l'itinerario corrente più il nuovo
/// segnale (pioggia, affollamento, stanchezza) che ne motiva la riscrittura.
class AdaptRequest {
  final Itinerary itinerary;
  final Signal signal;

  const AdaptRequest({required this.itinerary, required this.signal});

  Map<String, dynamic> toJson() => {
        'itinerary': itinerary.toJson(),
        'signal': signal.toJson(),
      };
}
