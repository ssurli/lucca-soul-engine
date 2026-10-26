// Gate indipendente sulla mappa (compito 4). Nessuna rete: provider finto che
// FALLISCE. Ogni test e' scritto per poter fallire.
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
import 'package:lucca_soul_app/theme/tokens.dart';
import 'package:lucca_soul_app/util/mappa_tappe.dart';
import 'package:lucca_soul_app/widgets/mappa_itinerario.dart';

class _TileKo extends TileProvider {
  int richieste = 0;
  @override
  ImageProvider getImage(TileCoordinates coordinates, TileLayer options) {
    richieste++;
    return MemoryImage(Uint8List(0));
  }
}

ItineraryStop _s(String id, {Punto? p}) => ItineraryStop(
      experienceId: id,
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 30,
      reason: 'm',
      titolo: 'Titolo $id',
      puntoArrivo: p,
    );

const _p1 = Punto(lat: 43.8429, lon: 10.5027);
const _p2 = Punto(lat: 43.8465, lon: 10.5071);
const _p4 = Punto(lat: 43.8390, lon: 10.5120);
const _p5 = Punto(lat: 43.8500, lon: 10.4900);
const _json = {'content-type': 'application/json; charset=utf-8'};

const _profilo = EmotionalProfile(
  curiosita: 0.5,
  contemplazione: 0.5,
  arte: 0.5,
  conBambini: false,
  tempoDisponibileMin: 240,
);

LatLng _ll(Punto p) => LatLng(p.lat, p.lon);

Future<MapController> _monta(WidgetTester t, List<ItineraryStop> tappe, {_TileKo? tp}) async {
  t.view.physicalSize = const Size(390, 844);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final c = MapController();
  await t.pumpWidget(MaterialApp(
    theme: buildAppTheme(),
    home: Scaffold(body: MappaItinerario(tappe: tappe, tileProvider: tp ?? _TileKo(), controller: c)),
  ),);
  await t.pump();
  await t.pump(const Duration(milliseconds: 200));
  return c;
}

Future<void> _schermata(
  WidgetTester t,
  List<ItineraryStop> originali,
  List<ItineraryStop> adattate, {
  Size size = const Size(390, 844),
}) async {
  t.view.physicalSize = size;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  Itinerary it(List<ItineraryStop> s) =>
      Itinerary(personId: 'p', stops: s, generatedAt: DateTime.utc(2026, 12, 12, 9));
  final client = BffClient(
    baseUrl: Uri.parse('http://test'),
    httpClient: MockClient((req) async {
      final r = req.url.path.endsWith('/adapt') ? adattate : originali;
      return http.Response(jsonEncode(it(r).toJson()), 200, headers: _json);
    }),
  );
  await t.pumpWidget(MaterialApp(
    theme: buildAppTheme(),
    home: ItineraryScreen(
      bffClient: client,
      personId: 'p',
      profile: _profilo,
      tileProvider: _TileKo(),
    ),
  ),);
  await t.pumpAndSettle();
}

void main() {
  final quattro = [_s('a', p: _p1), _s('b', p: _p2), _s('bottega'), _s('d', p: _p4)];

  group('1. segnaposti', () {
    test('tappe in coda o senza punto non producono segnaposto; numerazione = posizione', () {
      final tappe = [_s('a', p: _p1), _s('b'), _s('c'), _s('d', p: _p2), _s('coda-evento')];
      final s = segnapostiMappa(tappe);
      expect(s.map((e) => e.numero), [1, 4]);
      expect(s.map((e) => e.punto), [_ll(_p1), _ll(_p2)]);
    });

    testWidgets('un segnaposto per tappa con punto, con etichetta di accessibilita col numero', (t) async {
      final h = t.ensureSemantics();
      await _monta(t, [...quattro, _s('coda')]);
      final seg = find.byType(Segnaposto);
      expect(seg, findsNWidgets(3));
      // flutter_map fonde i nodi semantici dei marker nello stesso nodo:
      // l'etichetta fusa deve contenere le tre etichette, in ordine, e nessuna per la tappa 3.
      final righe = t.getSemantics(seg.first).label.split('\n');
      expect(righe.where((r) => r.startsWith('Tappa')).toList(), ['Tappa 1', 'Tappa 2', 'Tappa 4']);
      h.dispose();
    });
  });

  group('2. linea dritta', () {
    testWidgets('punti della polilinea nell ordine delle tappe', (t) async {
      await _monta(t, quattro);
      final l = t.widget<PolylineLayer>(find.byType(PolylineLayer)).polylines;
      expect(l, hasLength(1));
      expect(l.single.points, [_ll(_p1), _ll(_p2), _ll(_p4)]);
    });

    testWidgets('ordine rovesciato in ingresso: la polilinea segue le tappe, non una ordinatura', (t) async {
      await _monta(t, [_s('x', p: _p4), _s('y', p: _p1), _s('z', p: _p2)]);
      final pts = t.widget<PolylineLayer>(find.byType(PolylineLayer)).polylines.single.points;
      expect(pts, [_ll(_p4), _ll(_p1), _ll(_p2)]);
    });
  });

  group('3-4. inquadratura e strati che falliscono', () {
    testWidgets('inquadratura comprende tutti i segnaposti, anche sparsi', (t) async {
      final c = await _monta(t, [...quattro, _s('e', p: _p5)]);
      for (final p in [_p1, _p2, _p4, _p5]) {
        expect(c.camera.visibleBounds.contains(_ll(p)), isTrue, reason: '$p');
      }
    });

    testWidgets('provider che fallisce: nessuna eccezione, segnaposti e linee presenti', (t) async {
      final tp = _TileKo();
      await _monta(t, quattro, tp: tp);
      await t.pump(const Duration(seconds: 1));
      expect(t.takeException(), isNull);
      expect(find.byType(Segnaposto), findsNWidgets(3));
      expect(find.byType(PolylineLayer), findsOneWidget);
      expect(tp.richieste, greaterThan(0)); // gli strati sono stati davvero richiesti (e sono falliti)
    });
  });

  group('5. attribuzione', () {
    testWidgets('testo visibile (non in un icona) e contrasto >= 4,5 nel caso peggiore', (t) async {
      await _monta(t, quattro);
      final f = find.text('© OpenStreetMap contributors');
      expect(f, findsOneWidget);
      final mappa = t.getRect(find.byType(FlutterMap));
      expect(mappa.contains(t.getCenter(f)), isTrue);
      final fg = t.widget<Text>(f).style!.color!;
      final cont = t.widget<Container>(find.ancestor(of: f, matching: find.byType(Container)).first);
      final bg = (cont.color ?? (cont.decoration as BoxDecoration).color)!;
      // sfondo semitrasparente su tile qualunque: peggior caso nero, bianco, neutro
      for (final base in [Colors.black, Colors.white, Tk.avviso]) {
        final a = bg.a;
        final mix = Color.from(
          alpha: 1,
          red: bg.r * a + base.r * (1 - a),
          green: bg.g * a + base.g * (1 - a),
          blue: bg.b * a + base.b * (1 - a),
        );
        expect(rapportoContrasto(fg, mix), greaterThanOrEqualTo(4.5), reason: 'su base $base');
      }
    });
  });

  group('6. regole OSM', () {
    testWidgets('URL, user agent, nessun prefetch', (t) async {
      await _monta(t, quattro);
      final l = t.widget<TileLayer>(find.byType(TileLayer));
      expect(l.urlTemplate, 'https://tile.openstreetmap.org/{z}/{x}/{y}.png');
      // TileLayer scrive lo user agent negli header del provider
      expect(l.tileProvider.headers['User-Agent'], 'flutter_map (lucca_soul_app)');
      expect(l.panBuffer, 0);
    });
  });

  group('7. posizione e layout nella schermata', () {
    testWidgets('mappa in alto, prima delle card; 390x844 senza overflow ne scroll orizzontale', (t) async {
      await _schermata(t, quattro, quattro);
      expect(t.takeException(), isNull);
      final mappa = find.byType(FlutterMap);
      expect(mappa, findsOneWidget);
      final card = find.byType(StopCard).first;
      expect(t.getBottomLeft(mappa).dy, lessThanOrEqualTo(t.getTopLeft(card).dy));
      // in alto: nella prima meta dello schermo
      expect(t.getTopLeft(mappa).dy, lessThan(300));
      final r = t.getRect(mappa);
      expect(r.left, greaterThanOrEqualTo(0));
      expect(r.right, lessThanOrEqualTo(390));
      for (final s in t.widgetList<Scrollable>(find.byType(Scrollable))) {
        expect(s.axisDirection, anyOf(AxisDirection.down, AxisDirection.up));
      }
    });

    testWidgets('schermo largo: la mappa resta nella colonna <= 600 px', (t) async {
      await _schermata(t, quattro, quattro, size: const Size(1400, 900));
      expect(t.takeException(), isNull);
      expect(t.getSize(find.byType(FlutterMap)).width, lessThanOrEqualTo(600));
      final r = t.getRect(find.byType(FlutterMap));
      expect((r.center.dx - 700).abs(), lessThan(2)); // centrata come le card
    });
  });

  group('8. dopo un adattamento', () {
    testWidgets('la mappa mostra numeri e punti nuovi (schermata, adattamento reale)', (t) async {
      final nuove = [_s('a', p: _p1), _s('n', p: _p5), _s('m', p: _p4)];
      await _schermata(t, quattro, nuove);
      expect(t.widgetList<Segnaposto>(find.byType(Segnaposto)).map((s) => s.numero), [1, 2, 4]);
      await t.tap(find.text('Piove'));
      await t.pumpAndSettle();
      expect(t.takeException(), isNull);
      expect(t.widgetList<Segnaposto>(find.byType(Segnaposto)).map((s) => s.numero), [1, 2, 3]);
      final pts = t.widget<PolylineLayer>(find.byType(PolylineLayer)).polylines.single.points;
      expect(pts, [_ll(_p1), _ll(_p5), _ll(_p4)]);
    });

    testWidgets('reinquadratura sui punti nuovi', (t) async {
      final c = MapController();
      Future<void> pompa(List<ItineraryStop> tappe) => t.pumpWidget(MaterialApp(
            theme: buildAppTheme(),
            home: Scaffold(body: MappaItinerario(tappe: tappe, tileProvider: _TileKo(), controller: c)),
          ),);
      t.view.physicalSize = const Size(390, 844);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      await pompa([_s('a', p: _p1), _s('b', p: _p2)]);
      await t.pump(const Duration(milliseconds: 200));
      const lontano = Punto(lat: 43.9100, lon: 10.6000);
      await pompa([_s('a', p: _p1), _s('n', p: lontano)]);
      await t.pump(const Duration(milliseconds: 200));
      await t.pump(const Duration(milliseconds: 200));
      expect(c.camera.visibleBounds.contains(_ll(lontano)), isTrue);
      expect(c.camera.visibleBounds.contains(_ll(_p1)), isTrue);
    });
  });
}
