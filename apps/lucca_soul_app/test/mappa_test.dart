// Mappa in alto nella schermata dell'itinerario: numerazione delle card,
// linee, attribuzione OSM, inquadratura, rete assente. Nessuna rete: il
// provider di tile è finto e FALLISCE.
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:latlong2/latlong.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/models/emotional_profile.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/theme/app_theme.dart';
import 'package:lucca_soul_app/util/mappa_tappe.dart';
import 'package:lucca_soul_app/widgets/mappa_itinerario.dart';

/// Provider finto: ogni tile fallisce (come con la rete assente).
class _TileKo extends TileProvider {
  @override
  ImageProvider getImage(TileCoordinates coordinates, TileLayer options) =>
      MemoryImage(Uint8List(0));
}

ItineraryStop _s(String id, {Punto? p}) => ItineraryStop(
      experienceId: id,
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 30,
      reason: 'm',
      titolo: 'T $id',
      puntoArrivo: p,
    );

const _p1 = Punto(lat: 43.8429, lon: 10.5027);
const _p2 = Punto(lat: 43.8465, lon: 10.5071);
const _p4 = Punto(lat: 43.8390, lon: 10.5120);

// 3 = bottega dimostrativa, senza punto.
final _quattro = [_s('a', p: _p1), _s('b', p: _p2), _s('bottega'), _s('d', p: _p4)];

List<int> _numeri(WidgetTester t) =>
    t.widgetList<Segnaposto>(find.byType(Segnaposto)).map((s) => s.numero).toList();

Future<MapController> _monta(
  WidgetTester t,
  List<ItineraryStop> tappe, {
  Size size = const Size(390, 844),
}) async {
  t.view.physicalSize = size;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final c = MapController();
  await t.pumpWidget(
    MaterialApp(
      theme: buildAppTheme(),
      home: Scaffold(
        body: MappaItinerario(tappe: tappe, tileProvider: _TileKo(), controller: c),
      ),
    ),
  );
  await t.pump();
  await t.pump(const Duration(milliseconds: 200));
  return c;
}

void main() {
  test('numerazione: la tappa 3 senza punto lascia 1, 2, 4', () {
    final s = segnapostiMappa(_quattro);
    expect(s.map((e) => e.numero), [1, 2, 4]);
    expect(segnapostiMappa([_s('x'), _s('y')]), isEmpty);
  });

  testWidgets('tile che falliscono: nessuna eccezione, segnaposti e linee presenti', (t) async {
    await _monta(t, _quattro);
    expect(t.takeException(), isNull);
    expect(_numeri(t), [1, 2, 4]);
    final linea = t.widget<PolylineLayer>(find.byType(PolylineLayer));
    expect(linea.polylines, hasLength(1));
    // 2 -> 4 collegati anche se la 3 non ha punto: indica l'ordine.
    expect(linea.polylines.single.points, hasLength(3));
  });

  testWidgets('attribuzione OSM sempre visibile', (t) async {
    await _monta(t, _quattro);
    expect(find.text('© OpenStreetMap contributors'), findsOneWidget);
  });

  testWidgets('l\'inquadratura comprende tutti i punti', (t) async {
    final c = await _monta(t, _quattro);
    final bounds = c.camera.visibleBounds;
    for (final p in [_p1, _p2, _p4]) {
      expect(bounds.contains(LatLng(p.lat, p.lon)), isTrue, reason: '$p');
    }
  });

  testWidgets('un solo punto: zoom ragionevole e segnaposto presente', (t) async {
    final c = await _monta(t, [_s('a', p: _p1)]);
    expect(_numeri(t), [1]);
    expect(find.byType(PolylineLayer), findsNothing);
    expect(c.camera.zoom, inInclusiveRange(10, 16));
    expect(c.camera.visibleBounds.contains(LatLng(_p1.lat, _p1.lon)), isTrue);
  });

  testWidgets('zero punti: nessuna mappa', (t) async {
    await _monta(t, [_s('a'), _s('b')]);
    expect(find.byType(FlutterMap), findsNothing);
    expect(find.text('© OpenStreetMap contributors'), findsNothing);
  });

  testWidgets('dopo un adattamento tappe e numeri si aggiornano', (t) async {
    final c = MapController();
    Future<void> pompa(List<ItineraryStop> tappe) => t.pumpWidget(
          MaterialApp(
            theme: buildAppTheme(),
            home: Scaffold(
              body: MappaItinerario(tappe: tappe, tileProvider: _TileKo(), controller: c),
            ),
          ),
        );
    await pompa(_quattro);
    await t.pump(const Duration(milliseconds: 200));
    expect(_numeri(t), [1, 2, 4]);
    await pompa([_s('a', p: _p1), _s('nuova', p: _p4)]);
    await t.pump(const Duration(milliseconds: 200));
    await t.pump(const Duration(milliseconds: 200));
    expect(_numeri(t), [1, 2]);
    expect(t.takeException(), isNull);
  });

  testWidgets('schermata a 390x844 con la mappa: nessun overflow ne\' scorrimento orizzontale', (t) async {
    t.view.physicalSize = const Size(390, 844);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    final it = Itinerary(personId: 'p', stops: _quattro, generatedAt: DateTime.utc(2026, 12, 12, 9));
    final client = BffClient(
      baseUrl: Uri.parse('http://test'),
      httpClient: MockClient(
        (_) async => http.Response(
          jsonEncode(it.toJson()),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'},
        ),
      ),
    );
    await t.pumpWidget(
      MaterialApp(
        theme: buildAppTheme(),
        home: ItineraryScreen(
          bffClient: client,
          personId: 'p',
          profile: const EmotionalProfile(
            curiosita: 0.5,
            contemplazione: 0.5,
            arte: 0.5,
            conBambini: false,
            tempoDisponibileMin: 240,
          ),
          tileProvider: _TileKo(),
        ),
      ),
    );
    await t.pumpAndSettle();
    expect(t.takeException(), isNull);
    expect(find.byType(FlutterMap), findsOneWidget);
    expect(t.getSize(find.byType(FlutterMap)).width, lessThanOrEqualTo(390));
    for (final s in t.widgetList<Scrollable>(find.byType(Scrollable))) {
      expect(s.axisDirection, anyOf(AxisDirection.down, AxisDirection.up));
    }
  });
}
