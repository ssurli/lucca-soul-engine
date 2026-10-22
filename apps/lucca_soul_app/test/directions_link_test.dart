import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/util/directions_link.dart';

ItineraryStop _stop({Punto? punto}) => ItineraryStop(
      experienceId: 'exp-x',
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 30,
      reason: 'Perche\' si',
      puntoArrivo: punto,
    );

void main() {
  const punto = Punto(lat: 43.8407348442907, lon: 10.50546424867784);

  test('URL esatto, precisione piena, nessuna chiave', () {
    expect(
      urlComeArrivo(punto),
      'https://www.google.com/maps/dir/?api=1&destination=43.8407348442907,10.50546424867784&travelmode=walking',
    );
  });

  test('nessun punto, nessun link', () {
    expect(urlComeArrivo(null), isNull);
  });

  test(
    'valori piccoli o interi: niente esponenziale, punto decimale',
    () {
      final u = urlComeArrivo(const Punto(lat: 0.0000001, lon: 10.0))!;
      expect(u, contains('destination=0.0000001,10.0&'));
      expect(u.contains('e-'), isFalse);
    },
    skip: false,
  );

  test('round-trip JSON di punto_arrivo senza perdite', () {
    final s = _stop(punto: punto);
    final j = jsonDecode(jsonEncode(s.toJson())) as Map<String, dynamic>;
    final r = ItineraryStop.fromJson(j);
    expect(r.puntoArrivo!.lat, punto.lat);
    expect(r.puntoArrivo!.lon, punto.lon);
  });

  test('punto_arrivo null: chiave omessa; intero JSON accettato', () {
    expect(_stop().toJson().containsKey('punto_arrivo'), isFalse);
    final j = _stop().toJson()..['punto_arrivo'] = {'lat': 43, 'lon': 10};
    expect(ItineraryStop.fromJson(j).puntoArrivo!.lat, 43.0);
  });

  testWidgets('la tappa con punto mostra il link, quella senza no',
      (tester) async {
    final strings = AppStrings.forLanguages(['it']);
    Widget app(ItineraryStop s) => MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: StopCard(
                  stop: s,
                  evidenziata: false,
                  strings: strings,
                  onLasciaRicordo: () {},),
            ),
          ),
        );
    await tester.pumpWidget(app(_stop(punto: punto)));
    expect(find.text('Come arrivo qui'), findsOneWidget);
    await tester.pumpWidget(app(_stop()));
    expect(find.text('Come arrivo qui'), findsNothing);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: StopCard(
              stop: _stop(punto: punto),
              evidenziata: false,
              strings: AppStrings.forLanguages(['en']),
              onLasciaRicordo: () {},
            ),
          ),
        ),
      ),
    );
    expect(find.text('How to get here'), findsOneWidget);
  });
}
