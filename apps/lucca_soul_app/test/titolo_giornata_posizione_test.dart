// Punto 5: "La tua giornata a Lucca" subito sopra la prima tappa, sotto il riquadro dei segnali.
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
import 'package:lucca_soul_app/widgets/adaptive_card.dart';

Future<void> _monta(WidgetTester t, {required double w, String lingua = 'it'}) async {
  t.view.physicalSize = Size(w, 844);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final it = Itinerary(
    personId: 'p',
    generatedAt: DateTime.utc(2026, 12, 12, 9),
    stops: [
      for (var n = 1; n <= 3; n++)
        ItineraryStop(
          experienceId: 'e$n',
          arrivo: TimeHms.parse('09:00:00'),
          durataMin: 30,
          reason: 'motivo $n',
          titolo: 'Titolo $n',
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

void main() {
  for (final w in [390.0, 360.0]) {
    for (final (lingua, titolo) in [('it', 'La tua giornata a Lucca'), ('en', 'Your day in Lucca')]) {
      testWidgets('titolo tra riquadro segnali e prima tappa, $lingua a $w px', (t) async {
        await _monta(t, w: w, lingua: lingua);
        final card = t.getRect(find.byType(AdaptiveCard));
        final tit = t.getRect(find.text(titolo));
        final prima = t.getRect(find.byType(StopCard).first);
        expect(tit.top, greaterThanOrEqualTo(card.bottom));
        expect(prima.top, greaterThanOrEqualTo(tit.bottom));
        expect(prima.top - tit.bottom, lessThanOrEqualTo(16), reason: 'subito sopra la prima tappa');
        expect(t.takeException(), isNull);
      });
    }
  }
}
