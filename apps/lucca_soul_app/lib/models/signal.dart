import '../util/clock.dart';
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

  /// Istante assoluto (UTC) della lettura; il BFF ne ricava ora/data nel fuso
  /// della città. `ora`/`data` restano come fallback.
  final DateTime? istante;

  const Signal({
    required this.meteo,
    required this.affollamento,
    required this.stanchezza,
    required this.ora,
    this.eventiAttivi = const [],
    this.data,
    this.istante,
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
      istante: json['istante'] == null
          ? null
          : DateTime.parse(json['istante'] as String).toUtc(),
    );
  }

  /// Ora e data locali da UNA SOLA lettura dell'orologio, così non possono
  /// discordare a mezzanotte. Senza `now` usa [Orologio] (device o demo);
  /// `now` esplicito solo nei test. `ora`/`data` sono in ora locale del device.
  static ({TimeHms ora, DateTime data, DateTime istante}) orologio([DateTime? now]) {
    final assoluto = (now ?? Orologio.adesso()).toUtc();
    final t = assoluto.toLocal();
    return (
      istante: assoluto,
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
        if (istante != null) 'istante': istante!.toUtc().toIso8601String(),
      };

  Signal copyWith({
    Meteo? meteo,
    Map<String, double>? affollamento,
    double? stanchezza,
    TimeHms? ora,
    List<String>? eventiAttivi,
    DateTime? data,
    DateTime? istante,
  }) {
    return Signal(
      meteo: meteo ?? this.meteo,
      affollamento: affollamento ?? this.affollamento,
      stanchezza: stanchezza ?? this.stanchezza,
      ora: ora ?? this.ora,
      eventiAttivi: eventiAttivi ?? this.eventiAttivi,
      data: data ?? this.data,
      istante: istante ?? this.istante,
    );
  }
}
