import 'time_hms.dart';

/// Rispecchia `ItineraryStop` in `docs/DATA_CONTRACTS.md` §3.
/// `reason` è la spiegabilità obbligatoria: il prodotto, non una nota.
class ItineraryStop {
  final String experienceId;
  final TimeHms arrivo;
  final int durataMin;
  final String reason;

  const ItineraryStop({
    required this.experienceId,
    required this.arrivo,
    required this.durataMin,
    required this.reason,
  });

  factory ItineraryStop.fromJson(Map<String, dynamic> json) {
    return ItineraryStop(
      experienceId: json['experience_id'] as String,
      arrivo: TimeHms.parse(json['arrivo'] as String),
      durataMin: json['durata_min'] as int,
      reason: json['reason'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
        'experience_id': experienceId,
        'arrivo': arrivo.toJson(),
        'durata_min': durataMin,
        'reason': reason,
      };
}

/// Rispecchia `Itinerary` in `docs/DATA_CONTRACTS.md` §3.
/// Uscita di `POST /itinerary` e `POST /itinerary/adapt`.
class Itinerary {
  final String personId;
  final List<ItineraryStop> stops;
  final DateTime generatedAt;
  final bool adattatoDaSegnale;

  const Itinerary({
    required this.personId,
    required this.stops,
    required this.generatedAt,
    this.adattatoDaSegnale = false,
  });

  factory Itinerary.fromJson(Map<String, dynamic> json) {
    return Itinerary(
      personId: json['person_id'] as String,
      stops: (json['stops'] as List<dynamic>)
          .map((e) => ItineraryStop.fromJson(e as Map<String, dynamic>))
          .toList(),
      generatedAt: DateTime.parse(json['generated_at'] as String),
      adattatoDaSegnale: json['adattato_da_segnale'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
        'person_id': personId,
        'stops': stops.map((s) => s.toJson()).toList(),
        'generated_at': generatedAt.toIso8601String(),
        'adattato_da_segnale': adattatoDaSegnale,
      };
}
