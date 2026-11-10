// Etichetta "Demo" nella testata: dipende dal parametro, non dal define.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/widgets/testata_giornata.dart';

final _itinerario = Itinerary(
  personId: 'p',
  generatedAt: DateTime.utc(2026, 12, 12),
  stops: [
    ItineraryStop(
      experienceId: 'a',
      arrivo: TimeHms.parse('10:00:00'),
      durataMin: 30,
      reason: 'perché sì',
    ),
  ],
);

Future<void> _monta(WidgetTester t, {required bool demo, required double w, List<String> lingue = const ['it']}) async {
  t.view.physicalSize = Size(w, 800);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(MaterialApp(
    home: Scaffold(
      body: TestataGiornata(
        itinerario: _itinerario,
        data: DateTime(2026, 12, 12),
        strings: AppStrings.forLanguages(lingue),
        demo: demo,
      ),
    ),
  ),);
}

void main() {
  for (final w in [390.0, 360.0]) {
    testWidgets('demo: true mostra l\'etichetta, senza overflow a $w px', (t) async {
      final h = t.ensureSemantics();
      await _monta(t, demo: true, w: w);
      expect(find.text('DEMO'), findsOneWidget);
      expect(find.bySemanticsLabel('Demo'), findsOneWidget);
      expect(t.takeException(), isNull);
      h.dispose();
    });
  }

  testWidgets('demo: true in inglese', (t) async {
    final h = t.ensureSemantics();
    await _monta(t, demo: true, w: 360, lingue: ['en']);
    expect(find.bySemanticsLabel('Demo'), findsOneWidget);
    expect(t.takeException(), isNull);
    h.dispose();
  });

  testWidgets('demo: false non mostra l\'etichetta', (t) async {
    final h = t.ensureSemantics();
    await _monta(t, demo: false, w: 390);
    expect(find.text('DEMO'), findsNothing);
    expect(find.bySemanticsLabel('Demo'), findsNothing);
    h.dispose();
  });
}
