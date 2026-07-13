import 'meteo.dart';
import 'time_hms.dart';

/// Rispecchia `Signal` in `docs/DATA_CONTRACTS.md` §1: lo stato del mondo,
/// ORA. Governa la riscrittura dell'itinerario (pioggia, affollamento,
/// stanchezza) — mai dati identificanti.
class Signal {
  final Meteo meteo;
  final Map<String, double> affollamento; // place_id -> 0..1
  final double stanchezza; // 0..1
  final TimeHms ora;
  final List<String> eventiAttivi;

  const Signal({
    required this.meteo,
    required this.affollamento,
    required this.stanchezza,
    required this.ora,
    this.eventiAttivi = const [],
  });

  factory Signal.fromJson(Map<String, dynamic> json) {
    return Signal(
      meteo: meteoFromJson(json['meteo'] as String),
      affollamento: (json['affollamento'] as Map<String, dynamic>).map(
        (key, value) => MapEntry(key, (value as num).toDouble()),
      ),
      stanchezza: (json['stanchezza'] as num).toDouble(),
      ora: TimeHms.parse(json['ora'] as String),
      eventiAttivi:
          (json['eventi_attivi'] as List<dynamic>?)?.map((e) => e as String).toList() ??
              const [],
    );
  }

  Map<String, dynamic> toJson() => {
        'meteo': meteo.toJson(),
        'affollamento': affollamento,
        'stanchezza': stanchezza,
        'ora': ora.toJson(),
        'eventi_attivi': eventiAttivi,
      };

  Signal copyWith({
    Meteo? meteo,
    Map<String, double>? affollamento,
    double? stanchezza,
    TimeHms? ora,
    List<String>? eventiAttivi,
  }) {
    return Signal(
      meteo: meteo ?? this.meteo,
      affollamento: affollamento ?? this.affollamento,
      stanchezza: stanchezza ?? this.stanchezza,
      ora: ora ?? this.ora,
      eventiAttivi: eventiAttivi ?? this.eventiAttivi,
    );
  }
}
