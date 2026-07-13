import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/adapt_request.dart';
import '../models/emotional_profile.dart';
import '../models/itinerary.dart';
import '../models/onboarding.dart';
import '../models/visitor_context.dart';
import 'bff_exception.dart';

/// URL di default del BFF locale. Sovrascrivibile a build/run time con
/// `--dart-define=BFF_URL=http://host:porta`.
const String kDefaultBffUrl = 'http://localhost:8000';

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
            Uri.parse(const String.fromEnvironment('BFF_URL', defaultValue: kDefaultBffUrl)),
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

  Future<Map<String, dynamic>> _post(String path, Map<String, dynamic> body) async {
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
        _extractErrorDetail(response.bodyBytes) ?? 'Il BFF ha risposto con un errore',
        statusCode: response.statusCode,
      );
    }

    final Object? decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is! Map<String, dynamic>) {
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
