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

/// `--dart-define=DEMO=true` abilita `?istante=` nell'indirizzo.
const bool _demoDefine = bool.fromEnvironment('DEMO');

final RegExp _istanteIndirizzo =
    RegExp(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?Z$');

/// Sceglie l'istante all'apertura. Funzione pura. Precedenza:
/// parametro `istante` dell'indirizzo (solo se `demo`) > `define`
/// (DEMO_ISTANTE) > `null` (orologio del dispositivo).
///
/// Nell'indirizzo e' ammessa SOLO la forma con `Z`: un `+01:00` diventerebbe
/// uno spazio. Valore non valido: `FormatException` (mai un default muto).
/// Senza `demo` il parametro e' ignorato.
DateTime? risolviIstanteDemo({
  required bool demo,
  required Map<String, String> query,
  required String define,
}) {
  if (demo && query.containsKey('istante')) {
    final raw = query['istante']!.trim();
    final parsed = DateTime.tryParse(raw);
    if (!_istanteIndirizzo.hasMatch(raw) || parsed == null) {
      throw FormatException(
        '?istante non valido: "${query['istante']}". Atteso ISO 8601 UTC '
        'con Z, es. 2026-12-12T14:00:00Z',
      );
    }
    return parsed.toUtc();
  }
  if (define.trim().isNotEmpty) return parseDemoIstante(define);
  return null;
}

class Orologio {
  Orologio._();

  static DateTime Function() _sorgente = DateTime.now;

  /// L'istante corrente (o quello di demo), sempre in UTC.
  static DateTime adesso() => _sorgente().toUtc();

  /// Da chiamare all'avvio. Se `demo` è vuoto usa l'orologio del dispositivo;
  /// se non è parsabile lancia `FormatException` (l'app lo mostra a schermo).
  ///
  /// `query` sono i parametri dell'indirizzo (in `main`: `Uri.base.queryParameters`);
  /// contano solo con `DEMO=true` (vedi [risolviIstanteDemo]).
  static void inizializza({
    String demo = _demoIstanteDefine,
    bool demoAttivo = _demoDefine,
    Map<String, String> query = const {},
  }) {
    final fisso =
        risolviIstanteDemo(demo: demoAttivo, query: query, define: demo);
    _sorgente = fisso == null ? DateTime.now : () => fisso;
  }

  /// Solo per i test: sostituisce la sorgente (null = orologio del device).
  static void impostaPerTest(DateTime Function()? sorgente) {
    _sorgente = sorgente ?? DateTime.now;
  }
}
