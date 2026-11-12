// Voce 4: un 200 con corpo non JSON (HTML di un proxy) o con JSON senza una
// chiave obbligatoria diventa una BffException non di rete, senza il corpo
// nel messaggio; le schermate la trattano come errore del servizio (testo +
// Riprova), mai come lista vuota o spinner, e senza eccezioni non gestite.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/api/bff_exception.dart';
import 'package:lucca_soul_app/models/adapt_request.dart';
import 'package:lucca_soul_app/models/emotional_profile.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/memory_contribution.dart';
import 'package:lucca_soul_app/models/memory_kind.dart';
import 'package:lucca_soul_app/models/meteo.dart';
import 'package:lucca_soul_app/models/onboarding.dart';
import 'package:lucca_soul_app/models/person_kind.dart';
import 'package:lucca_soul_app/models/signal.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/models/visitor_context.dart';
import 'package:lucca_soul_app/screens/citizen_screen.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/util/app_strings.dart';

const _html = '<html><body>SEGRETO-DEL-PROXY 502 bad gateway</body></html>';
const _jsonSenzaChiave = '{"campo_inatteso": "SEGRETO-NEL-JSON"}';
const _listaConElementoSenzaChiave = '[{"campo_inatteso": "SEGRETO-NEL-JSON"}]';
const _segreti = ['SEGRETO-DEL-PROXY', 'SEGRETO-NEL-JSON', 'bad gateway', '<html'];

const _msgNonDecodificabile = 'Risposta del BFF non decodificabile';
const _msgFormato = 'Risposta del BFF non nel formato atteso';

final _s = AppStrings.forLanguages(['it']);

BffClient _client(String corpo, {int stato = 200}) => BffClient(
      baseUrl: Uri.parse('http://test'),
      httpClient: MockClient((_) async => http.Response(
            corpo,
            stato,
            headers: {'content-type': 'application/json; charset=utf-8'},
          ),),
    );

const _profilo = EmotionalProfile(
  curiosita: 0.5,
  contemplazione: 0.5,
  arte: 0.5,
  conBambini: false,
  tempoDisponibileMin: 240,
  lingue: ['it'],
);

Signal _segnale() => const Signal(
      meteo: Meteo.sereno,
      affollamento: {},
      stanchezza: 0,
      ora: TimeHms(hour: 10, minute: 0),
    );

Itinerary _itinerario() => Itinerary(
      personId: 'p',
      generatedAt: DateTime.utc(2026, 12, 12, 9),
      stops: [
        ItineraryStop(
          experienceId: 'a',
          arrivo: TimeHms.parse('09:00:00'),
          durataMin: 30,
          reason: 'motivo',
        ),
      ],
    );

MemoryContribution _memoria() => MemoryContribution(
      id: 'memoria_1',
      kind: MemoryKind.racconto,
      testo: 'un ricordo',
      riguarda: const ['mura-urbane'],
      contributorId: 'c',
      contributorKind: PersonKind.cittadino,
      consenso: true,
      licenza: 'CC0-1.0',
      creatoIl: DateTime.utc(2026, 12, 12),
    );

/// Le sei chiamate del client, ciascuna con la sua richiesta valida.
final Map<String, Future<Object?> Function(BffClient)> _chiamate = {
  'itinerary': (c) => c.itinerary(
        VisitorContext(personId: 'p', profile: _profilo, signal: _segnale()),
      ),
  'adaptItinerary': (c) =>
      c.adaptItinerary(AdaptRequest(itinerary: _itinerario(), signal: _segnale())),
  'memoriesForPlace': (c) => c.memoriesForPlace('mura-urbane'),
  'dashboardIndex': (c) => c.dashboardIndex('2026-12'),
  'dashboardFlows': (c) => c.dashboardFlows(periodo: '2026-12'),
  'onboarding': (c) => c.onboarding(
        const OnboardingRequest(risposte: [
          OnboardingAnswer(domandaId: 'q1', risposta: 'si'),
        ],),
      ),
  'submitMemory': (c) => c.submitMemory(_memoria()),
};

/// Corpo "JSON valido ma senza una chiave obbligatoria", per chiamata.
String _jsonSbagliato(String chiamata) =>
    chiamata == 'memoriesForPlace' ? _listaConElementoSenzaChiave : _jsonSenzaChiave;

Future<void> _attesa(Future<Object?> f, String messaggio) async {
  BffException? presa;
  try {
    await f;
  } on BffException catch (e) {
    presa = e;
  }
  expect(presa, isNotNull, reason: 'attesa una BffException');
  final e = presa!;
  expect(e.message, messaggio);
  expect(e.connessioneAssente, isFalse, reason: 'non e un errore di rete');
  expect(e.statusCode, isNull);
  for (final segreto in _segreti) {
    expect(e.message, isNot(contains(segreto)));
    expect(e.toString(), isNot(contains(segreto)));
  }
}

Future<void> _schermoGrande(WidgetTester t) async {
  t.view.physicalSize = const Size(800, 2000);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

void _eccoErroreDelServizio(WidgetTester t, {required String vuoto}) {
  expect(find.text(_s.serviceUnavailable), findsOneWidget);
  expect(find.text(_s.noConnection), findsNothing);
  expect(find.widgetWithText(FilledButton, _s.retry), findsOneWidget);
  expect(find.byType(CircularProgressIndicator), findsNothing);
  expect(find.text(vuoto), findsNothing);
  expect(t.takeException(), isNull);
}

void main() {
  group('BffClient: corpo HTML in un 200', () {
    for (final e in _chiamate.entries) {
      test(e.key, () => _attesa(e.value(_client(_html)), _msgNonDecodificabile));
    }
  });

  group('BffClient: JSON senza una chiave obbligatoria in un 200', () {
    for (final e in _chiamate.entries) {
      test(e.key, () => _attesa(e.value(_client(_jsonSbagliato(e.key))), _msgFormato));
    }
  });

  group('BffClient: altre forme sbagliate', () {
    test('corpo vuoto in un 200 -> non decodificabile', () {
      return _attesa(_chiamate['itinerary']!(_client('')), _msgNonDecodificabile);
    });

    test('elemento della lista che non e un oggetto -> formato non atteso', () {
      return _attesa(_chiamate['memoriesForPlace']!(_client('[1, "x"]')), _msgFormato);
    });

    test('tipo sbagliato per un campo (stops stringa) -> formato non atteso', () {
      return _attesa(
        _chiamate['itinerary']!(_client('{"person_id": "p", "stops": "no", "generated_at": "2026-12-12T09:00:00Z"}')),
        _msgFormato,
      );
    });

    test('un 500 resta una BffException con statusCode (invariato)', () async {
      try {
        await _chiamate['itinerary']!(_client('{"detail": "boom"}', stato: 500));
        fail('attesa BffException');
      } on BffException catch (e) {
        expect(e.statusCode, 500);
      }
    });
  });

  group('ItineraryScreen', () {
    for (final caso in {'HTML': _html, 'JSON senza chiave': _jsonSenzaChiave}.entries) {
      testWidgets('200 con ${caso.key}: errore del servizio e Riprova', (t) async {
        await t.pumpWidget(MaterialApp(
          home: ItineraryScreen(bffClient: _client(caso.value), personId: 'p', profile: _profilo),
        ),);
        await t.pumpAndSettle();
        _eccoErroreDelServizio(t, vuoto: _s.emptyStops);
        expect(find.text(_s.emptyStops), findsNothing);
        expect(find.text('Ancora nessuna tappa.'), findsNothing);
      });
    }
  });

  group('CitizenScreen', () {
    for (final caso in {'HTML': _html, 'JSON senza chiave': _listaConElementoSenzaChiave}.entries) {
      testWidgets('200 con ${caso.key}: errore del servizio e Riprova', (t) async {
        await _schermoGrande(t);
        await t.pumpWidget(MaterialApp(home: CitizenScreen(bffClient: _client(caso.value), personId: 'c')));
        await t.pumpAndSettle();
        _eccoErroreDelServizio(t, vuoto: _s.citizenEmpty);
        expect(find.text('Ancora nessun ricordo curato per questo luogo.'), findsNothing);
      });
    }
  });
}
