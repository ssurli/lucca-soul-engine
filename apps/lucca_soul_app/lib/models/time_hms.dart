/// Un orario "HH:MM:SS", così come lo serializza Pydantic per i campi
/// `datetime.time` dei contratti (`Signal.ora`, `ItineraryStop.arrivo`).
///
/// Niente dipendenza da `TimeOfDay` di Flutter: quella classe non porta i
/// secondi ed è un widget-helper, non un tipo di dominio. Questo modello
/// resta puro e testabile senza il framework.
class TimeHms implements Comparable<TimeHms> {
  final int hour;
  final int minute;
  final int second;

  const TimeHms({required this.hour, required this.minute, this.second = 0});

  /// Interpreta una stringa "HH:MM:SS" o "HH:MM" (quest'ultima tollerata
  /// per input utente/di test; il BFF invia sempre "HH:MM:SS").
  factory TimeHms.parse(String value) {
    final parts = value.trim().split(':');
    if (parts.length < 2 || parts.length > 3) {
      throw FormatException('Orario non valido: "$value"');
    }
    final hour = int.parse(parts[0]);
    final minute = int.parse(parts[1]);
    final second = parts.length == 3 ? int.parse(parts[2]) : 0;
    if (hour < 0 || hour > 23 || minute < 0 || minute > 59 || second < 0 || second > 59) {
      throw FormatException('Orario fuori scala: "$value"');
    }
    return TimeHms(hour: hour, minute: minute, second: second);
  }

  factory TimeHms.now() {
    final now = DateTime.now();
    return TimeHms(hour: now.hour, minute: now.minute, second: now.second);
  }

  /// Rappresentazione canonica "HH:MM:SS" per il JSON verso il BFF.
  String toJson() {
    String two(int n) => n.toString().padLeft(2, '0');
    return '${two(hour)}:${two(minute)}:${two(second)}';
  }

  /// Rappresentazione breve "HH:MM" per la UI.
  String get label {
    String two(int n) => n.toString().padLeft(2, '0');
    return '${two(hour)}:${two(minute)}';
  }

  int get _totalSeconds => hour * 3600 + minute * 60 + second;

  @override
  int compareTo(TimeHms other) => _totalSeconds.compareTo(other._totalSeconds);

  @override
  bool operator ==(Object other) => other is TimeHms && other._totalSeconds == _totalSeconds;

  @override
  int get hashCode => _totalSeconds.hashCode;

  @override
  String toString() => toJson();
}
