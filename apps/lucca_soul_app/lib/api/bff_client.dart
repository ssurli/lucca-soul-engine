import 'dart:convert';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;

import '../models/adapt_request.dart';
import '../models/dashboard_flows_response.dart';
import '../models/dashboard_index_response.dart';
import '../models/emotional_profile.dart';
import '../models/itinerary.dart';
import '../models/memory_contribution.dart';
import '../models/onboarding.dart';
import '../models/visitor_context.dart';
import '../util/periodo.dart';
import 'bff_exception.dart';

/// URL di default del BFF locale. Sovrascrivibile a build/run time con
/// `--dart-define=BFF_URL=http://host:porta`.
const String kDefaultBffUrl = 'http://localhost:8000';

/// Valore di `--dart-define=BFF_URL=...` (vuoto se non definito).
const String _bffUrlDefine = String.fromEnvironment('BFF_URL');

/// Sceglie l'indirizzo del BFF. Funzione pura.
///
/// - `define` non vuoto: vince (sviluppo, es. `flutter run -d chrome`).
/// - altrimenti, sul web: la STESSA origine da cui l'app e' servita
///   (schema, host e porta di `base`; i percorsi sono assoluti, `/itinerary`...).
/// - altrimenti: [kDefaultBffUrl].
Uri risolviBffUrl({
  required String define,
  required bool isWeb,
  required Uri base,
}) {
  final d = define.trim();
  if (d.isNotEmpty) return Uri.parse(d);
  if (isWeb) {
    return Uri(
      scheme: base.scheme,
      host: base.host,
      port: base.hasPort ? base.port : null,
      path: '/',
    );
  }
  return Uri.parse(kDefaultBffUrl);
}

/// Client verso il BFF (`services/api`).
///
/// L'app parla SOLO con il BFF: nessuna schermata o widget chiama Neo4j,
/// Postgres o un servizio interno direttamente. Questa classe è l'unico
/// punto di rete di tutta l'app.
class BffClient {
  final Uri baseUrl;
  final http.Client _http;

  BffClient({Uri? baseUrl, http.Client? httpClient})
      : baseUrl = baseUrl ??
            risolviBffUrl(define: _bffUrlDefine, isWeb: kIsWeb, base: Uri.base),
        _http = httpClient ?? http.Client();

  /// `POST /session/onboarding` — la conversazione produce un
  /// `EmotionalProfile`. Nessuna risposta viene salvata sul device oltre la
  /// sessione corrente.
  Future<EmotionalProfile> onboarding(OnboardingRequest request) async {
    final json = await _post('/session/onboarding', request.toJson());
    return EmotionalProfile.fromJson(json);
  }

  /// `POST /itinerary` — genera l'itinerario del giorno per il contesto
  /// dato (profilo + segnale corrente).
  Future<Itinerary> itinerary(VisitorContext context) async {
    final json = await _post('/itinerary', context.toJson());
    return Itinerary.fromJson(json);
  }

  /// `POST /itinerary/adapt` — riscrive l'itinerario a fronte di un nuovo
  /// segnale (pioggia, affollamento, stanchezza).
  Future<Itinerary> adaptItinerary(AdaptRequest request) async {
    final json = await _post('/itinerary/adapt', request.toJson());
    return Itinerary.fromJson(json);
  }

  /// `POST /memory` — conferisce un contributo alla Urban Memory. Il BFF
  /// rifiuta (4xx) un conferimento senza consenso esplicito o con licenza
  /// mancante: il messaggio (`detail`) del server arriva intatto nel
  /// `BffException`, così la UI mostra esattamente ciò che dice il BFF.
  Future<MemoryContribution> submitMemory(
    MemoryContribution contribution,
  ) async {
    final json = await _post('/memory', contribution.toJson());
    return MemoryContribution.fromJson(json);
  }

  /// `GET /memory/{place_id}` — solo i contributi già curati (revisionati)
  /// che riguardano un Luogo/Bottega/Artista del grafo.
  Future<List<MemoryContribution>> memoriesForPlace(String placeId) async {
    final list = await _getList('/memory/${Uri.encodeComponent(placeId)}');
    return list
        .map((e) => MemoryContribution.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// `GET /dashboard/index?periodo=YYYY-MM` — l'Urban Intelligence Index del
  /// periodo, o lo stato esplicito "dato insufficiente" (soglia k=10,
  /// `disponibile=false`). Risponde SEMPRE 200 lato BFF: qui non c'è alcuna
  /// eccezione di dominio da distinguere, solo l'eventuale `BffException` di
  /// rete/BFF (la terza fascia di stato, gestita dal chiamante).
  Future<DashboardIndexResponse> dashboardIndex(String periodo) async {
    final json = await _get('/dashboard/index', {'periodo': periodo});
    return DashboardIndexResponse.fromJson(json);
  }

  /// `GET /dashboard/flows?periodo=YYYY-MM&giorno=YYYY-MM-DD&ora=0..23` —
  /// heatmap dei flussi, una `FlowCell` per luogo. `giorno`/`ora` sono
  /// filtri opzionali sulla STESSA lista di celle, mai una dimensione
  /// combinatoria del payload.
  Future<DashboardFlowsResponse> dashboardFlows({
    required String periodo,
    DateTime? giorno,
    int? ora,
  }) async {
    final query = <String, String>{'periodo': periodo};
    if (giorno != null) query['giorno'] = formatDateYmd(giorno);
    if (ora != null) query['ora'] = ora.toString();
    final json = await _get('/dashboard/flows', query);
    return DashboardFlowsResponse.fromJson(json);
  }

  Future<Map<String, dynamic>> _get(
    String path,
    Map<String, String> queryParams,
  ) async {
    final uri = baseUrl.resolve(path).replace(queryParameters: queryParams);
    late final http.Response response;
    try {
      response = await _http.get(uri).timeout(const Duration(seconds: 20));
    } catch (error) {
      throw BffException('Impossibile contattare il BFF su $uri: $error');
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw BffException(
        _extractErrorDetail(response.bodyBytes) ??
            'Il BFF ha risposto con un errore',
        statusCode: response.statusCode,
      );
    }

    final Object? decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is! Map<String, dynamic>) {
      throw BffException('Risposta del BFF non nel formato atteso per $path');
    }
    return decoded;
  }

  Future<Map<String, dynamic>> _post(
    String path,
    Map<String, dynamic> body,
  ) async {
    final uri = baseUrl.resolve(path);
    late final http.Response response;
    try {
      response = await _http
          .post(
            uri,
            headers: const {'Content-Type': 'application/json; charset=utf-8'},
            body: jsonEncode(body),
          )
          .timeout(const Duration(seconds: 20));
    } catch (error) {
      throw BffException('Impossibile contattare il BFF su $uri: $error');
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw BffException(
        _extractErrorDetail(response.bodyBytes) ??
            'Il BFF ha risposto con un errore',
        statusCode: response.statusCode,
      );
    }

    final Object? decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is! Map<String, dynamic>) {
      throw BffException('Risposta del BFF non nel formato atteso per $path');
    }
    return decoded;
  }

  Future<List<dynamic>> _getList(String path) async {
    final uri = baseUrl.resolve(path);
    late final http.Response response;
    try {
      response = await _http.get(uri).timeout(const Duration(seconds: 20));
    } catch (error) {
      throw BffException('Impossibile contattare il BFF su $uri: $error');
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw BffException(
        _extractErrorDetail(response.bodyBytes) ??
            'Il BFF ha risposto con un errore',
        statusCode: response.statusCode,
      );
    }

    final Object? decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is! List<dynamic>) {
      throw BffException('Risposta del BFF non nel formato atteso per $path');
    }
    return decoded;
  }

  String? _extractErrorDetail(List<int> bodyBytes) {
    try {
      final Object? decoded = jsonDecode(utf8.decode(bodyBytes));
      if (decoded is Map<String, dynamic> && decoded['detail'] != null) {
        return decoded['detail'].toString();
      }
    } catch (_) {
      // Corpo non JSON: si usa il messaggio di default del chiamante.
    }
    return null;
  }

  /// Rilascia la connessione HTTP sottostante.
  void dispose() => _http.close();
}
