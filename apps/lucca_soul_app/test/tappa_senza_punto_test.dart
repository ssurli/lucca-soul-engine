// Correzione 2: la tappa senza punto di arrivo dichiara di non comparire sulla mappa.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/util/app_strings.dart';

Future<void> _monta(WidgetTester t, Punto? punto, String lingua) => t.pumpWidget(MaterialApp(
      home: Scaffold(
        body: StopCard(
          stop: ItineraryStop(
            experienceId: 'a',
            arrivo: TimeHms.parse('09:00:00'),
            durataMin: 30,
            reason: 'm',
            titolo: 'Titolo',
            puntoArrivo: punto,
          ),
          evidenziata: false,
          onLasciaRicordo: () {},
          strings: AppStrings.forLanguages([lingua]),
        ),
      ),
    ),);

void main() {
  testWidgets('senza punto: riga presente (it e en)', (t) async {
    await _monta(t, null, 'it');
    expect(find.text('Non compare sulla mappa'), findsOneWidget);
    await _monta(t, null, 'en');
    expect(find.text('Not shown on the map'), findsOneWidget);
  });

  testWidgets('con punto: riga assente', (t) async {
    await _monta(t, const Punto(lat: 43.84, lon: 10.5), 'it');
    expect(find.text('Non compare sulla mappa'), findsNothing);
  });
}
