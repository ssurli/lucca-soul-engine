// Compito 4: mappa bassa, linea puntinata, dicitura, tocco sul segnaposto che
// apre e porta in vista la tappa. Nessuna rete: tile finti.
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/models/emotional_profile.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/theme/app_theme.dart';
import 'package:lucca_soul_app/theme/tokens.dart';
import 'package:lucca_soul_app/widgets/mappa_itinerario.dart';

class _TileKo extends TileProvider {
  @override
  ImageProvider getImage(TileCoordinates coordinates, TileLayer options) =>
      MemoryImage(Uint8List(0));
}

const _pA = Punto(lat: 43.8429, lon: 10.5027);
const _pB = Punto(lat: 43.8465, lon: 10.5071);
const _pC = Punto(lat: 43.8390, lon: 10.5120);

ItineraryStop _s(int n, {Punto? p}) => ItineraryStop(
      experienceId: 'e$n',
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 30,
      reason: 'motivo $n',
      titolo: 'Titolo $n',
      puntoArrivo: p,
    );

Future<void> _schermata(
  WidgetTester t,
  List<ItineraryStop> tappe, {
  Size size = const Size(390, 600),
  List<String> lingue = const ['it'],
}) async {
  t.view.physicalSize = size;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final it = Itinerary(personId: 'p', stops: tappe, generatedAt: DateTime.utc(2026, 12, 12, 9));
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
        profile: EmotionalProfile(
          curiosita: 0.5,
          contemplazione: 0.5,
          arte: 0.5,
          conBambini: false,
          tempoDisponibileMin: 240,
          lingue: lingue,
        ),
        tileProvider: _TileKo(),
      ),
    ),
  );
  await t.pumpAndSettle();
}

Future<void> _soloMappa(
  WidgetTester t, {
  String dicitura = "Tocca un numero per aprire la tappa. La linea indica l'ordine, non il percorso.",
  ValueChanged<int>? onSegnaposto,
  Size size = const Size(390, 844),
}) async {
  t.view.physicalSize = size;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(
    MaterialApp(
      theme: buildAppTheme(),
      home: Scaffold(
        body: MappaItinerario(
          tappe: [_s(1, p: _pA), _s(2, p: _pB), _s(3, p: _pC)],
          tileProvider: _TileKo(),
          dicitura: dicitura,
          onSegnaposto: onSegnaposto,
        ),
      ),
    ),
  );
  await t.pump(const Duration(milliseconds: 200));
}

Finder _segnaposto(int n) => find.byWidgetPredicate((w) => w is Segnaposto && w.numero == n);

List<bool> _stati(WidgetTester t) =>
    [for (final c in t.widgetList<StopCard>(find.byType(StopCard))) c.aperta ?? false];

void main() {
  test('altezza mappa 168', () => expect(kAltezzaMappa, 168));

  testWidgets('altezza reale della mappa 168', (t) async {
    await _soloMappa(t);
    expect(t.getSize(find.byType(FlutterMap)).height, 168);
  });

  testWidgets('polilinea puntinata, colore e spessore invariati', (t) async {
    await _soloMappa(t);
    final l = t.widget<PolylineLayer>(find.byType(PolylineLayer)).polylines.single;
    expect(l.pattern, const StrokePattern.dotted());
    expect(l.strokeWidth, 3);
    expect(l.color, Tk.accento);
  });

  for (final (lingue, testo) in [
    (['it'], "Tocca un numero per aprire la tappa. La linea indica l'ordine, non il percorso."),
    (['en'], 'Tap a number to open the stop. The line shows the order, not the route.'),
  ]) {
    testWidgets('dicitura in ${lingue.first}: in alto a sinistra, senza toccare l attribuzione', (t) async {
      await _schermata(t, [_s(1, p: _pA), _s(2, p: _pB)], lingue: lingue);
      final d = find.text(testo);
      expect(d, findsOneWidget);
      final attr = find.text(kAttribuzioneOsm);
      expect(attr, findsOneWidget);
      final mappa = t.getRect(find.byType(FlutterMap));
      final rd = t.getRect(d);
      final ra = t.getRect(attr);
      // sotto la mappa, allineata al suo bordo sinistro, fuori dal riquadro
      expect(rd.top, greaterThanOrEqualTo(mappa.bottom));
      expect((rd.left - mappa.left).abs(), lessThan(1));
      expect(rd.overlaps(mappa), isFalse);
      expect(mappa.contains(ra.bottomRight), isTrue); // attribuzione dentro la mappa
      final st = t.widget<Text>(d).style!;
      expect(st.fontSize, 12);
      expect(st.fontWeight, FontWeight.w700);
      expect(rapportoContrasto(st.color!, Tk.cardSfondo), greaterThanOrEqualTo(4.5));
    });
  }

  testWidgets('dicitura e attribuzione non si sovrappongono a 360 px', (t) async {
    await _soloMappa(t, dicitura: 'Tap a number to open the stop. The line shows the order, not the route.', size: const Size(360, 640));
    final rd = t.getRect(find.text('Tap a number to open the stop. The line shows the order, not the route.'));
    final ra = t.getRect(find.text(kAttribuzioneOsm));
    expect(rd.overlaps(ra), isFalse);
    expect(rd.right, lessThanOrEqualTo(360));
    expect(t.takeException(), isNull);
  });

  testWidgets('area del tocco del segnaposto >= 44x44, pulsante con etichetta', (t) async {
    final h = t.ensureSemantics();
    await _soloMappa(t, onSegnaposto: (_) {});
    for (final n in [1, 2, 3]) {
      final r = t.getRect(_segnaposto(n));
      expect(r.width, greaterThanOrEqualTo(Tk.areaMinima));
      expect(r.height, greaterThanOrEqualTo(Tk.areaMinima));
    }
    expect(t.getSemantics(_segnaposto(1)).label, contains('Tappa 1'));
    h.dispose();
  });

  testWidgets('tocco al bordo dell area 44 (fuori dal cerchio 32) arriva al segnaposto', (t) async {
    final visti = <int>[];
    await _soloMappa(t, onSegnaposto: visti.add);
    final r = t.getRect(_segnaposto(2));
    await t.tapAt(r.topLeft + const Offset(3, 3));
    await t.pump(const Duration(milliseconds: 400));
    expect(visti, [2]);
  });

  testWidgets('tocco sul segnaposto N apre la tappa N (lista corta)', (t) async {
    await _schermata(t, [_s(1, p: _pA), _s(2, p: _pB), _s(3, p: _pC)], size: const Size(390, 844));
    expect(_stati(t), [false, false, false]);
    await t.tap(_segnaposto(2));
    await t.pumpAndSettle();
    expect(_stati(t), [false, true, false]);
    expect(find.text('motivo 2'), findsOneWidget);
  });

  testWidgets('lista lunga: la tappa fuori vista viene aperta e portata nel viewport', (t) async {
    final tappe = [
      _s(1, p: _pA),
      for (var n = 2; n <= 29; n++) _s(n),
      _s(30, p: _pC),
    ];
    await _schermata(t, tappe, size: const Size(390, 600));
    // la tappa 30 non e' costruita: sta fuori dalla cache della lista
    expect(find.text('Titolo 30'), findsNothing);
    await t.tap(_segnaposto(30));
    await t.pumpAndSettle();
    expect(t.takeException(), isNull);
    final card = find.ancestor(of: find.text('Titolo 30'), matching: find.byType(StopCard));
    expect(card, findsOneWidget);
    expect(t.widget<StopCard>(card).aperta, isTrue);
    expect(find.text('motivo 30'), findsOneWidget);
    final vista = t.getRect(find.byType(RefreshIndicator));
    final rc = t.getRect(card);
    expect(rc.top, greaterThanOrEqualTo(vista.top - 0.5));
    expect(rc.bottom, lessThanOrEqualTo(vista.bottom + 0.5));
  });

  testWidgets('nessun altro gesto: il tocco sulla mappa fuori dai segnaposti non apre nulla', (t) async {
    await _schermata(t, [_s(1, p: _pA), _s(2, p: _pB), _s(3, p: _pC)], size: const Size(390, 844));
    final mappa = t.getRect(find.byType(FlutterMap));
    final seg = [for (final n in [1, 2, 3]) t.getRect(_segnaposto(n))];
    Offset? libero;
    for (var x = mappa.left + 20; x < mappa.right - 20 && libero == null; x += 10) {
      for (var y = mappa.top + 50; y < mappa.bottom - 30; y += 10) {
        final o = Offset(x, y);
        if (!seg.any((r) => r.inflate(4).contains(o))) {
          libero = o;
          break;
        }
      }
    }
    expect(libero, isNotNull);
    await t.tapAt(libero!);
    await t.pump(const Duration(milliseconds: 400)); // attesa del doppio tocco della mappa
    await t.pumpAndSettle();
    expect(_stati(t), [false, false, false]);
  });
}
