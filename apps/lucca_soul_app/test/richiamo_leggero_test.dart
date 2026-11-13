// Linee di richiamo leggere: continue, grigie, sottili, piu leggere della
// linea dell'ordine (accento, 3 px, puntinata).
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/theme/app_theme.dart';
import 'package:lucca_soul_app/theme/tokens.dart';
import 'package:lucca_soul_app/widgets/mappa_itinerario.dart';
import 'package:lucca_soul_app/widgets/segnaposto_mura.dart';

import 'segnaposto_prove.dart';

class _TileKo extends TileProvider {
  @override
  ImageProvider getImage(TileCoordinates coordinates, TileLayer options) =>
      MemoryImage(Uint8List(0));
}

Future<void> _disegna(
  WidgetTester t,
  List<Offset> veri,
  List<Offset> punte,
) =>
    t.pumpWidget(
      Directionality(
        textDirection: TextDirection.ltr,
        child: SizedBox(
          width: 300,
          height: 200,
          child: CustomPaint(painter: GuidePainter(veri, punte)),
        ),
      ),
    );

RenderObject _render(WidgetTester t) => t.renderObject(
      find.descendant(
        of: find.byType(SizedBox),
        matching: find.byType(CustomPaint),
      ),
    );

void main() {
  group('GuidePainter', () {
    test('costanti: colore non testuale, 1 px, pallino 2,5, niente nero', () {
      expect(kColoreRichiamo, Tk.grigioNonTestuale);
      expect(kSpessoreRichiamo, 1);
      expect(kRaggioPallinoRichiamo, 2.5);
      expect(kColoreRichiamo, isNot(Tk.testo));
      expect(kColoreRichiamo, isNot(Colors.black));
      expect(kColoreRichiamo.a, 1.0, reason: 'opaco: nessun alone');
    });

    testWidgets(
        'scostato: una linea e un pallino, colore/spessore/raggio attesi',
        (t) async {
      await _disegna(t, const [Offset(100, 100)], const [Offset(100, 140)]);
      expect(
        _render(t),
        paints
          ..line(
            p1: const Offset(100, 140),
            p2: const Offset(100, 100),
            color: kColoreRichiamo,
            strokeWidth: kSpessoreRichiamo,
          )
          ..circle(
            x: 100,
            y: 100,
            radius: kRaggioPallinoRichiamo,
            color: kColoreRichiamo,
          ),
      );
    });

    testWidgets('un solo disegno per richiamo: niente alone, niente nero',
        (t) async {
      await _disegna(t, const [Offset(100, 100)], const [Offset(100, 140)]);
      // esattamente 1 linea + 1 cerchio: nessun secondo cerchio (alone) o linea
      expect(_render(t), paintsExactlyCountTimes(#drawLine, 1));
      expect(_render(t), paintsExactlyCountTimes(#drawCircle, 1));
      expect(
        _render(t),
        isNot(paints..circle(color: Colors.black)),
      );
      expect(
        _render(t),
        isNot(paints..line(color: Tk.testo)),
      );
    });

    testWidgets('scostamento sotto 2 px: nessun disegno', (t) async {
      await _disegna(
        t,
        const [Offset(100, 100), Offset(50, 50)],
        const [Offset(101, 100.5), Offset(50, 50)],
      );
      expect(_render(t), paintsNothing);
    });

    testWidgets('due richiami: ciascuno con la sua linea e il suo pallino',
        (t) async {
      await _disegna(
        t,
        const [Offset(50, 50), Offset(200, 50)],
        const [Offset(50, 90), Offset(200, 10)],
      );
      expect(_render(t), paintsExactlyCountTimes(#drawLine, 2));
      expect(_render(t), paintsExactlyCountTimes(#drawCircle, 2));
    });
  });

  testWidgets(
      'distinguibile dalla linea dell ordine: colore, spessore e tratto diversi',
      (t) async {
    t.view.physicalSize = const Size(390, 844);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    const p = Punto(lat: 43.8429, lon: 10.5027);
    ItineraryStop s(int n) => ItineraryStop(
          experienceId: 'e$n',
          arrivo: TimeHms.parse('09:00:00'),
          durataMin: 30,
          reason: 'motivo $n',
          puntoArrivo: p,
        );
    await t.pumpWidget(
      MaterialApp(
        theme: buildAppTheme(),
        home: Scaffold(
          body: MappaItinerario(
            tappe: [s(1), s(2)],
            tileProvider: _TileKo(),
            sagoma: Future.value(sagomaMura()),
          ),
        ),
      ),
    );
    await t.pump(const Duration(milliseconds: 200));
    await t.pump(const Duration(milliseconds: 200));
    final ordine =
        t.widget<PolylineLayer>(find.byType(PolylineLayer)).polylines.single;
    expect(ordine.color, Tk.accento);
    expect(ordine.strokeWidth, 3);
    expect(ordine.pattern, const StrokePattern.dotted());
    // il richiamo e davvero presente (due tappe nello stesso punto)
    expect(
      find.byWidgetPredicate(
        (w) => w is CustomPaint && w.painter is GuidePainter,
      ),
      findsOneWidget,
    );
    expect(kColoreRichiamo, isNot(ordine.color));
    expect(kSpessoreRichiamo, lessThan(ordine.strokeWidth));
    // il richiamo e una linea continua (drawLine), l'ordine e puntinato
    expect(ordine.pattern, isNot(const StrokePattern.solid()));
  });

  test('contrasto non testuale: grigio su avviso >= 3:1', () {
    final r = rapportoContrasto(Tk.grigioNonTestuale, Tk.avviso);
    expect(r, greaterThanOrEqualTo(3.0));
    expect(r, closeTo(3.46, 0.02));
  });
}
