// Mappa nella schermata: un dito scorre la pagina, due dita muovono la mappa,
// il pulsante «Tutte le tappe» riporta all'inquadratura iniziale.
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
import 'package:lucca_soul_app/util/segnaposti_separati.dart';
import 'package:lucca_soul_app/widgets/mappa_itinerario.dart';
import 'package:lucca_soul_app/widgets/segnaposto_mura.dart';

import 'segnaposto_prove.dart';

class _TileKo extends TileProvider {
  @override
  ImageProvider getImage(TileCoordinates coordinates, TileLayer options) =>
      MemoryImage(Uint8List(0));
}

const _pA = Punto(lat: 43.8429, lon: 10.5027);
const _pB = Punto(lat: 43.8465, lon: 10.5071);
const _pC = Punto(lat: 43.8390, lon: 10.5120);

LatLng _ll(Punto p) => LatLng(p.lat, p.lon);

ItineraryStop _s(int n, {Punto? p}) => ItineraryStop(
      experienceId: 'e$n',
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 30,
      reason: 'motivo $n',
      titolo: 'Titolo $n',
      puntoArrivo: p,
    );

Finder _segnaposto(int n) =>
    find.byWidgetPredicate((w) => w is Segnaposto && w.numero == n);
Finder _pulsante() => find.byKey(kChiavePulsanteTutteLeTappe);
Finder _guide() => find
    .byWidgetPredicate((w) => w is CustomPaint && w.painter is GuidePainter);

Future<void> _schermata(
  WidgetTester t,
  List<ItineraryStop> tappe, {
  String lingua = 'it',
}) async {
  t.view.physicalSize = const Size(390, 700);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final it = Itinerary(
    personId: 'p',
    stops: tappe,
    generatedAt: DateTime.utc(2026, 12, 12, 9),
  );
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
          lingue: [lingua],
        ),
        tileProvider: _TileKo(),
        sagomaSegnaposto: Future.value(sagomaMura()),
      ),
    ),
  );
  await t.pumpAndSettle();
}

/// Pagina lunga: 3 tappe con punto e altre 9 senza.
List<ItineraryStop> _tappeLunghe() => [
      _s(1, p: _pA),
      _s(2, p: _pB),
      _s(3, p: _pC),
      for (var n = 4; n <= 12; n++) _s(n),
    ];

MapCamera _camera(WidgetTester t) =>
    MapCamera.of(t.element(find.byType(Segnaposto).first));

double _scroll(WidgetTester t) => t
    .state<ScrollableState>(
      find
          .descendant(
            of: find.byType(ListView),
            matching: find.byType(Scrollable),
          )
          .first,
    )
    .position
    .pixels;

Rect _mappa(WidgetTester t) => t.getRect(find.byType(FlutterMap));

/// Punto della mappa che non cade su un segnaposto, ne' sul pulsante, ne'
/// sull'attribuzione.
Offset _libero(WidgetTester t) {
  final m = _mappa(t);
  final seg = [
    for (final e in find.byType(Segnaposto).evaluate())
      t.getRect(find.byWidget(e.widget)).inflate(6),
  ];
  for (var y = m.top + 60; y < m.bottom - 40; y += 8) {
    for (var x = m.left + 30; x < m.right - 120; x += 8) {
      final o = Offset(x, y);
      if (!seg.any((r) => r.contains(o))) return o;
    }
  }
  throw StateError('nessun punto libero');
}

bool _uguale(MapCamera a, MapCamera b) =>
    (a.zoom - b.zoom).abs() < 1e-9 &&
    (a.center.latitude - b.center.latitude).abs() < 1e-9 &&
    (a.center.longitude - b.center.longitude).abs() < 1e-9;

Future<void> _dueDitaMuovi(
  WidgetTester t,
  Offset da,
  Offset passo, {
  int passi = 12,
}) async {
  final g1 = await t.startGesture(da);
  final g2 = await t.startGesture(da + const Offset(70, 0));
  await t.pump(const Duration(milliseconds: 20));
  for (var i = 0; i < passi; i++) {
    await g1.moveBy(passo);
    await g2.moveBy(passo);
    await t.pump(const Duration(milliseconds: 16));
  }
  expect(_scroll(t), 0, reason: 'con due dita la pagina non scorre');
  await g1.up();
  await g2.up();
  await t.pump(const Duration(milliseconds: 100));
}

Future<void> _doppioTocco(WidgetTester t, Offset o) async {
  await t.tapAt(o);
  await t.pump(const Duration(milliseconds: 60));
  await t.tapAt(o);
  await t.pumpAndSettle();
}

void main() {
  _provaAngoloAltoDestra();
  testWidgets(
      'un dito: il trascinamento verticale sulla mappa scorre la pagina e non muove la camera',
      (t) async {
    await _schermata(t, _tappeLunghe());
    final prima = _camera(t);
    expect(_scroll(t), 0);
    final o = _libero(t);
    final g = await t.startGesture(o);
    for (var i = 0; i < 10; i++) {
      await g.moveBy(const Offset(0, -12));
      await t.pump(const Duration(milliseconds: 16));
    }
    await g.up();
    await t.pumpAndSettle();
    expect(_scroll(t), greaterThan(40), reason: 'la pagina deve scorrere');
    // la mappa e' salita insieme alla pagina: confronto per camera, non per rect
    expect(
      _uguale(_camera(t), prima),
      isTrue,
      reason: 'la camera non deve muoversi con un dito',
    );
    expect(_pulsante(), findsNothing);
    expect(t.takeException(), isNull);
  });

  testWidgets(
      'due dita: spostamento verticale e orizzontale muovono la camera, la pagina non scorre; poi un dito scorre di nuovo',
      (t) async {
    await _schermata(t, _tappeLunghe());
    final iniziale = _camera(t);
    final m = _mappa(t);
    final da = Offset(m.left + 90, m.top + 110);

    await _dueDitaMuovi(t, da, const Offset(0, 8));
    final dopoV = _camera(t);
    expect(
      _uguale(dopoV, iniziale),
      isFalse,
      reason: 'lo spostamento verticale a due dita muove la camera',
    );
    expect(
      (dopoV.center.latitude - iniziale.center.latitude).abs(),
      greaterThan(1e-6),
    );

    await _dueDitaMuovi(t, da, const Offset(10, 0));
    final dopoO = _camera(t);
    expect(
      (dopoO.center.longitude - dopoV.center.longitude).abs(),
      greaterThan(1e-6),
      reason: 'lo spostamento orizzontale muove la camera',
    );

    // dita alzate: la pagina torna a scorrere con un dito
    final g = await t.startGesture(Offset(m.left + 20, m.bottom + 30));
    for (var i = 0; i < 8; i++) {
      await g.moveBy(const Offset(0, -15));
      await t.pump(const Duration(milliseconds: 16));
    }
    await g.up();
    await t.pumpAndSettle();
    expect(_scroll(t), greaterThan(40));
    expect(t.takeException(), isNull);
  });

  testWidgets(
      'pulsante «Tutte le tappe»: assente all inizio, compare dopo zoom e dopo spostamento, riporta la vista iniziale e sparisce',
      (t) async {
    await _schermata(t, _tappeLunghe());
    final iniziale = _camera(t);
    expect(_pulsante(), findsNothing);

    // dopo uno zoom (doppio tocco)
    await _doppioTocco(t, _libero(t));
    expect(_camera(t).zoom, greaterThan(iniziale.zoom + 0.05));
    expect(_pulsante(), findsOneWidget);

    // riporta all'inquadratura iniziale e sparisce
    await t.tap(_pulsante());
    await t.pumpAndSettle();
    final dopo = _camera(t);
    expect((dopo.zoom - iniziale.zoom).abs(), lessThan(0.05));
    final sp = (dopo.latLngToScreenOffset(iniziale.center) -
            dopo.size.center(Offset.zero))
        .distance;
    expect(sp, lessThan(2));
    expect(_pulsante(), findsNothing);

    // dopo uno spostamento a due dita
    final m = _mappa(t);
    await _dueDitaMuovi(
      t,
      Offset(m.left + 90, m.top + 110),
      const Offset(10, 0),
    );
    expect(_pulsante(), findsOneWidget);
    await t.tap(_pulsante());
    await t.pumpAndSettle();
    expect(_pulsante(), findsNothing);
    expect((_camera(t).zoom - iniziale.zoom).abs(), lessThan(0.05));
    expect(t.takeException(), isNull);
  });

  for (final (lingua, testo) in [
    ('it', 'Tutte le tappe'),
    ('en', 'All stops'),
  ]) {
    testWidgets(
        'pulsante [$lingua]: etichetta, area, semantica, contrasto, non tocca l attribuzione',
        (t) async {
      final h = t.ensureSemantics();
      await _schermata(t, _tappeLunghe(), lingua: lingua);
      await _doppioTocco(t, _libero(t));
      final p = _pulsante();
      expect(p, findsOneWidget);
      expect(
        find.descendant(of: p, matching: find.text(testo)),
        findsOneWidget,
      );
      final r = t.getRect(p);
      expect(r.width, greaterThanOrEqualTo(Tk.areaMinima));
      expect(r.height, greaterThanOrEqualTo(Tk.areaMinima));
      final sem = t.getSemantics(p);
      expect(sem.label, testo);
      expect(sem.flagsCollection.isButton, isTrue);
      // non interseca l'attribuzione OSM
      final attr = t.getRect(
        find
            .ancestor(
              of: find.text(kAttribuzioneOsm),
              matching: find.byType(Container),
            )
            .first,
      );
      expect(r.overlaps(attr), isFalse, reason: '$r contro $attr');
      // dentro la mappa, in alto a destra
      final m = _mappa(t);
      expect(m.inflate(0.5).contains(r.topLeft), isTrue);
      expect(r.right, lessThanOrEqualTo(m.right + 0.5));
      // contrasto testo / sfondo
      final stile = t
          .widget<Text>(find.descendant(of: p, matching: find.text(testo)))
          .style!;
      expect(
        rapportoContrasto(stile.color!, Tk.cardSfondo),
        greaterThanOrEqualTo(4.5),
      );
      expect(stile.color, Tk.accento);
      h.dispose();
    });
  }

  testWidgets(
      'dopo zoom e spostamento i segnaposti restano separati, dentro la mappa, e il GuidePainter coincide',
      (t) async {
    // due tappe nello stesso punto (separazione) + una distante
    await _schermata(t, [
      _s(1, p: _pA),
      _s(2, p: _pA),
      _s(3, p: _pB),
      for (var n = 4; n <= 10; n++) _s(n),
    ]);
    final sg = sagomaMura();

    void controlla(String quando) {
      final cam = _camera(t);
      final m = _mappa(t);
      final g = t.widget<CustomPaint>(_guide()).painter! as GuidePainter;
      final punte = <Offset>[];
      for (var n = 1; n <= 3; n++) {
        final r = t.getRect(_segnaposto(n));
        expect(
          m.inflate(0.5).contains(r.topLeft) &&
              m.inflate(0.5).contains(r.bottomRight),
          isTrue,
          reason: '$quando: riquadro $n fuori dalla mappa $r $m',
        );
        final punta =
            r.topLeft - m.topLeft + sg.puntaNelRiquadro(kLarghezzaSegnaposto);
        punte.add(punta);
        // punte del painter = punte disegnate; veri = luoghi della camera corrente
        expect(
          (g.punte[n - 1] - punta).distance,
          lessThanOrEqualTo(1),
          reason: '$quando: punta $n',
        );
        final vero = cam.latLngToScreenOffset(_ll([_pA, _pA, _pB][n - 1]));
        expect(
          (g.veri[n - 1] - vero).distance,
          lessThanOrEqualTo(1),
          reason: '$quando: luogo vero $n',
        );
      }
      for (var i = 0; i < 3; i++) {
        for (var j = i + 1; j < 3; j++) {
          expect(
            (punte[i] - punte[j]).distance,
            greaterThanOrEqualTo(kLarghezzaSegnaposto - 0.01),
            reason: '$quando: punte $i e $j',
          );
        }
      }
    }

    controlla('iniziale');
    await _doppioTocco(t, _libero(t));
    expect(_pulsante(), findsOneWidget);
    controlla('dopo lo zoom');
    final m = _mappa(t);
    await _dueDitaMuovi(
      t,
      Offset(m.left + 90, m.top + 110),
      const Offset(6, 0),
      passi: 14,
    );
    controlla('dopo lo spostamento');
    expect(t.takeException(), isNull);
  });
}

// Angolo in alto a destra con il pulsante «Tutte le tappe» visibile: nessun
// segnaposto sotto il pulsante, tutti dentro la mappa e sopra l'attribuzione.
void _provaAngoloAltoDestra() {
  Rect attribuzione(WidgetTester t) => t.getRect(
        find
            .ancestor(
              of: find.text(kAttribuzioneOsm),
              matching: find.byType(Container),
            )
            .first,
      );

  // Monta la mappa con [tappe] e porta il punto [p] a (dx, dy) locali.
  Future<MapController> monta(
    WidgetTester t,
    List<ItineraryStop> tappe,
    bool conSagoma,
    List<int> visti,
    Punto p,
    double dx,
    double dy,
  ) async {
    t.view.physicalSize = const Size(390, 700);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    final c = MapController();
    await t.pumpWidget(
      MaterialApp(
        theme: buildAppTheme(),
        home: Scaffold(
          body: MappaItinerario(
            tappe: tappe,
            tileProvider: _TileKo(),
            controller: c,
            onSegnaposto: visti.add,
            sagoma: conSagoma ? Future.value(sagomaMura()) : Future.value(null),
          ),
        ),
      ),
    );
    await t.pump(const Duration(milliseconds: 200));
    await t.pump(const Duration(milliseconds: 200));
    c.move(_ll(p), 16);
    await t.pump(const Duration(milliseconds: 200));
    final cam = c.camera;
    final w = cam.size.width;
    final h = cam.size.height;
    c.move(
      cam.screenOffsetToLatLng(
        Offset(w / 2 + (w / 2 - dx), h / 2 + (h / 2 - dy)),
      ),
      16,
    );
    await t.pump(const Duration(milliseconds: 200));
    return c;
  }

  void controllaFuoriDalPulsante(WidgetTester t, List<int> numeri) {
    final b = t.getRect(_pulsante());
    final m = t.getRect(find.byType(FlutterMap));
    final attr = attribuzione(t);
    for (final n in numeri) {
      final r = t.getRect(_segnaposto(n));
      expect(
        r.overlaps(b),
        isFalse,
        reason: 'segnaposto $n sotto il pulsante: $r $b',
      );
      expect(
        m.inflate(0.5).contains(r.topLeft) &&
            m.inflate(0.5).contains(r.bottomRight),
        isTrue,
        reason: 'segnaposto $n fuori dalla mappa: $r $m',
      );
      expect(
        r.overlaps(attr),
        isFalse,
        reason: 'segnaposto $n sull attribuzione',
      );
    }
  }

  for (final conSagoma in [true, false]) {
    final nome = conSagoma ? 'sagoma' : 'cerchio';

    testWidgets(
        'angolo in alto a destra [$nome]: il segnaposto sta fuori dal pulsante, il tocco apre la tappa, il pulsante resta',
        (t) async {
      final visti = <int>[];
      final c = await monta(
        t,
        [_s(1, p: _pA), _s(2, p: _pB)],
        conSagoma,
        visti,
        _pA,
        388,
        2,
      );
      expect(_pulsante(), findsOneWidget);
      controllaFuoriDalPulsante(t, [1]);
      await t.tapAt(t.getCenter(_segnaposto(1)));
      await t.pump(const Duration(milliseconds: 400));
      expect(visti, [1], reason: 'il tocco apre la tappa 1');
      expect(_pulsante(), findsOneWidget, reason: 'il pulsante resta visibile');
      if (conSagoma) {
        // la linea di richiamo parte dalla punta SPOSTATA e arriva al luogo vero
        final g = t.widget<CustomPaint>(_guide()).painter! as GuidePainter;
        final cam = c.camera;
        final origine = t.getRect(find.byType(FlutterMap)).topLeft;
        expect(
          (g.veri[0] - cam.latLngToScreenOffset(_ll(_pA))).distance,
          lessThanOrEqualTo(1),
        );
        expect(
          (g.punte[0] - g.veri[0]).distance,
          greaterThan(2),
          reason: 'la punta e stata spostata: serve il richiamo',
        );
        final punta = t.getRect(_segnaposto(1)).topLeft +
            sagomaMura().puntaNelRiquadro(kLarghezzaSegnaposto);
        expect((punta - origine - g.punte[0]).distance, lessThanOrEqualTo(1));
      }
      expect(t.takeException(), isNull);
    });

    testWidgets(
        'angolo in alto a destra [$nome]: tre tappe nello stesso punto, tutte fuori dal pulsante, separate, dentro la mappa',
        (t) async {
      final visti = <int>[];
      await monta(
        t,
        [_s(1, p: _pA), _s(2, p: _pA), _s(3, p: _pA)],
        conSagoma,
        visti,
        _pA,
        388,
        2,
      );
      expect(_pulsante(), findsOneWidget);
      controllaFuoriDalPulsante(t, [1, 2, 3]);
      final sg = conSagoma ? sagomaMura() : null;
      final punti = [
        for (final n in [1, 2, 3])
          sg == null
              ? t.getCenter(_segnaposto(n))
              : t.getRect(_segnaposto(n)).topLeft +
                  sg.puntaNelRiquadro(kLarghezzaSegnaposto),
      ];
      final soglia = conSagoma ? kLarghezzaSegnaposto : kDiametroSegnaposto;
      for (var i = 0; i < 3; i++) {
        for (var j = i + 1; j < 3; j++) {
          expect(
            (punti[i] - punti[j]).distance,
            greaterThanOrEqualTo(soglia - 0.01),
            reason: 'punte $i e $j',
          );
        }
      }
      for (final n in [1, 2, 3]) {
        visti.clear();
        await t.tapAt(t.getCenter(_segnaposto(n)));
        await t.pump(const Duration(milliseconds: 400));
        expect(visti, [n], reason: 'tocco su $n');
        expect(_pulsante(), findsOneWidget);
      }
      expect(t.takeException(), isNull);
    });
  }
}
