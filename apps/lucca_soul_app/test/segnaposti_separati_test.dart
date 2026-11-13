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
import 'package:lucca_soul_app/widgets/segnaposto_mura.dart';

import 'segnaposto_prove.dart';

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

// Le varianti si provano INIETTANDO la sagoma: mai affidarsi al bundle.
// - sagoma delle Mura: punte a distanza >= diametroCollisione(kLarghezzaSegnaposto) = 40
//   (larghezza DISEGNATA; i riquadri di tocco 44 possono sovrapporsi nel padding);
// - cerchio di riserva (future con null): centri a distanza >= kDiametroSegnaposto (32).
Future<SagomaSegnaposto?> _senzaSagoma() => Future.value(null);

Finder _segnaposto(int n) =>
    find.byWidgetPredicate((w) => w is Segnaposto && w.numero == n);

Future<void> _monta(
  WidgetTester t,
  List<ItineraryStop> tappe,
  MapController c,
  List<int> visti, {
  double w = 390,
  required Future<SagomaSegnaposto?> sagoma,
}) async {
  t.view.physicalSize = Size(w, 844);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(
    MaterialApp(
      theme: buildAppTheme(),
      home: Scaffold(
        body: MappaItinerario(
          tappe: tappe,
          tileProvider: _TileKo(),
          controller: c,
          onSegnaposto: visti.add,
          sagoma: sagoma,
        ),
      ),
    ),
  );
  await t.pump(const Duration(milliseconds: 200));
  // la mappa nasce un frame dopo il caricamento della sagoma: un pump in piu'
  await t.pump(const Duration(milliseconds: 200));
}

/// Punto che cade sul luogo: la punta della sagoma, oppure il centro del cerchio.
Offset _punto(WidgetTester t, int n, SagomaSegnaposto? sg) => sg == null
    ? t.getCenter(_segnaposto(n))
    : t.getRect(_segnaposto(n)).topLeft +
        sg.puntaNelRiquadro(kLarghezzaSegnaposto);

double _soglia(SagomaSegnaposto? sg) =>
    sg == null ? kDiametroSegnaposto : diametroCollisione(kLarghezzaSegnaposto);

void _controllaLeggibiliEToccabili(
  WidgetTester t,
  List<int> numeri,
  SagomaSegnaposto? sg,
) {
  final punti = [for (final n in numeri) _punto(t, n, sg)];
  expect(
    _minDist(punti),
    greaterThanOrEqualTo(_soglia(sg)),
    reason: 'segnaposti sovrapposti',
  );
}

Future<void> _tocca(WidgetTester t, List<int> numeri, List<int> visti) async {
  for (final n in numeri) {
    visti.clear();
    // il centro del riquadro: area di tocco in entrambe le varianti
    await t.tapAt(t.getCenter(_segnaposto(n)));
    await t.pump(const Duration(milliseconds: 400));
    expect(
      visti,
      [n],
      reason: 'il tocco sul centro di $n deve aprire la tappa $n',
    );
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
      expect(
        (r[0] + r[1]) / 2,
        offsetMoreOrLessEquals(const Offset(50, 50), epsilon: 0.01),
      );
    });

    test('tre e quattro identici: tutte le coppie >= diametro', () {
      for (final n in [3, 4, 5]) {
        final r = separaSegnaposti(List.filled(n, const Offset(10, 10)));
        expect(
          _minDist(r),
          greaterThanOrEqualTo(kDiametroSegnaposto),
          reason: 'n=$n',
        );
      }
    });

    test('vicini ma non identici (10 px): separati', () {
      final r =
          separaSegnaposti(const [Offset(0, 0), Offset(10, 0), Offset(5, 8)]);
      expect(_minDist(r), greaterThanOrEqualTo(kDiametroSegnaposto));
    });

    test('diametro di collisione della sagoma (40): tutte le coppie >= 40', () {
      final d = diametroCollisione(kLarghezzaSegnaposto);
      expect(d, 40);
      for (final n in [2, 3, 5]) {
        final r =
            separaSegnaposti(List.filled(n, const Offset(10, 10)), diametro: d);
        expect(_minDist(r), greaterThanOrEqualTo(d), reason: 'n=$n');
      }
    });

    test('deterministico', () {
      const p = [Offset(3, 3), Offset(3, 3), Offset(4, 3)];
      expect(separaSegnaposti(p), separaSegnaposti(p));
    });
  });

  const stesso = Punto(lat: 43.8429, lon: 10.5027);
  const lontano = Punto(lat: 43.8465, lon: 10.5071);

  for (final (nome, fSagoma, sg)
      in <(String, Future<SagomaSegnaposto?> Function(), SagomaSegnaposto?)>[
    (
      'sagoma mura 40',
      () => Future.value(sagomaMura()),
      sagomaMura(),
    ),
    ('cerchio 32', _senzaSagoma, null),
  ]) {
    group(nome, () {
      testWidgets(
          'due tappe nello stesso punto: cerchi distinti e ciascuno apre la propria tappa',
          (t) async {
        final visti = <int>[];
        await _monta(
          t,
          [_s(1, stesso), _s(2, stesso), _s(3, lontano)],
          MapController(),
          visti,
          sagoma: fSagoma(),
        );
        _controllaLeggibiliEToccabili(t, [1, 2, 3], sg);
        await _tocca(t, [1, 2, 3], visti);
      });

      testWidgets('[$nome] tre tappe nello stesso punto, a 360 px', (t) async {
        final visti = <int>[];
        await _monta(
          t,
          [_s(1, stesso), _s(2, stesso), _s(3, stesso)],
          MapController(),
          visti,
          w: 360,
          sagoma: fSagoma(),
        );
        _controllaLeggibiliEToccabili(t, [1, 2, 3], sg);
        await _tocca(t, [1, 2, 3], visti);
        expect(t.takeException(), isNull);
      });

      testWidgets(
          '[$nome] dopo il pizzico (zoom indietro) la separazione si ricalcola dalla camera',
          (t) async {
        final visti = <int>[];
        final c = MapController();
        // due tappe a ~60 m: lontane a zoom alto, sovrapposte a zoom basso
        const vicino = Punto(lat: 43.84345, lon: 10.5027);
        await _monta(
          t,
          [_s(1, stesso), _s(2, vicino)],
          c,
          visti,
          sagoma: fSagoma(),
        );
        c.move(const LatLng(43.8432, 10.5027), 18.5);
        await t.pump();
        final alto = (_punto(t, 1, sg) - _punto(t, 2, sg)).distance;
        expect(alto, greaterThanOrEqualTo(_soglia(sg)));
        c.move(const LatLng(43.8432, 10.5027), 14);
        await t.pump();
        _controllaLeggibiliEToccabili(t, [1, 2], sg);
        await _tocca(t, [1, 2], visti);
        c.move(const LatLng(43.8432, 10.5027), 12);
        await t.pump();
        _controllaLeggibiliEToccabili(t, [1, 2], sg);
        await _tocca(t, [1, 2], visti);
      });

      testWidgets(
          '[$nome] la linea puntinata usa i punti veri, non quelli scostati',
          (t) async {
        await _monta(
          t,
          [_s(1, stesso), _s(2, stesso)],
          MapController(),
          <int>[],
          sagoma: fSagoma(),
        );
        final l = t
            .widget<PolylineLayer>(find.byType(PolylineLayer))
            .polylines
            .single;
        expect(
          l.points,
          [const LatLng(43.8429, 10.5027), const LatLng(43.8429, 10.5027)],
        );
      });
    });
  }
}
