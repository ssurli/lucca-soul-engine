// Segnaposto con la sagoma delle Mura: la punta cade sul luogo, linee di
// richiamo, ripiego sul cerchio se l'asset manca, lettura dell'asset reale.
// La sagoma e' SEMPRE iniettata (mai il bundle) per sapere cosa si prova.
import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/theme/app_theme.dart';
import 'package:lucca_soul_app/theme/tokens.dart';
import 'package:lucca_soul_app/widgets/mappa_itinerario.dart';
import 'package:lucca_soul_app/widgets/segnaposto_mura.dart';
import 'package:lucca_soul_app/widgets/segnaposto_variante.dart';

import 'segnaposto_prove.dart';

class _TileKo extends TileProvider {
  @override
  ImageProvider getImage(TileCoordinates coordinates, TileLayer options) =>
      MemoryImage(Uint8List(0));
}

const _pA = Punto(lat: 43.8429, lon: 10.5027);
const _pB = Punto(lat: 43.8465, lon: 10.5071);

LatLng _ll(Punto p) => LatLng(p.lat, p.lon);

ItineraryStop _s(int n, Punto p) => ItineraryStop(
      experienceId: 'e$n',
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 30,
      reason: 'motivo $n',
      puntoArrivo: p,
    );

Finder _segnaposto(int n) =>
    find.byWidgetPredicate((w) => w is Segnaposto && w.numero == n);

Finder _guide() => find
    .byWidgetPredicate((w) => w is CustomPaint && w.painter is GuidePainter);

Future<MapController> _monta(
  WidgetTester t,
  List<ItineraryStop> tappe,
  Future<SagomaSegnaposto?> sagoma, {
  List<int>? visti,
}) async {
  t.view.physicalSize = const Size(390, 844);
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
          sagoma: sagoma,
          onSegnaposto: visti?.add,
        ),
      ),
    ),
  );
  await t.pump(const Duration(milliseconds: 200));
  // la mappa nasce un frame dopo il caricamento della sagoma: un pump in piu'
  await t.pump(const Duration(milliseconds: 200));
  return c;
}

void main() {
  group('asset reale', () {
    test('mura: parseSagomaSegnaposto: 58 punti di contorno, 22 di traccia',
        () {
      final sg = sagomaDi(VarianteSegnaposto.mura);
      expect(sg.contorno.length, 58);
      expect(sg.traccia.length, 22);
      expect(sg.stile, StileSegnaposto.mura);
    });

    test('mura: geometria: viewBox, punta e dimensione a 48 px', () {
      final sg = sagomaDi(VarianteSegnaposto.mura);
      expect(sg.larghezza, 48);
      expect(sg.viewBox, const Rect.fromLTWH(-17, -14, 34, 32));
      expect(sg.punta, const Offset(-4.9, 17.2));
      final dim = sg.dimensione(sg.larghezza);
      expect(dim.width, 48);
      expect(dim.height, closeTo(45.18, 0.05));
      final pl = sg.puntaLocale(sg.larghezza);
      expect(pl.dx, inInclusiveRange(0, dim.width));
      expect(pl.dy, inInclusiveRange(0, dim.height));
    });

    test(
        'baluardo: geometria: viewBox = riquadro di tocco 44x44, punta in (0,0)',
        () {
      final sg = sagomaDi(VarianteSegnaposto.baluardo);
      expect(sg.stile, StileSegnaposto.baluardo);
      expect(sg.larghezza, 44);
      expect(sg.viewBox, const Rect.fromLTWH(-22, -40, 44, 44));
      expect(sg.punta, Offset.zero);
      expect(sg.punta.dx, 0, reason: 'la punta sta sull asse x=0');
      expect(sg.dimensione(sg.larghezza), const Size(44, 44));
      expect(
        sg.dimensione(sg.larghezza).width,
        greaterThanOrEqualTo(Tk.areaMinima),
      );
      expect(
        sg.dimensione(sg.larghezza).height,
        greaterThanOrEqualTo(Tk.areaMinima),
      );
      // punta locale: centro del bordo basso meno 4 px
      expect(sg.puntaLocale(sg.larghezza), const Offset(22, 40));
      expect(sg.contorno, const [
        Offset(0, 0),
        Offset(18, -22),
        Offset(12, -36),
        Offset(-12, -36),
        Offset(-18, -22),
      ]);
      expect(sg.traccia.length, 5);
      expect(sg.centroNumero.dx, 0);
    });

    test('baluardo: contorno simmetrico rispetto a x=0', () {
      final c = sagomaDi(VarianteSegnaposto.baluardo).contorno;
      for (final q in c) {
        expect(
          c.any(
            (r) => (r.dx + q.dx).abs() < 1e-9 && (r.dy - q.dy).abs() < 1e-9,
          ),
          isTrue,
          reason: 'manca lo specchio di $q',
        );
      }
      final t = sagomaDi(VarianteSegnaposto.baluardo).traccia;
      for (final q in t) {
        expect(
          t.any(
            (r) => (r.dx + q.dx).abs() < 0.01 && (r.dy - q.dy).abs() < 0.01,
          ),
          isTrue,
          reason: 'traccia: manca lo specchio di $q',
        );
      }
    });

    test('ogni contorno sta dentro la propria viewBox', () {
      for (final v in kVarianti) {
        final sg = sagomaDi(v);
        for (final q in [...sg.contorno, sg.punta]) {
          expect(
            sg.viewBox.inflate(0.001).contains(q),
            isTrue,
            reason: '${v.name}: $q',
          );
        }
      }
    });
  });

  test('varianteDaTesto: mura, baluardo, vuoto e sconosciuto', () {
    expect(varianteDaTesto('mura'), VarianteSegnaposto.mura);
    expect(varianteDaTesto('baluardo'), VarianteSegnaposto.baluardo);
    expect(varianteDaTesto(''), VarianteSegnaposto.baluardo);
    expect(varianteDaTesto('xyz'), VarianteSegnaposto.baluardo);
  });

  test('senza define SEGNAPOSTO la variante di build e il baluardo', () {
    expect(kVarianteSegnaposto, VarianteSegnaposto.baluardo);
  });

  testWidgets('default di caricaSagomaSegnaposto() senza define: baluardo',
      (t) async {
    azzeraCacheSagoma();
    final sg = await t.runAsync(() => caricaSagomaSegnaposto());
    expect(sg, isNotNull);
    expect(sg!.stile, StileSegnaposto.baluardo);
    expect(sg.larghezza, 44);
    azzeraCacheSagoma();
  });

  testWidgets(
      'caricaSagomaSegnaposto(variante) carica ciascuna variante dal bundle',
      (t) async {
    azzeraCacheSagoma();
    for (final v in kVarianti) {
      final sg = await t.runAsync(() => caricaSagomaSegnaposto(variante: v));
      expect(sg, isNotNull, reason: v.name);
      expect(sg!.stile.name, v.name);
    }
    azzeraCacheSagoma();
  });

  for (final v in kVarianti) {
    final sg = sagomaDi(v);
    testWidgets(
        '[${v.name}] la punta del segnaposto cade sul punto vero (tolleranza 1 px)',
        (t) async {
      final c = await _monta(t, [_s(1, _pA), _s(2, _pB)], Future.value(sg));
      for (final (n, p) in [(1, _pA), (2, _pB)]) {
        final vero = (t.getTopLeft(find.byType(FlutterMap)) +
            c.camera.latLngToScreenOffset(_ll(p)));
        final punta =
            t.getRect(_segnaposto(n)).topLeft + sg.puntaLocale(sg.larghezza);
        expect(
          (punta - vero).distance,
          lessThanOrEqualTo(1),
          reason: 'tappa $n',
        );
      }
      // nessuna separazione: il painter delle linee non ha nulla da tracciare
      final g = t.widget<CustomPaint>(_guide()).painter! as GuidePainter;
      for (var i = 0; i < g.veri.length; i++) {
        expect((g.punte[i] - g.veri[i]).distance, lessThan(2));
      }
      expect(t.takeException(), isNull);
    });

    testWidgets(
        '[${v.name}] due tappe nello stesso punto: linee di richiamo, punte scostate, ciascun tocco apre la propria tappa',
        (t) async {
      final visti = <int>[];
      final c = await _monta(
        t,
        [_s(1, _pA), _s(2, _pA)],
        Future.value(sg),
        visti: visti,
      );
      expect(_guide(), findsOneWidget);
      final g = t.widget<CustomPaint>(_guide()).painter! as GuidePainter;
      // GuidePainter lavora in coordinate locali della mappa
      final origine = t.getTopLeft(find.byType(FlutterMap));
      final vero = c.camera.latLngToScreenOffset(_ll(_pA));
      expect(g.veri.length, 2);
      for (final v in g.veri) {
        expect((v - vero).distance, lessThanOrEqualTo(1));
      }
      for (var i = 0; i < 2; i++) {
        expect(
          (g.punte[i] - g.veri[i]).distance,
          greaterThan(2),
          reason: 'tappa ${i + 1}: serve la linea di richiamo',
        );
      }
      expect(
        (g.punte[0] - g.punte[1]).distance,
        greaterThanOrEqualTo(sg.larghezza),
      );
      // le punte disegnate coincidono con quelle passate al painter
      for (final n in [1, 2]) {
        final punta =
            t.getRect(_segnaposto(n)).topLeft + sg.puntaLocale(sg.larghezza);
        expect(
          (punta - origine - g.punte[n - 1]).distance,
          lessThanOrEqualTo(1),
        );
      }
      for (final n in [1, 2]) {
        visti.clear();
        await t.tapAt(t.getCenter(_segnaposto(n)));
        await t.pump(const Duration(milliseconds: 400));
        expect(visti, [n]);
      }
    });

    group('riquadro della sagoma dentro la mappa (senza separazione)', () {
      for (final (nome, punti) in <(String, List<Punto>)>[
        ('un solo punto', [_pA]),
        ('due punti', [_pA, _pB]),
      ]) {
        testWidgets('[${v.name}] $nome', (t) async {
          await _monta(
            t,
            [for (var i = 0; i < punti.length; i++) _s(i + 1, punti[i])],
            Future.value(sg),
          );
          final mappa = t.getRect(find.byType(FlutterMap));
          for (var n = 1; n <= punti.length; n++) {
            final r = t.getRect(_segnaposto(n));
            expect(
              mappa.contains(r.topLeft),
              isTrue,
              reason: 'angolo alto-sx di $n: $r fuori da $mappa',
            );
            expect(
              mappa.contains(r.bottomRight),
              isTrue,
              reason: 'angolo basso-dx di $n: $r fuori da $mappa',
            );
          }
          expect(t.takeException(), isNull);
        });
      }
    });
  }

  testWidgets('caricamento della sagoma in sospeso: nessuna eccezione',
      (t) async {
    final mai = Completer<SagomaSegnaposto?>();
    await _monta(t, [_s(1, _pA), _s(2, _pB)], mai.future);
    await t.pump(const Duration(seconds: 2));
    expect(t.takeException(), isNull);
    // Mentre attende: riquadro vuoto alto kAltezzaMappa, niente segnaposti.
    expect(_segnaposto(1), findsNothing);
    expect(
      t.getSize(find.byType(MappaItinerario)).height,
      greaterThanOrEqualTo(kAltezzaMappa),
    );
  });

  group('asset mancante: cerchio di riserva', () {
    for (final (nome, f) in <(String, Future<SagomaSegnaposto?> Function())>[
      ('Future.value(null)', () => Future.value(null)),
      (
        'Future.error',
        () => Future<SagomaSegnaposto?>.delayed(
              const Duration(milliseconds: 50),
              () => throw StateError('asset assente'),
            )
      ),
    ]) {
      testWidgets(
          '$nome: riquadro 44x44 centrato sul punto, nessuna linea, nessuna eccezione',
          (t) async {
        final visti = <int>[];
        final c = await _monta(t, [_s(1, _pA), _s(2, _pB)], f(), visti: visti);
        for (final (n, p) in [(1, _pA), (2, _pB)]) {
          final r = t.getRect(_segnaposto(n));
          expect(r.size, const Size.square(Tk.areaMinima));
          final vero = (t.getTopLeft(find.byType(FlutterMap)) +
              c.camera.latLngToScreenOffset(_ll(p)));
          expect((r.center - vero).distance, lessThanOrEqualTo(1));
        }
        expect(_guide(), findsNothing);
        await t.tapAt(t.getCenter(_segnaposto(2)));
        await t.pump(const Duration(milliseconds: 400));
        expect(visti, [2]);
        expect(t.takeException(), isNull);
      });
    }
  });
}
