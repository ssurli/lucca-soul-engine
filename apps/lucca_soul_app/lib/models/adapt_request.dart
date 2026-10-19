import 'emotional_profile.dart';
import 'itinerary.dart';
import 'signal.dart';

/// Rispecchia `AdaptRequest` in `docs/DATA_CONTRACTS.md` §7.
/// Input di `POST /itinerary/adapt`: l'itinerario corrente più il nuovo
/// segnale (pioggia, affollamento, stanchezza) che ne motiva la riscrittura.
class AdaptRequest {
  final Itinerary itinerary;
  final Signal signal;

  /// Profilo ottenuto dall'onboarding; opzionale (assente dal JSON se null).
  final EmotionalProfile? profile;

  const AdaptRequest({required this.itinerary, required this.signal, this.profile});

  Map<String, dynamic> toJson() => {
        'itinerary': itinerary.toJson(),
        'signal': signal.toJson(),
        if (profile != null) 'profile': profile!.toJson(),
      };
}
