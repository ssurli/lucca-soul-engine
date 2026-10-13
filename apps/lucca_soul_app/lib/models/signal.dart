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

  /// Data LOCALE della visita (solo anno-mese-giorno; ore ignorate). Va
  /// letta dallo stesso `DateTime.now()` di `ora`: vedi [Signal.orologio].
  final DateTime? data;

  const Signal({
    required this.meteo,
    required this.affollamento,
    required this.stanchezza,
    required this.ora,
    this.eventiAttivi = const [],
    this.data,
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
      data: json['data'] == null ? null : parseIsoDate(json['data'] as String),
    );
  }

  /// Ora e data locali da UNA SOLA lettura dell'orologio, così non possono
  /// discordare a mezzanotte. Passare `now` esplicito solo nei test.
  static ({TimeHms ora, DateTime data}) orologio([DateTime? now]) {
    final t = now ?? DateTime.now();
    return (
      ora: TimeHms(hour: t.hour, minute: t.minute, second: t.second),
      data: DateTime(t.year, t.month, t.day),
    );
  }

  /// "YYYY-MM-DD" con zero-padding, indipendente dalla locale.
  static String formatIsoDate(DateTime d) {
    final y = d.year.toString().padLeft(4, '0');
    final m = d.month.toString().padLeft(2, '0');
    final g = d.day.toString().padLeft(2, '0');
    return '$y-$m-$g';
  }

  static DateTime parseIsoDate(String value) {
    final m = RegExp(r'^(\d{4})-(\d{2})-(\d{2})').firstMatch(value.trim());
    if (m == null) throw FormatException('Data non valida: "$value"');
    return DateTime(int.parse(m[1]!), int.parse(m[2]!), int.parse(m[3]!));
  }

  Map<String, dynamic> toJson() => {
        'meteo': meteo.toJson(),
        'affollamento': affollamento,
        'stanchezza': stanchezza,
        'ora': ora.toJson(),
        'eventi_attivi': eventiAttivi,
        if (data != null) 'data': formatIsoDate(data!),
      };

  Signal copyWith({
    Meteo? meteo,
    Map<String, double>? affollamento,
    double? stanchezza,
    TimeHms? ora,
    List<String>? eventiAttivi,
    DateTime? data,
  }) {
    return Signal(
      meteo: meteo ?? this.meteo,
      affollamento: affollamento ?? this.affollamento,
      stanchezza: stanchezza ?? this.stanchezza,
      ora: ora ?? this.ora,
      eventiAttivi: eventiAttivi ?? this.eventiAttivi,
      data: data ?? this.data,
    );
  }
}
