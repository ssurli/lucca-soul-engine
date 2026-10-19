/// Unico orologio dell'app. Ora, data e `istante` del `Signal` escono tutti
/// da qui, quindi da una sola lettura.
///
/// Demo: `--dart-define=DEMO_ISTANTE=2026-12-12T09:00:00Z` sostituisce
/// l'orologio del dispositivo. Il valore è un dato di avvio: nessun istante,
/// fuso o città è scritto nel codice.
const String _demoIstanteDefine = String.fromEnvironment('DEMO_ISTANTE');

/// Interpreta un istante di demo. Deve essere ISO 8601 con `Z` o con offset
/// esplicito: senza, l'istante dipenderebbe dal fuso del dispositivo e la demo
/// sarebbe ambigua. Valore non valido: `FormatException` (mai un default muto).
DateTime parseDemoIstante(String raw) {
  final testo = raw.trim();
  final haFuso = RegExp(r'(Z|[+-]\d{2}(:?\d{2})?)$').hasMatch(testo);
  final parsed = DateTime.tryParse(testo);
  if (parsed == null || !haFuso) {
    throw FormatException(
      'DEMO_ISTANTE non valido: "$raw". Atteso ISO 8601 con fuso, '
      'es. 2026-12-12T09:00:00Z',
    );
  }
  return parsed.toUtc();
}

class Orologio {
  Orologio._();

  static DateTime Function() _sorgente = DateTime.now;

  /// L'istante corrente (o quello di demo), sempre in UTC.
  static DateTime adesso() => _sorgente().toUtc();

  /// Da chiamare all'avvio. Se `demo` è vuoto usa l'orologio del dispositivo;
  /// se non è parsabile lancia `FormatException` (l'app lo mostra a schermo).
  static void inizializza({String demo = _demoIstanteDefine}) {
    if (demo.trim().isEmpty) {
      _sorgente = DateTime.now;
      return;
    }
    final fisso = parseDemoIstante(demo);
    _sorgente = () => fisso;
  }

  /// Solo per i test: sostituisce la sorgente (null = orologio del device).
  static void impostaPerTest(DateTime Function()? sorgente) {
    _sorgente = sorgente ?? DateTime.now;
  }
}
