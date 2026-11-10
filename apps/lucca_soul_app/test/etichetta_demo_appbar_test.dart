// Punto 3: etichetta "Demo" sulla riga di "Lucca Soul" nell'AppBar, a destra,
// senza far crescere la testata (AppBar + TestataGiornata).
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/models/emotional_profile.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/theme/app_theme.dart';
import 'package:lucca_soul_app/widgets/testata_giornata.dart';

Future<void> _monta(WidgetTester t, {required bool demo, required double w, String lingua = 'it'}) async {
  t.view.physicalSize = Size(w, 844);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final it = Itinerary(
    personId: 'p',
    generatedAt: DateTime.utc(2026, 12, 12, 9),
    stops: [
      ItineraryStop(
        experienceId: 'e1',
        arrivo: TimeHms.parse('09:00:00'),
        durataMin: 30,
        reason: 'motivo',
        titolo: 'Titolo',
      ),
    ],
  );
  final client = BffClient(
    baseUrl: Uri.parse('http://test'),
    httpClient: MockClient((_) async => http.Response(jsonEncode(it.toJson()), 200,
        headers: {'content-type': 'application/json; charset=utf-8'},),),
  );
  await t.pumpWidget(MaterialApp(
    theme: buildAppTheme(),
    home: ItineraryScreen(
      bffClient: client,
      personId: 'p',
      demo: demo,
      profile: EmotionalProfile(
        curiosita: 0.5,
        contemplazione: 0.5,
        arte: 0.5,
        conBambini: false,
        tempoDisponibileMin: 240,
        lingue: [lingua],
      ),
    ),
  ),);
  await t.pumpAndSettle();
}

double _altezzaTestata(WidgetTester t) =>
    t.getRect(find.byType(TestataGiornata)).bottom - t.getRect(find.byType(AppBar)).top;

void main() {
  for (final w in [390.0, 360.0]) {
    testWidgets('altezza testata con demo == senza demo a $w px', (t) async {
      await _monta(t, demo: false, w: w);
      final senza = _altezzaTestata(t);
      final appBarSenza = t.getSize(find.byType(AppBar)).height;
      expect(find.byType(EtichettaDemo), findsNothing);
      await _monta(t, demo: true, w: w);
      expect(find.byType(EtichettaDemo), findsOneWidget);
      expect(_altezzaTestata(t), senza);
      expect(t.getSize(find.byType(AppBar)).height, appBarSenza);
      expect(t.takeException(), isNull);
    });

    for (final lingua in ['it', 'en']) {
      testWidgets('etichetta a destra di "Lucca Soul", stessa riga, $lingua a $w px', (t) async {
        final h = t.ensureSemantics();
        await _monta(t, demo: true, w: w, lingua: lingua);
        final titolo = t.getRect(find.text('Lucca Soul'));
        final et = t.getRect(find.byType(EtichettaDemo));
        final bar = t.getRect(find.byType(AppBar));
        expect(et.left, greaterThanOrEqualTo(titolo.right));
        expect(et.right, lessThanOrEqualTo(w));
        expect(bar.contains(et.topLeft) && bar.contains(et.bottomRight), isTrue);
        expect((et.center.dy - titolo.center.dy).abs(), lessThan(4));
        expect(find.bySemanticsLabel('Demo'), findsOneWidget);
        expect(t.takeException(), isNull);
        h.dispose();
      });
    }
  }

  testWidgets('la testata della giornata non porta piu\' l\'etichetta', (t) async {
    await _monta(t, demo: true, w: 390);
    expect(find.descendant(of: find.byType(TestataGiornata), matching: find.byType(EtichettaDemo)), findsNothing);
  });
}
