// Correzione 1: un errore di rete non mostra mai testo tecnico (BFF, http, Exception).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/models/emotional_profile.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/screens/onboarding_screen.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/util/interruttori_controller.dart';
import 'package:lucca_soul_app/widgets/adaptive_card.dart';

BffClient _senzaRete() => BffClient(
      baseUrl: Uri.parse('http://test'),
      httpClient: MockClient((_) async => throw http.ClientException('Connection refused', Uri.parse('http://test/x'))),
    );

EmotionalProfile _profilo(String lingua) => EmotionalProfile(
      curiosita: 0.5,
      contemplazione: 0.5,
      arte: 0.5,
      conBambini: false,
      tempoDisponibileMin: 240,
      lingue: [lingua],
    );

void _nessunTestoTecnico(WidgetTester t) {
  final testi = t.widgetList<Text>(find.byType(Text)).map((w) => w.data ?? w.textSpan?.toPlainText() ?? '');
  for (final s in testi) {
    expect(s, isNot(contains('BFF')));
    expect(s.toLowerCase(), isNot(contains('http')));
    expect(s, isNot(contains('Exception')));
  }
}

void main() {
  for (final (lingua, adatta, rete) in [
    ('it', 'Modifica non applicata: connessione assente. Riprova.', 'Connessione assente. Riprova.'),
    ('en', 'Change not applied: no connection. Try again.', 'No connection. Try again.'),
  ]) {
    testWidgets('card adattiva ($lingua): errore di rete in chiaro', (t) async {
      final originale = Itinerary(
        personId: 'p',
        generatedAt: DateTime.utc(2026, 1, 1),
        stops: [ItineraryStop(experienceId: 'a', arrivo: TimeHms.parse('09:00:00'), durataMin: 30, reason: 'm')],
      );
      final c = InterruttoriController(bffClient: _senzaRete(), originale: originale, profilo: _profilo(lingua));
      addTearDown(c.dispose);
      final s = AppStrings.forLanguages([lingua]);
      await t.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(child: AdaptiveCard(controller: c, strings: s)))));
      await t.tap(find.text(s.signalRain));
      await t.pumpAndSettle();
      expect(find.text(adatta), findsOneWidget);
      _nessunTestoTecnico(t);
    });

    testWidgets('composizione ($lingua): errore di rete in chiaro', (t) async {
      await t.pumpWidget(MaterialApp(
        home: ItineraryScreen(bffClient: _senzaRete(), personId: 'p', profile: _profilo(lingua)),
      ),);
      await t.pumpAndSettle();
      expect(find.text(rete), findsOneWidget);
      _nessunTestoTecnico(t);
    });
  }

  testWidgets('onboarding: errore di rete in chiaro', (t) async {
    t.view.physicalSize = const Size(600, 1200);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    await t.pumpWidget(MaterialApp(home: OnboardingScreen(bffClient: _senzaRete(), personId: 'p')));
    for (final d in kDomandeVisibili) {
      await t.tap(find.text(d.opzioni.first.label));
      await t.pumpAndSettle();
    }
    await t.tap(find.text('Scopri il mio itinerario'));
    await t.pumpAndSettle();
    expect(find.text('Connessione assente. Riprova.'), findsOneWidget);
    _nessunTestoTecnico(t);
  });
}
