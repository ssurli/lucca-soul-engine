// Numero delle card sulla sagoma delle Mura senza puntale: asset, geometria del
// numero (anche col glifo reale), linea della timeline, ripiego sul cerchio.
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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
import 'package:lucca_soul_app/widgets/segnaposto_mura.dart';

import 'segnaposto_prove.dart';

Map<String, dynamic> _json() => jsonDecode(
      File('assets/brand/segnaposto_sagoma.json').readAsStringSync(),
    ) as Map<String, dynamic>;

List<Offset> _punti(Object? l) => [
      for (final p in l! as List<dynamic>)
        Offset(
          ((p as List<dynamic>)[0] as num).toDouble(),
          (p[1] as num).toDouble(),
        ),
    ];

Path _percorso(SagomaSegnaposto sg, double larghezza) {
  final s = sg.scala(larghezza);
  final p = Path();
  for (var i = 0; i < sg.contorno.length; i++) {
    final q = (sg.contorno[i] - sg.viewBox.topLeft) * s;
    i == 0 ? p.moveTo(q.dx, q.dy) : p.lineTo(q.dx, q.dy);
  }
  return p..close();
}

/// Griglia 5x5 del rettangolo (angoli, punti medi dei lati e interno).
List<Offset> _campioni(Rect r) => [
      for (var i = 0; i <= 4; i++)
        for (var j = 0; j <= 4; j++)
          Offset(r.left + r.width * i / 4, r.top + r.height * j / 4),
    ];

ItineraryStop _stop(int n) => ItineraryStop(
      experienceId: 'e$n',
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 30,
      reason: 'motivo $n',
      titolo: 'Titolo $n',
    );

Future<void> _monta(
  WidgetTester t,
  Future<SagomaSegnaposto?> sagoma, {
  int tappe = 3,
  String lingua = 'it',
}) async {
  t.view.physicalSize = const Size(390, 4000);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final it = Itinerary(
    personId: 'p',
    stops: [for (var n = 1; n <= tappe; n++) _stop(n)],
    generatedAt: DateTime.utc(2026, 12, 12, 9),
  );
  await t.pumpWidget(
    MaterialApp(
      theme: buildAppTheme(),
      home: ItineraryScreen(
        bffClient: BffClient(
          baseUrl: Uri.parse('http://test'),
          httpClient: MockClient(
            (_) async => http.Response(
              jsonEncode(it.toJson()),
              200,
              headers: {'content-type': 'application/json; charset=utf-8'},
            ),
          ),
        ),
        personId: 'p',
        profile: EmotionalProfile(
          curiosita: 0.5,
          contemplazione: 0.5,
          arte: 0.5,
          conBambini: false,
          tempoDisponibileMin: 240,
          lingue: [lingua],
        ),
        sagomaSegnaposto: sagoma,
      ),
    ),
  );
  await t.pumpAndSettle();
}

Rect _rect(Element e) {
  final r = e.renderObject! as RenderBox;
  return r.localToGlobal(Offset.zero) & r.size;
}

/// La linea della timeline di una card: ColoredBox cardBordo larga 2.
Iterable<Element> _linee(Finder card) => find
    .descendant(
      of: card,
      matching: find.byWidgetPredicate(
        (w) => w is ColoredBox && w.color == Tk.cardBordo,
      ),
    )
    .evaluate()
    .where((e) => (e.renderObject! as RenderBox).size.width == 2);

void main() {
  setUpAll(() async {
    // Font reali del tema: le misure dei glifi sono quelle dell'app.
    final n = FontLoader('NunitoSans')
      ..addFont(
        rootBundle.load('assets/fonts/nunitosans/NunitoSans-Variable.ttf'),
      );
    await n.load();
    final d = FontLoader('Domine')
      ..addFont(rootBundle.load('assets/fonts/domine/Domine-Variable.ttf'));
    await d.load();
  });

  group('asset: chiavi esistenti invariate rispetto a HEAD', () {
    test('contorno 58, traccia 22, viewBox, punta, centroNumero, dimensione',
        () {
      final j = _json();
      final contorno = _punti(j['contorno']);
      expect(contorno.length, 58);
      expect(_punti(j['traccia']).length, 22);
      expect(
        j['viewBox'],
        {'x': -17, 'y': -14, 'larghezza': 34, 'altezza': 32},
      );
      expect(_punti([j['punta']]).single, const Offset(-4.9, 17.2));
      expect(_punti([j['centroNumero']]).single, const Offset(0.4, 0.9));
      expect(j['dimensioneNumero'], 12.5);
      // il puntale e' il punto 31 del contorno originale
      expect(contorno[30], const Offset(-6, 10.6));
      expect(contorno[31], const Offset(-4.9, 17.2));
      expect(contorno[32], const Offset(-3.7, 10.6));
    });
  });

  group('asset: contornoSenzaPunta', () {
    final j = _json();
    final c = _punti(j['contorno']);
    final s = _punti(j['contornoSenzaPunta']);
    final punta = _punti([j['punta']]).single;
    final vb = j['viewBoxSenzaPunta'] as Map<String, dynamic>;
    final box = Rect.fromLTWH(
      (vb['x'] as num).toDouble(),
      (vb['y'] as num).toDouble(),
      (vb['larghezza'] as num).toDouble(),
      (vb['altezza'] as num).toDouble(),
    );

    test('i punti fuori dagli indici sostituiti (30-32) sono quelli originali',
        () {
      expect(s.length, 60);
      expect(s.sublist(0, 30), c.sublist(0, 30));
      // 3 punti (30-32) sostituiti da 5: il resto scorre di 2
      expect(s.sublist(35), c.sublist(33));
    });

    test('nessun puntale: la y massima sta almeno 5 px sopra la punta', () {
      final maxY = s.map((p) => p.dy).reduce((a, b) => a > b ? a : b);
      expect(maxY, lessThanOrEqualTo(punta.dy - 5), reason: 'maxY=$maxY');
      expect(s.contains(punta), isFalse);
      // i punti nuovi (baluardo tozzo) sono bassi al massimo come il corpo
      for (final p in s.sublist(30, 35)) {
        expect(p.dy, lessThan(12));
      }
    });

    test('tutto il contorno sta dentro viewBoxSenzaPunta, con margine sotto',
        () {
      for (final p in s) {
        expect(
          box.inflate(0.001).contains(p),
          isTrue,
          reason: '$p fuori da $box',
        );
      }
      final maxY = s.map((p) => p.dy).reduce((a, b) => a > b ? a : b);
      expect(box.bottom - maxY, greaterThan(0.5));
    });

    test('SagomaSegnaposto.senzaPunta legge le chiavi e non cambia la sagoma',
        () {
      final sg = sagomaMura();
      expect(sg.senzaPunta, isNotNull);
      expect(sg.senzaPunta!.contorno, s);
      expect(sg.senzaPunta!.viewBox, box);
      expect(sg.senzaPunta!.traccia, isEmpty);
      expect(sg.contorno, c);
      expect(sg.viewBox, const Rect.fromLTWH(-17, -14, 34, 32));
      expect(
        sg.senzaPunta!.dimensione(kLarghezzaNumeroCard).height,
        closeTo(24.47, 0.05),
      );
    });

    test('se manca una chiave (o e malformata) senzaPunta e null', () {
      for (final k in [
        'contornoSenzaPunta',
        'viewBoxSenzaPunta',
        'centroNumeroSenzaPunta',
        'dimensioneNumeroSenzaPunta',
      ]) {
        final m = _json()..remove(k);
        expect(SagomaSegnaposto.fromJson(m).senzaPunta, isNull, reason: k);
      }
      final rotto = _json()..['contornoSenzaPunta'] = [1, 2];
      expect(SagomaSegnaposto.fromJson(rotto).senzaPunta, isNull);
      final corto = _json()
        ..['contornoSenzaPunta'] = [
          [0, 0],
          [1, 1],
        ];
      expect(SagomaSegnaposto.fromJson(corto).senzaPunta, isNull);
    });
  });

  group('il numero sta dentro il contorno senza punta', () {
    final sp = sagomaMura().senzaPunta!;
    final corpo = _percorso(sp, kLarghezzaNumeroCard);

    for (final n in [1, 2, 3, 5, 8, 9, 10, 11, 18, 19, 20, 88, 99]) {
      test('rettangoloNumero($n) (euristica) dentro il path', () {
        final r = sp.rettangoloNumero(kLarghezzaNumeroCard, n);
        for (final o in _campioni(r)) {
          expect(corpo.contains(o), isTrue, reason: 'n=$n: $o di $r fuori');
        }
      });
    }

    // Misura REALE: si disegna il numero come fa SagomaPainter e si legge
    // l'inchiostro pixel per pixel (a 8x), poi si controlla che l'ingombro
    // reale stia dentro il path.
    for (final n in [1, 7, 10, 18, 88, 99]) {
      testWidgets('glifo reale di $n dentro il path', (t) async {
        const k = 8.0;
        final size = sp.dimensione(kLarghezzaNumeroCard);
        final dim = sp.dimensioneCarattere(kLarghezzaNumeroCard, n);
        final tp = TextPainter(
          text: TextSpan(
            text: '$n',
            style: stileTesto(dim, 800, const Color(0xFF000000)),
          ),
          textDirection: TextDirection.ltr,
        )..layout();
        final c = (sp.centroNumero - sp.viewBox.topLeft) *
            sp.scala(kLarghezzaNumeroCard);
        final rec = ui.PictureRecorder();
        final cv = Canvas(rec)..scale(k);
        tp.paint(cv, c - Offset(tp.width / 2, tp.height / 2));
        final w = (size.width * k).ceil();
        final h = (size.height * k).ceil();
        final img = await t.runAsync(() => rec.endRecording().toImage(w, h));
        final dati = (await t.runAsync(
          () => img!.toByteData(format: ui.ImageByteFormat.rawRgba),
        ))!;
        var minX = w, minY = h, maxX = -1, maxY = -1;
        for (var y = 0; y < h; y++) {
          for (var x = 0; x < w; x++) {
            if (dati.getUint8((y * w + x) * 4 + 3) > 64) {
              if (x < minX) minX = x;
              if (x > maxX) maxX = x;
              if (y < minY) minY = y;
              if (y > maxY) maxY = y;
            }
          }
        }
        expect(maxX, greaterThan(minX), reason: 'nessun inchiostro: font?');
        final ink =
            Rect.fromLTRB(minX / k, minY / k, (maxX + 1) / k, (maxY + 1) / k);
        for (final o in _campioni(ink)) {
          expect(
            corpo.contains(o),
            isTrue,
            reason: 'n=$n: glifo reale $ink esce dal contorno in $o',
          );
        }
        // l'euristica kAltezzaCifre non sottostima il glifo reale di piu di 1 px
        final r = sp.rettangoloNumero(kLarghezzaNumeroCard, n);
        expect(
          ink.height,
          lessThanOrEqualTo(r.height + 1.0),
          reason: 'altezza reale ${ink.height} contro euristica ${r.height}',
        );
      });
    }
  });

  group('timeline e ripiego nella schermata', () {
    testWidgets(
        'con la sagoma: linea con asse al centro della sagoma, parte dal suo centro',
        (t) async {
      await _monta(t, Future.value(sagomaMura()));
      final cards = find.byType(StopCard);
      for (var i = 0; i < 2; i++) {
        final card = cards.at(i);
        final num = t.getRect(numeroSagoma(card));
        final linee = _linee(card);
        expect(linee, hasLength(1), reason: 'card $i');
        final l = _rect(linee.single);
        expect(
          l.center.dx,
          closeTo(num.center.dx, 0.5),
          reason: 'asse card $i',
        );
        expect(
          l.top,
          closeTo(num.center.dy, 0.5),
          reason: 'parte dal centro card $i',
        );
        expect(l.bottom, greaterThan(num.bottom));
      }
      // l'ultima card non ha linea
      expect(_linee(cards.at(2)), isEmpty);
      expect(t.takeException(), isNull);
    });

    testWidgets(
        'con il cerchio: asse al centro del cerchio, parte dal suo bordo basso (invariato)',
        (t) async {
      await _monta(t, Future.value(null));
      final card = find.byType(StopCard).first;
      final cerchio = t.getRect(
        find
            .descendant(
              of: card,
              matching: find.ancestor(
                of: find.text('1'),
                matching: find.byType(Container),
              ),
            )
            .first,
      );
      final linee = _linee(card);
      expect(linee, hasLength(1));
      final l = _rect(linee.single);
      expect(cerchio.size, const Size(32, 32));
      expect(l.center.dx, closeTo(cerchio.center.dx, 0.5));
      expect(l.top, closeTo(cerchio.bottom, 0.5));
    });

    for (final (nome, f) in <(String, Future<SagomaSegnaposto?> Function())>[
      ('null', () => Future.value(null)),
      (
        'errore',
        () => Future<SagomaSegnaposto?>.delayed(
              const Duration(milliseconds: 50),
              () => throw StateError('assente'),
            ),
      ),
    ]) {
      testWidgets(
          'asset non caricato ($nome): le card hanno il cerchio con il numero come Text',
          (t) async {
        await _monta(t, f());
        expect(numeroSagoma(), findsNothing);
        for (final n in ['1', '2', '3']) {
          expect(find.text(n), findsOneWidget);
        }
        expect(t.takeException(), isNull);
      });
    }

    testWidgets('sagoma senza le chiavi senzaPunta: cerchio di riserva',
        (t) async {
      final m = _json()
        ..remove('contornoSenzaPunta')
        ..remove('viewBoxSenzaPunta');
      final sg = SagomaSegnaposto.fromJson(m);
      expect(sg.senzaPunta, isNull);
      await _monta(t, Future.value(sg));
      expect(numeroSagoma(), findsNothing);
      for (final n in ['1', '2', '3']) {
        expect(find.text(n), findsOneWidget);
      }
    });

    for (final lingua in ['it', 'en']) {
      testWidgets('Semantics: la card annuncia ancora il numero [$lingua]',
          (t) async {
        final h = t.ensureSemantics();
        await _monta(t, Future.value(sagomaMura()), lingua: lingua);
        for (var i = 0; i < 3; i++) {
          expect(
            t.getSemantics(numeroSagoma().at(i)).label,
            startsWith('${i + 1}\n'),
          );
        }
        expect(numeriDisegnati(t), [1, 2, 3]);
        h.dispose();
      });
    }

    testWidgets('due cifre: la tappa 10 e 11 mostrano il numero nella sagoma',
        (t) async {
      await _monta(t, Future.value(sagomaMura()), tappe: 11);
      expect(numeriDisegnati(t), [for (var i = 1; i <= 11; i++) i]);
      expect(numeroSagoma(), findsNWidgets(11));
    });
  });
}
