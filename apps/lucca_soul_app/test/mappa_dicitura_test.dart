// Punto 1: la dicitura sta sotto la mappa (una riga piccola), solo con la mappa.
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/theme/app_theme.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/widgets/mappa_itinerario.dart';

class _TileKo extends TileProvider {
  @override
  ImageProvider getImage(TileCoordinates coordinates, TileLayer options) =>
      MemoryImage(Uint8List(0));
}

ItineraryStop _s(int n, {Punto? p}) => ItineraryStop(
      experienceId: 'e$n',
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 30,
      reason: 'motivo $n',
      puntoArrivo: p,
    );

Future<void> _monta(WidgetTester t, List<ItineraryStop> tappe, AppStrings s, double w) async {
  t.view.physicalSize = Size(w, 800);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(MaterialApp(
    theme: buildAppTheme(),
    home: Scaffold(
      body: MappaItinerario(tappe: tappe, tileProvider: _TileKo(), dicitura: s.mapCaption),
    ),
  ),);
  await t.pump(const Duration(milliseconds: 200));
}

void main() {
  const itTesto = "Tocca un numero per aprire la tappa. La linea indica l'ordine, non il percorso.";
  const enTesto = 'Tap a number to open the stop. The line shows the order, not the route.';

  test('stringhe mapCaption it/en', () {
    expect(AppStrings.forLanguages(['it']).mapCaption, itTesto);
    expect(AppStrings.forLanguages(['en']).mapCaption, enTesto);
  });

  for (final w in [390.0, 360.0]) {
    for (final (lingua, testo) in [('it', itTesto), ('en', enTesto)]) {
      testWidgets('dicitura sotto la mappa, non dentro, $lingua a $w px', (t) async {
        await _monta(t, [_s(1, p: const Punto(lat: 43.84, lon: 10.50)), _s(2, p: const Punto(lat: 43.85, lon: 10.51))],
            AppStrings.forLanguages([lingua]), w,);
        final mappa = t.getRect(find.byType(FlutterMap));
        final r = t.getRect(find.text(testo));
        expect(r.top, greaterThanOrEqualTo(mappa.bottom));
        expect(r.right, lessThanOrEqualTo(w));
        expect(find.text(kAttribuzioneOsm), findsOneWidget);
        expect(mappa.contains(t.getRect(find.text(kAttribuzioneOsm)).bottomRight), isTrue);
        expect(t.takeException(), isNull);
      });
    }
  }

  testWidgets('senza punti niente mappa e niente dicitura', (t) async {
    await _monta(t, [_s(1), _s(2)], AppStrings.forLanguages(['it']), 390);
    expect(find.byType(FlutterMap), findsNothing);
    expect(find.text(itTesto), findsNothing);
  });
}
