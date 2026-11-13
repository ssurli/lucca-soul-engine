// Versione di prova: l'app non registra i percorsi (kAppRegistraEventi ==
// false), quindi la dashboard avvisa, una volta sola, che gli indicatori
// restano vuoti. Il fallback "indice non disponibile" non promette dati
// futuri (niente "ancora").
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/screens/dashboard_screen.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/util/registrazione_eventi.dart';

const _fraseIt =
    "In questa versione di prova l'app non registra i percorsi, quindi gli indicatori restano vuoti.";
const _fraseEn = 'This trial version does not record routes, so the indicators stay empty.';
const _chiave = Key('avviso-prova-senza-eventi');

BffClient _client({required bool disponibile}) => BffClient(
      baseUrl: Uri.parse('http://test'),
      httpClient: MockClient((req) async {
        final Object corpo;
        if (req.url.path == '/dashboard/index') {
          corpo = disponibile
              ? {
                  'periodo': '2026-07',
                  'disponibile': true,
                  'index': {
                    'periodo': '2026-07',
                    'tempo_medio_esperienza_min': 42.0,
                    'coinvolgimento': 0.68,
                    'soddisfazione': null,
                    'tasso_ritorno': 0.31,
                    'nuovi_percorsi': 0.5,
                    'attivazione_locale': 0.44,
                    'distribuzione_flussi': 0.72,
                    'contributi_memoria': 17,
                  },
                  'motivo_indisponibilita': null,
                }
              : {
                  'periodo': '2026-07',
                  'disponibile': false,
                  'index': null,
                  'motivo_indisponibilita': null,
                };
        } else {
          corpo = {'periodo': '2026-07', 'giorno': null, 'ora': null, 'celle': <Object>[]};
        }
        return http.Response(
          jsonEncode(corpo),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'},
        );
      }),
    );

Future<void> _monta(WidgetTester t, {required bool disponibile}) async {
  t.view.physicalSize = const Size(800, 2000);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(
    MaterialApp(home: DashboardScreen(bffClient: _client(disponibile: disponibile))),
  );
  await t.pumpAndSettle();
}

void main() {
  final it = AppStrings.forLanguages(['it']);
  final en = AppStrings.forLanguages(['en']);

  test('premessa: la versione di prova non registra eventi', () {
    expect(kAppRegistraEventi, isFalse);
  });

  test('le stringhe hanno il testo atteso', () {
    expect(it.dashboardProvaSenzaEventi, _fraseIt);
    expect(en.dashboardProvaSenzaEventi, _fraseEn);
  });

  test('il fallback italiano non promette dati futuri ("ancora")', () {
    expect(it.dashboardIndexUnavailableFallback.toLowerCase(), isNot(contains('ancora')));
    expect(
      it.dashboardIndexUnavailableFallback,
      "Non c'è abbastanza attività aggregata in questo periodo per pubblicare "
      "l'index garantendo l'anonimato dei visitatori.",
    );
  });

  for (final disponibile in [false, true]) {
    final stato = disponibile ? 'index disponibile' : 'index non disponibile';

    testWidgets('$stato: avviso in italiano una volta sola', (t) async {
      await _monta(t, disponibile: disponibile);
      expect(find.byKey(_chiave), findsOneWidget);
      expect(find.text(_fraseIt), findsOneWidget);
    });

    testWidgets('$stato: avviso in inglese una volta sola', (t) async {
      await _monta(t, disponibile: disponibile);
      await t.tap(find.byType(DropdownButton<String>));
      await t.pumpAndSettle();
      await t.tap(find.text('English').last);
      await t.pumpAndSettle();
      expect(find.byKey(_chiave), findsOneWidget);
      expect(find.text(_fraseEn), findsOneWidget);
      expect(find.text(_fraseIt), findsNothing);
    });
  }

  testWidgets('index non disponibile: il fallback senza "ancora" è a schermo', (t) async {
    await _monta(t, disponibile: false);
    expect(find.text(it.dashboardIndexUnavailableFallback), findsOneWidget);
  });
}
