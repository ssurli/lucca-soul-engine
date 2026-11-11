// Punto 6: in nessuna delle sei schermate un errore del BFF (rete assente o
// risposta 500) mostra testo tecnico: "BFF", "http", "Exception".
// Unica eccezione voluta: il 422 testuale di POST /memory (motivo del rifiuto
// pensato per l'utente) resta il messaggio del server.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/models/emotional_profile.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/person_kind.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/screens/citizen_screen.dart';
import 'package:lucca_soul_app/screens/dashboard_screen.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/screens/onboarding_screen.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/util/interruttori_controller.dart';
import 'package:lucca_soul_app/widgets/adaptive_card.dart';
import 'package:lucca_soul_app/widgets/memory_contribution_sheet.dart';

/// Come si guasta il BFF finto.
enum Guasto { rete, errore500 }

BffClient _client(Guasto g) => BffClient(
      baseUrl: Uri.parse('http://test'),
      httpClient: MockClient((req) async {
        if (g == Guasto.rete) {
          throw http.ClientException('Connection refused', req.url);
        }
        // Corpo volutamente "tecnico": nulla di questo deve arrivare a schermo.
        return http.Response(
          jsonEncode({'detail': 'BFF Exception: neo4j+s://aura http://x non raggiungibile'}),
          500,
          headers: {'content-type': 'application/json; charset=utf-8'},
        );
      }),
    );

BffClient _clientMemoria422(Object detail) => BffClient(
      baseUrl: Uri.parse('http://test'),
      httpClient: MockClient((_) async => http.Response(
            jsonEncode({'detail': detail}),
            422,
            headers: {'content-type': 'application/json; charset=utf-8'},
          ),),
    );

EmotionalProfile _profilo() => const EmotionalProfile(
      curiosita: 0.5,
      contemplazione: 0.5,
      arte: 0.5,
      conBambini: false,
      tempoDisponibileMin: 240,
      lingue: ['it'],
    );

/// Tutto il testo visibile: Text/RichText, SelectableText, campi di testo,
/// tooltip (le SnackBar contengono Text e sono quindi comprese).
List<String> _testiAschermo(WidgetTester t) => [
      for (final w in t.widgetList<RichText>(find.byType(RichText))) w.text.toPlainText(),
      for (final w in t.widgetList<SelectableText>(find.byType(SelectableText)))
        w.data ?? w.textSpan?.toPlainText() ?? '',
      for (final w in t.widgetList<EditableText>(find.byType(EditableText))) w.controller.text,
      for (final w in t.widgetList<Tooltip>(find.byType(Tooltip)))
        w.message ?? w.richMessage?.toPlainText() ?? '',
      for (final w in t.widgetList<SnackBar>(find.byType(SnackBar)))
        if (w.content is Text) (w.content as Text).data ?? '',
    ];

/// [ammessi]: testi esatti che NON sono messaggi d'errore e contengono
/// legittimamente una parola vietata (solo il segnaposto "https://…" del
/// campo URL del media nel foglio dei ricordi).
void _nessunTestoTecnico(WidgetTester t, {Set<String> ammessi = const {}}) {
  for (final s in _testiAschermo(t).where((s) => !ammessi.contains(s))) {
    expect(s, isNot(contains('BFF')), reason: s);
    expect(s.toLowerCase(), isNot(contains('http')), reason: s);
    expect(s, isNot(contains('Exception')), reason: s);
  }
}

Future<void> _schermoGrande(WidgetTester t) async {
  t.view.physicalSize = const Size(800, 2000);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

Future<void> _compilaEInviaRicordo(WidgetTester t, BffClient client, AppStrings s) async {
  await t.pumpWidget(MaterialApp(
    home: Scaffold(
      body: SingleChildScrollView(
        child: MemoryContributionSheet(
          bffClient: client,
          contributorId: 'c',
          contributorKind: PersonKind.cittadino,
          riguarda: const ['mura-urbane'],
          strings: s,
        ),
      ),
    ),
  ),);
  await t.enterText(find.byType(TextField).first, 'un ricordo');
  await t.tap(find.byType(CheckboxListTile));
  await t.pumpAndSettle();
  await t.tap(find.text(s.memorySubmit));
  await t.pumpAndSettle();
}

void main() {
  final s = AppStrings.forLanguages(['it']);

  for (final g in Guasto.values) {
    final atteso = g == Guasto.rete ? s.noConnection : s.serviceUnavailable;
    final attesoAdatta = g == Guasto.rete ? s.adaptNoConnection : s.adaptServiceUnavailable;

    group('${g.name}:', () {
      testWidgets('composizione', (t) async {
        await t.pumpWidget(MaterialApp(
          home: ItineraryScreen(bffClient: _client(g), personId: 'p', profile: _profilo()),
        ),);
        await t.pumpAndSettle();
        expect(find.text(atteso), findsOneWidget);
        _nessunTestoTecnico(t);
      });

      testWidgets('onboarding', (t) async {
        await _schermoGrande(t);
        await t.pumpWidget(MaterialApp(home: OnboardingScreen(bffClient: _client(g), personId: 'p')));
        for (final d in kDomandeVisibili) {
          await t.tap(find.text(d.opzioni.first.label));
          await t.pumpAndSettle();
        }
        await t.tap(find.text('Scopri il mio itinerario'));
        await t.pumpAndSettle();
        expect(find.text(atteso), findsOneWidget);
        _nessunTestoTecnico(t);
      });

      testWidgets('card adattiva', (t) async {
        final originale = Itinerary(
          personId: 'p',
          generatedAt: DateTime.utc(2026, 1, 1),
          stops: [ItineraryStop(experienceId: 'a', arrivo: TimeHms.parse('09:00:00'), durataMin: 30, reason: 'm')],
        );
        final c = InterruttoriController(bffClient: _client(g), originale: originale, profilo: _profilo());
        addTearDown(c.dispose);
        await t.pumpWidget(MaterialApp(
          home: Scaffold(body: SingleChildScrollView(child: AdaptiveCard(controller: c, strings: s))),
        ),);
        await t.tap(find.text(s.signalRain));
        await t.pumpAndSettle();
        expect(find.text(attesoAdatta), findsOneWidget);
        _nessunTestoTecnico(t);
      });

      testWidgets('vista Cittadino', (t) async {
        await _schermoGrande(t);
        await t.pumpWidget(MaterialApp(home: CitizenScreen(bffClient: _client(g), personId: 'c')));
        await t.pumpAndSettle();
        expect(find.text(atteso), findsOneWidget);
        _nessunTestoTecnico(t);
      });

      testWidgets('dashboard', (t) async {
        await _schermoGrande(t);
        await t.pumpWidget(MaterialApp(home: DashboardScreen(bffClient: _client(g))));
        await t.pumpAndSettle();
        // Index e heatmap dei flussi falliscono entrambi.
        expect(find.text(atteso), findsNWidgets(2));
        expect(find.text(s.dashboardErrorIndex), findsOneWidget);
        expect(find.text(s.dashboardErrorFlows), findsOneWidget);
        _nessunTestoTecnico(t);
      });

      testWidgets('foglio dei ricordi', (t) async {
        await _schermoGrande(t);
        await _compilaEInviaRicordo(t, _client(g), s);
        expect(find.text(s.memorySubmitError), findsOneWidget);
        expect(find.text(atteso), findsOneWidget);
        _nessunTestoTecnico(t, ammessi: {s.memoryMediaHint});
      });
    });
  }

  group('foglio dei ricordi, 422:', () {
    testWidgets('il motivo del rifiuto scritto dal server resta a schermo', (t) async {
      await _schermoGrande(t);
      const motivo = 'conferimento rifiutato: serve il consenso esplicito';
      await _compilaEInviaRicordo(t, _clientMemoria422(motivo), s);
      expect(find.text(motivo), findsOneWidget);
      expect(find.text(s.serviceUnavailable), findsNothing);
    });

    testWidgets('la lista di validazione di FastAPI non arriva a schermo', (t) async {
      await _schermoGrande(t);
      await _compilaEInviaRicordo(
        t,
        _clientMemoria422([
          {'type': 'missing', 'loc': ['body', 'licenza'], 'msg': 'Field required'},
        ]),
        s,
      );
      expect(find.text(s.serviceUnavailable), findsOneWidget);
      _nessunTestoTecnico(t, ammessi: {s.memoryMediaHint});
      for (final testo in _testiAschermo(t)) {
        expect(testo, isNot(contains('Field required')));
      }
    });
  });
}
