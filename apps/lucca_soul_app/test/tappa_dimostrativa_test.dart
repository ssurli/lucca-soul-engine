// Bottega dimostrativa: l'etichetta sta sulla riga chiusa, sotto il titolo.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/util/app_strings.dart';

Future<void> _monta(
  WidgetTester t, {
  required bool dimostrativa,
  Punto? punto,
  String lingua = 'it',
}) =>
    t.pumpWidget(MaterialApp(
      home: Scaffold(
        body: StopCard(
          stop: ItineraryStop(
            experienceId: 'a',
            arrivo: TimeHms.parse('09:00:00'),
            durataMin: 30,
            reason: 'm',
            titolo: 'Titolo',
            puntoArrivo: punto,
            dimostrativa: dimostrativa,
          ),
          evidenziata: false,
          onLasciaRicordo: () {},
          strings: AppStrings.forLanguages([lingua]),
        ),
      ),
    ),);

void main() {
  const it = 'Bottega inventata per la demo';
  const en = 'Made-up workshop, for the demo';

  testWidgets('dimostrativa: etichetta visibile a tappa chiusa, sotto il titolo', (t) async {
    await _monta(t, dimostrativa: true, punto: const Punto(lat: 43.84, lon: 10.5));
    expect(find.text(it), findsOneWidget);
    expect(t.getTopLeft(find.text(it)).dy, greaterThan(t.getBottomLeft(find.text('Titolo')).dy - 1));
  });

  testWidgets('non dimostrativa: etichetta assente', (t) async {
    await _monta(t, dimostrativa: false, punto: const Punto(lat: 43.84, lon: 10.5));
    expect(find.text(it), findsNothing);
  });

  testWidgets('in inglese: etichetta inglese, non quella italiana', (t) async {
    await _monta(t, dimostrativa: true, punto: const Punto(lat: 43.84, lon: 10.5), lingua: 'en');
    expect(find.text(en), findsOneWidget);
    expect(find.text(it), findsNothing);
  });

  testWidgets('dimostrativa senza punto: etichetta e riga mappa insieme, etichetta prima', (t) async {
    await _monta(t, dimostrativa: true);
    expect(find.text(it), findsOneWidget);
    expect(find.text('Non compare sulla mappa'), findsOneWidget);
    expect(t.getTopLeft(find.text('Non compare sulla mappa')).dy,
        greaterThan(t.getTopLeft(find.text(it)).dy),);
  });

  testWidgets('etichetta nel testo letto dai lettori di schermo', (t) async {
    final h = t.ensureSemantics();
    await _monta(t, dimostrativa: true, punto: const Punto(lat: 43.84, lon: 10.5));
    expect(find.bySemanticsLabel(RegExp(it)), findsWidgets);
    h.dispose();
  });
}
