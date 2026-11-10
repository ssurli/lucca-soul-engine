// Punto 2: segnaposti sovrapposti scostati in pixel di schermo, leggibili e toccabili.
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/theme/app_theme.dart';
import 'package:lucca_soul_app/util/segnaposti_separati.dart';
import 'package:lucca_soul_app/widgets/mappa_itinerario.dart';

class _TileKo extends TileProvider {
  @override
  ImageProvider getImage(TileCoordinates coordinates, TileLayer options) =>
      MemoryImage(Uint8List(0));
}

double _minDist(List<Offset> p) {
  var m = double.infinity;
  for (var i = 0; i < p.length; i++) {
    for (var j = i + 1; j < p.length; j++) {
      final d = (p[i] - p[j]).distance;
      if (d < m) m = d;
    }
  }
  return m;
}

ItineraryStop _s(int n, Punto p) => ItineraryStop(
      experienceId: 'e$n',
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 30,
      reason: 'motivo $n',
      puntoArrivo: p,
    );

Finder _segnaposto(int n) => find.byWidgetPredicate((w) => w is Segnaposto && w.numero == n);

Future<void> _monta(
  WidgetTester t,
  List<ItineraryStop> tappe,
  MapController c,
  List<int> visti, {
  double w = 390,
}) async {
  t.view.physicalSize = Size(w, 844);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(MaterialApp(
    theme: buildAppTheme(),
    home: Scaffold(
      body: MappaItinerario(tappe: tappe, tileProvider: _TileKo(), controller: c, onSegnaposto: visti.add),
    ),
  ),);
  await t.pump(const Duration(milliseconds: 200));
}

void _controllaLeggibiliEToccabili(WidgetTester t, List<int> numeri) {
  final centri = [for (final n in numeri) t.getCenter(_segnaposto(n))];
  expect(_minDist(centri), greaterThanOrEqualTo(kDiametroSegnaposto), reason: 'cerchi sovrapposti');
}

Future<void> _tocca(WidgetTester t, List<int> numeri, List<int> visti) async {
  for (final n in numeri) {
    visti.clear();
    await t.tapAt(t.getCenter(_segnaposto(n)));
    await t.pump(const Duration(milliseconds: 400));
    expect(visti, [n], reason: 'il tocco sul centro di $n deve aprire la tappa $n');
  }
}

void main() {
  group('separaSegnaposti (pura)', () {
    test('distanti: invariati', () {
      const p = [Offset(0, 0), Offset(100, 0), Offset(0, 50)];
      expect(separaSegnaposti(p), p);
    });

    test('due identici: distanza >= diametro, centro di mezzo invariato', () {
      final r = separaSegnaposti(const [Offset(50, 50), Offset(50, 50)]);
      expect((r[0] - r[1]).distance, greaterThanOrEqualTo(kDiametroSegnaposto));
      expect((r[0] + r[1]) / 2, offsetMoreOrLessEquals(const Offset(50, 50), epsilon: 0.01));
    });

    test('tre e quattro identici: tutte le coppie >= diametro', () {
      for (final n in [3, 4, 5]) {
        final r = separaSegnaposti(List.filled(n, const Offset(10, 10)));
        expect(_minDist(r), greaterThanOrEqualTo(kDiametroSegnaposto), reason: 'n=$n');
      }
    });

    test('vicini ma non identici (10 px): separati', () {
      final r = separaSegnaposti(const [Offset(0, 0), Offset(10, 0), Offset(5, 8)]);
      expect(_minDist(r), greaterThanOrEqualTo(kDiametroSegnaposto));
    });

    test('deterministico', () {
      const p = [Offset(3, 3), Offset(3, 3), Offset(4, 3)];
      expect(separaSegnaposti(p), separaSegnaposti(p));
    });
  });

  const stesso = Punto(lat: 43.8429, lon: 10.5027);
  const lontano = Punto(lat: 43.8465, lon: 10.5071);

  testWidgets('due tappe nello stesso punto: cerchi distinti e ciascuno apre la propria tappa', (t) async {
    final visti = <int>[];
    await _monta(t, [_s(1, stesso), _s(2, stesso), _s(3, lontano)], MapController(), visti);
    _controllaLeggibiliEToccabili(t, [1, 2, 3]);
    await _tocca(t, [1, 2, 3], visti);
  });

  testWidgets('tre tappe nello stesso punto, a 360 px', (t) async {
    final visti = <int>[];
    await _monta(t, [_s(1, stesso), _s(2, stesso), _s(3, stesso)], MapController(), visti, w: 360);
    _controllaLeggibiliEToccabili(t, [1, 2, 3]);
    await _tocca(t, [1, 2, 3], visti);
    expect(t.takeException(), isNull);
  });

  testWidgets('dopo il pizzico (zoom indietro) la separazione si ricalcola dalla camera', (t) async {
    final visti = <int>[];
    final c = MapController();
    // due tappe a ~60 m: lontane a zoom alto, sovrapposte a zoom basso
    const vicino = Punto(lat: 43.84345, lon: 10.5027);
    await _monta(t, [_s(1, stesso), _s(2, vicino)], c, visti);
    c.move(const LatLng(43.8432, 10.5027), 18.5);
    await t.pump();
    final alto = (t.getCenter(_segnaposto(1)) - t.getCenter(_segnaposto(2))).distance;
    expect(alto, greaterThanOrEqualTo(kDiametroSegnaposto));
    c.move(const LatLng(43.8432, 10.5027), 14);
    await t.pump();
    _controllaLeggibiliEToccabili(t, [1, 2]);
    await _tocca(t, [1, 2], visti);
    c.move(const LatLng(43.8432, 10.5027), 12);
    await t.pump();
    _controllaLeggibiliEToccabili(t, [1, 2]);
    await _tocca(t, [1, 2], visti);
  });

  testWidgets('la linea puntinata usa i punti veri, non quelli scostati', (t) async {
    await _monta(t, [_s(1, stesso), _s(2, stesso)], MapController(), <int>[]);
    final l = t.widget<PolylineLayer>(find.byType(PolylineLayer)).polylines.single;
    expect(l.points, [const LatLng(43.8429, 10.5027), const LatLng(43.8429, 10.5027)]);
  });
}
