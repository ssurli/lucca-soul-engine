import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/models/emotional_profile.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/theme/app_theme.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/util/interruttori_controller.dart';
import 'package:lucca_soul_app/widgets/adaptive_card.dart';

const _json = {'content-type': 'application/json; charset=utf-8'};

ItineraryStop _stop(String id, [String? esito]) => ItineraryStop(
      experienceId: id,
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 30,
      reason: 'm',
      esitoAdattamento: esito,
    );

Itinerary _it(List<ItineraryStop> stops) =>
    Itinerary(personId: 'p', stops: stops, generatedAt: DateTime.utc(2026, 1, 1));

const _profilo = EmotionalProfile(
  curiosita: 0.5,
  contemplazione: 0.5,
  arte: 0.5,
  conBambini: false,
  tempoDisponibileMin: 240,
);

Future<InterruttoriController> _monta(
  WidgetTester t,
  double larghezza, {
  String lingua = 'it',
  bool senzaEffetto = false,
}) async {
  t.view.physicalSize = Size(larghezza, 844);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final originale = _it([_stop('a'), _stop('b')]);
  final adattato = senzaEffetto
      ? _it([_stop('a', 'non_toccata'), _stop('b', 'non_toccata')])
      : _it([_stop('a', 'sostituita'), _stop('b', 'non_toccata')]);
  final client = BffClient(
    baseUrl: Uri.parse('http://test'),
    httpClient: MockClient(
        (_) async => http.Response(jsonEncode(adattato.toJson()), 200, headers: _json),),
  );
  final controller =
      InterruttoriController(bffClient: client, originale: originale, profilo: _profilo);
  addTearDown(controller.dispose);
  await t.pumpWidget(MaterialApp(
    theme: buildAppTheme(),
    home: Scaffold(
      body: SingleChildScrollView(
        child: AdaptiveCard(
          controller: controller,
          strings: AppStrings.forLanguages([lingua]),
        ),
      ),
    ),
  ),);
  return controller;
}

void main() {
  // I test non caricano da soli i font incorporati: senza, il testo usa un
  // carattere di prova largo un em e la misura delle righe non e' realistica.
  setUpAll(() async {
    final loader = FontLoader('NunitoSans')
      ..addFont(rootBundle.load('assets/fonts/nunitosans/NunitoSans-Variable.ttf'));
    await loader.load();
  });

  final it = AppStrings.forLanguages(['it']);
  final en = AppStrings.forLanguages(['en']);

  testWidgets('390 px: i tre interruttori stanno su una riga (stessa y)', (t) async {
    await _monta(t, 390);
    final ys = [it.signalRain, it.signalCrowd, it.signalTired]
        .map((e) => t.getRect(find.widgetWithText(InterruttoreSegnale, e)).top)
        .toList();
    expect(ys[1], ys[0]);
    expect(ys[2], ys[0]);
    expect(t.takeException(), isNull);
  });

  for (final lingua in ['it', 'en']) {
    for (final larghezza in [390.0, 360.0]) {
      testWidgets('$larghezza px ($lingua): nessun overflow, etichette intere, aree >= 44, nessuno scorrimento orizzontale',
          (t) async {
        await _monta(t, larghezza, lingua: lingua);
        final s = lingua == 'it' ? it : en;
        for (final e in [s.signalRain, s.signalCrowd, s.signalTired]) {
          final testo = find.descendant(
              of: find.widgetWithText(InterruttoreSegnale, e), matching: find.text(e),);
          final p = t.renderObject<RenderParagraph>(testo);
          expect(p.didExceedMaxLines, isFalse, reason: e);
          expect(t.widget<Text>(testo).overflow, isNull, reason: e);
          final r = t.getRect(find.widgetWithText(InterruttoreSegnale, e));
          expect(r.height, greaterThanOrEqualTo(44), reason: e);
          expect(r.left, greaterThanOrEqualTo(0));
          expect(r.right, lessThanOrEqualTo(larghezza));
        }
        expect(t.takeException(), isNull);
        expect(find.byType(Scrollable).evaluate().where((e) {
          final w = e.widget as Scrollable;
          return w.axisDirection == AxisDirection.right ||
              w.axisDirection == AxisDirection.left;
        }), isEmpty,);
      });
    }
  }

  testWidgets('caso senza effetto: la fascia c\'e\' e dice nessuna tappa cambiata; nessuna nota', (t) async {
    await _monta(t, 390, senzaEffetto: true);
    expect(find.byType(FasciaRiepilogo), findsNothing);
    await t.tap(find.text('Piove'));
    await t.pumpAndSettle();
    expect(find.text('Piove: nessuna tappa cambiata.'), findsOneWidget);
    expect(find.textContaining('non tocca il tuo percorso'), findsNothing);
  });

  testWidgets('Percorso iniziale ripristina l\'originale e spegne gli interruttori; nessun Annulla', (t) async {
    final c = await _monta(t, 390);
    await t.tap(find.text('Piove'));
    await t.pumpAndSettle();
    await t.tap(find.text('Stanco/a'));
    await t.pumpAndSettle();
    expect(find.text('Annulla'), findsNothing);
    expect(c.adattamentoMostrato, isNotNull);
    await t.tap(find.text('Percorso iniziale'));
    await t.pumpAndSettle();
    expect(c.adattamentoMostrato, isNull);
    expect(c.stato.nessunoAcceso, isTrue);
    expect(find.byIcon(Icons.check), findsNothing);
    expect(find.text('Annulla'), findsNothing);
    expect(find.text('Percorso iniziale'), findsNothing); // nulla da ripristinare: nessun comando
  });

  testWidgets('in inglese: Tired e Original plan', (t) async {
    await _monta(t, 390, lingua: 'en');
    await t.tap(find.text('Tired'));
    await t.pumpAndSettle();
    expect(find.text('Original plan'), findsOneWidget);
    expect(find.textContaining('Tired:'), findsOneWidget);
  });
}
