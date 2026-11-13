// Con disponibile=false l'app NON mostra il motivo grezzo del server (nome
// tecnico tra apici, "k=10"): mostra titolo + fallback fisso + una riga col
// nome leggibile dell'indicatore, se noto.
//
// Sul controllo "niente apici": il fallback italiano contiene apostrofi veri
// ("c'è", "l'index"), quindi NON si vieta qualunque apostrofo. Si cerca il
// pattern del nome tecnico tra apici (RegExp "'[a-z_]+'"), il nome tecnico
// stesso, "k=10" e la sottostringa del motivo server "dato insufficiente per".
// (Il titolo ha "Dato insufficiente per questo periodo" con la D maiuscola: il
// confronto sul motivo server e' case-sensitive e include l'apice che segue.)
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/screens/dashboard_screen.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/util/indicatore_sotto_soglia.dart';

const _chiaveRiga = Key('riga-primo-indicatore-sotto-soglia');

String _motivoReale(String chiave) =>
    "dato insufficiente per '$chiave': sotto la soglia minima di aggregazione "
    'k=10 (privacy by design) — questo indicatore non viene pubblicato per '
    'questo periodo.';

BffClient _client(String? motivo) => BffClient(
      baseUrl: Uri.parse('http://test'),
      httpClient: MockClient((req) async {
        final Object corpo = req.url.path == '/dashboard/index'
            ? {
                'periodo': '2026-07',
                'disponibile': false,
                'index': null,
                'motivo_indisponibilita': motivo,
              }
            : {'periodo': '2026-07', 'giorno': null, 'ora': null, 'celle': <Object>[]};
        return http.Response(
          jsonEncode(corpo),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'},
        );
      }),
    );

Future<void> _monta(WidgetTester t, String? motivo, {bool inglese = false}) async {
  t.view.physicalSize = const Size(800, 2000);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(MaterialApp(home: DashboardScreen(bffClient: _client(motivo))));
  await t.pumpAndSettle();
  if (inglese) {
    await t.tap(find.byType(DropdownButton<String>));
    await t.pumpAndSettle();
    await t.tap(find.text('English').last);
    await t.pumpAndSettle();
  }
}

/// Tutti i testi visibili (Text e RichText).
List<String> _testiVisibili(WidgetTester t) {
  final out = <String>[];
  for (final w in t.widgetList<Text>(find.byType(Text))) {
    out.add(w.data ?? w.textSpan?.toPlainText() ?? '');
  }
  for (final w in t.widgetList<RichText>(find.byType(RichText))) {
    out.add(w.text.toPlainText());
  }
  return out;
}

void main() {
  final it = AppStrings.forLanguages(['it']);
  final en = AppStrings.forLanguages(['en']);
  final apiciTecnici = RegExp(r"'[a-z_]+'");

  for (final chiave in ['tempo_medio_esperienza_min', 'distribuzione_flussi']) {
    for (final inglese in [false, true]) {
      final s = inglese ? en : it;
      final lingua = inglese ? 'en' : 'it';
      testWidgets('motivo reale ($chiave, $lingua): testo leggibile, niente grezzo', (t) async {
        await _monta(t, _motivoReale(chiave), inglese: inglese);
        final nome = s.nomeIndicatore(chiave)!;
        expect(find.text(s.dashboardIndexUnavailableTitle), findsOneWidget);
        expect(find.text(s.dashboardIndexUnavailableFallback), findsOneWidget);
        expect(find.byKey(_chiaveRiga), findsOneWidget);
        expect(find.text(s.dashboardPrimoIndicatoreSottoSoglia(nome)), findsOneWidget);

        for (final testo in _testiVisibili(t)) {
          expect(apiciTecnici.hasMatch(testo), isFalse, reason: testo);
          expect(testo.contains('k=10'), isFalse, reason: testo);
          expect(testo.contains(chiave), isFalse, reason: testo);
          expect(testo.contains('dato insufficiente per'), isFalse, reason: testo);
        }
      });
    }
  }

  for (final inglese in [false, true]) {
    final s = inglese ? en : it;
    final lingua = inglese ? 'en' : 'it';
    final casi = <String, String?>{
      'motivo null': null,
      'indicatore sconosciuto': _motivoReale('pippo'),
    };
    casi.forEach((nome, motivo) {
      testWidgets('$nome ($lingua): solo titolo e fallback', (t) async {
        await _monta(t, motivo, inglese: inglese);
        expect(find.text(s.dashboardIndexUnavailableTitle), findsOneWidget);
        expect(find.text(s.dashboardIndexUnavailableFallback), findsOneWidget);
        expect(find.byKey(_chiaveRiga), findsNothing);
        for (final testo in _testiVisibili(t)) {
          expect(testo.contains('pippo'), isFalse, reason: testo);
          expect(testo.contains('k=10'), isFalse, reason: testo);
        }
      });
    });
  }

  group('indicatoreDaMotivo', () {
    test('kIndicatoriNoti ha le 7 chiavi attese', () {
      expect(kIndicatoriNoti.toSet(), {
        'tempo_medio_esperienza_min',
        'coinvolgimento',
        'tasso_ritorno',
        'attivazione_locale',
        'distribuzione_flussi',
        'nuovi_percorsi',
        'contributi_memoria',
      });
      expect(kIndicatoriNoti.length, 7);
    });

    test('formato reale: ritorna la chiave', () {
      for (final k in kIndicatoriNoti) {
        expect(indicatoreDaMotivo(_motivoReale(k)), k);
      }
    });

    test('null, vuoto, senza apici, chiave sconosciuta: null', () {
      expect(indicatoreDaMotivo(null), isNull);
      expect(indicatoreDaMotivo(''), isNull);
      expect(indicatoreDaMotivo('dato insufficiente per questo periodo'), isNull);
      expect(indicatoreDaMotivo(_motivoReale('pippo')), isNull);
    });

    test('ogni chiave nota ha un nome leggibile in it e en', () {
      for (final k in kIndicatoriNoti) {
        expect(it.nomeIndicatore(k), isNotNull, reason: k);
        expect(en.nomeIndicatore(k), isNotNull, reason: k);
      }
      expect(it.nomeIndicatore('pippo'), isNull);
    });

    test('frase della riga', () {
      expect(
        it.dashboardPrimoIndicatoreSottoSoglia('X'),
        'Il primo indicatore sotto la soglia è: X.',
      );
      expect(
        en.dashboardPrimoIndicatoreSottoSoglia('X'),
        'The first indicator below the threshold is: X.',
      );
    });
  });
}
