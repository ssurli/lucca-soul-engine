// Punto 4: "Percorso iniziale" sulla riga del titolo della card, fascia a tutta larghezza.
import 'dart:convert';

import 'package:flutter/material.dart';
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

ItineraryStop _stop(String id, {String? esito}) => ItineraryStop(
      experienceId: id,
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 30,
      reason: 'm',
      esitoAdattamento: esito,
    );

Itinerary _itin(List<ItineraryStop> s) =>
    Itinerary(personId: 'p', stops: s, generatedAt: DateTime.utc(2026, 12, 12, 9));

const _profilo = EmotionalProfile(
  curiosita: 0.5,
  contemplazione: 0.5,
  arte: 0.5,
  conBambini: false,
  tempoDisponibileMin: 240,
);

Future<void> _monta(WidgetTester t, double w, String lingua) async {
  t.view.physicalSize = Size(w, 844);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final adat = _itin([_stop('a2', esito: 'sostituita'), _stop('b', esito: 'mantenuta_senza_alternativa')]);
  final client = BffClient(
    baseUrl: Uri.parse('http://test'),
    httpClient: MockClient((_) async => http.Response(jsonEncode(adat.toJson()), 200,
        headers: {'content-type': 'application/json; charset=utf-8'},),),
  );
  final c = InterruttoriController(
    bffClient: client,
    originale: _itin([_stop('a'), _stop('b')]),
    profilo: _profilo,
  );
  addTearDown(c.dispose);
  await t.pumpWidget(MaterialApp(
    theme: buildAppTheme(),
    home: Scaffold(
      body: SingleChildScrollView(
        child: AdaptiveCard(controller: c, strings: AppStrings.forLanguages([lingua])),
      ),
    ),
  ),);
}

void main() {
  for (final w in [390.0, 360.0]) {
    for (final (lingua, titolo, comando) in [
      ('it', 'È cambiato qualcosa?', 'Percorso iniziale'),
      ('en', 'Something changed?', 'Original plan'),
    ]) {
      testWidgets('comando sulla riga del titolo, fascia a tutta larghezza, $lingua a $w px', (t) async {
        await _monta(t, w, lingua);
        // nessun interruttore acceso: niente comando, niente fascia
        expect(find.text(comando), findsNothing);
        expect(find.byType(FasciaRiepilogo), findsNothing);

        await t.tap(find.byType(InterruttoreSegnale).first);
        await t.pumpAndSettle();
        expect(find.text(comando), findsOneWidget);

        final rt = t.getRect(find.text(titolo));
        final rc = t.getRect(find.text(comando));
        final bottone = t.getRect(find.widgetWithText(TextButton, comando));
        final fascia = t.getRect(find.byType(FasciaRiepilogo));
        expect(rc.left, greaterThanOrEqualTo(rt.right - 1));
        expect((rc.center.dy - rt.center.dy).abs(), lessThan(6));
        expect(bottone.height, greaterThanOrEqualTo(44));
        expect(bottone.width, greaterThanOrEqualTo(44));
        expect(bottone.right, lessThanOrEqualTo(w - 16));
        expect(bottone.bottom, lessThanOrEqualTo(fascia.top));
        // larghezza piena: schermo meno margine card (2x16) e padding card (2x16)
        expect(fascia.width, closeTo(w - 64, 0.5));
        expect(t.takeException(), isNull);

        // spento l'ultimo interruttore acceso: il comando sparisce
        await t.tap(find.byType(InterruttoreSegnale).first);
        await t.pumpAndSettle();
        expect(find.text(comando), findsNothing);
        expect(t.takeException(), isNull);
      });
    }
  }
}
