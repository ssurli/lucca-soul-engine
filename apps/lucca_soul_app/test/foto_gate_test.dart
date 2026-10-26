// Gate indipendente sul compito 5-bis (foto delle tappe).
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/theme/app_theme.dart';
import 'package:lucca_soul_app/theme/tokens.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/util/foto_tappa.dart';
import 'package:lucca_soul_app/widgets/foto_tappa_widget.dart';

final _png = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
);
ImageProvider _finta(String _) => MemoryImage(_png);

const _json = '{"exp-mura": {"didascalia": "Le Mura al tramonto", "autore": "Mario Rossi"}}';

ItineraryStop _stop(String id) => ItineraryStop(
      experienceId: id,
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 30,
      reason: 'perché sì',
      titolo: 'Passeggiata',
    );

FotoTappa _foto({ImageProvider Function(String)? f}) => risolviFoto(
      experienceId: 'exp-mura',
      assetDisponibili: {'assets/foto/exp-mura.jpg'},
      voci: parseVociFoto(_json),
      fabbricaImmagine: f ?? _finta,
    )!;

Future<void> _monta(WidgetTester t, FotoTappa? foto, {Size size = const Size(390, 844), bool esplicito = true}) async {
  t.view.physicalSize = size;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final strings = AppStrings.forLanguages(['it']);
  await t.pumpWidget(MaterialApp(
    theme: buildAppTheme(),
    home: Scaffold(
      body: SingleChildScrollView(
        child: esplicito
            ? StopCard(stop: _stop('exp-mura'), evidenziata: false, strings: strings, onLasciaRicordo: () {}, numero: 1, foto: foto)
            : StopCard(stop: _stop('exp-mura'), evidenziata: false, strings: strings, onLasciaRicordo: () {}, numero: 1),
      ),
    ),
  ),);
  await t.pump();
}

void main() {
  group('card senza foto identica a prima', () {
    testWidgets('foto null == parametro omesso; nessun AspectRatio ne\' Image nella card', (t) async {
      await _monta(t, null);
      final h1 = t.getSize(find.byType(StopCard));
      expect(find.descendant(of: find.byType(StopCard), matching: find.byType(AspectRatio)), findsNothing);
      expect(find.descendant(of: find.byType(StopCard), matching: find.byType(Image)), findsNothing);
      expect(find.byType(MiniaturaFoto), findsNothing);
      await _monta(t, null, esplicito: false);
      expect(t.getSize(find.byType(StopCard)), h1);
    });

    testWidgets('la foto aggiunge esattamente 10 + altezza miniatura (nessuno spazio riservato senza foto)', (t) async {
      await _monta(t, null);
      final senza = t.getSize(find.byType(StopCard)).height;
      await _monta(t, _foto());
      final con = t.getSize(find.byType(StopCard)).height;
      final mini = t.getSize(find.byType(MiniaturaFoto)).height;
      expect(con - senza, closeTo(10 + mini, 0.5));
    });

    testWidgets('stessi figli del Column con foto null: titolo, orario, reason, ricordo', (t) async {
      await _monta(t, null);
      expect(find.text('Passeggiata'), findsOneWidget);
      expect(find.text('perché sì'), findsOneWidget);
      expect(find.textContaining('09:00'), findsOneWidget);
    });
  });

  group('miniatura', () {
    testWidgets('4:3 effettiva, ritagliata (cover), >= 44 px, etichetta = didascalia', (t) async {
      final sem = t.ensureSemantics();
      await _monta(t, _foto());
      final r = t.getRect(find.byType(MiniaturaFoto));
      expect(r.width / r.height, closeTo(4 / 3, 0.01));
      expect(r.width, greaterThanOrEqualTo(Tk.areaMinima));
      expect(r.height, greaterThanOrEqualTo(Tk.areaMinima));
      final img = t.widget<Image>(find.descendant(of: find.byType(MiniaturaFoto), matching: find.byType(Image)));
      expect(img.fit, BoxFit.cover);
      final ir = t.getRect(find.descendant(of: find.byType(MiniaturaFoto), matching: find.byType(Image)));
      expect(ir.width / ir.height, closeTo(4 / 3, 0.01));
      final nodo = t.getSemantics(find.byType(MiniaturaFoto));
      expect(nodo.label, 'Le Mura al tramonto');
      expect(r.right, lessThanOrEqualTo(390));
      expect(t.takeException(), isNull);
      sem.dispose();
    });

    testWidgets('file illeggibile: nessuna eccezione e nessuno spazio riservato (la card resta com\'e\')', (t) async {
      await _monta(t, null);
      final senza = t.getSize(find.byType(StopCard)).height;
      await _monta(t, _foto(f: (_) => MemoryImage(Uint8List.fromList([1, 2, 3]))));
      await t.pump();
      await t.pump();
      expect(t.takeException(), isNull);
      final con = t.getSize(find.byType(StopCard)).height;
      expect(con, senza, reason: 'jpg corrotto: resta un riquadro vuoto toccabile di ${con - senza} px');
    });
  });

  group('dettaglio', () {
    testWidgets('foto intera (contain), didascalia, «Foto: autore»', (t) async {
      await _monta(t, _foto());
      await t.tap(find.byType(MiniaturaFoto));
      await t.pumpAndSettle();
      final img = t.widget<Image>(find.descendant(of: find.byType(DettaglioFoto), matching: find.byType(Image)));
      expect(img.fit, BoxFit.contain);
      expect(find.text('Foto: Mario Rossi'), findsOneWidget);
      expect(find.text('Le Mura al tramonto'), findsOneWidget);
      expect(t.takeException(), isNull);
    });

    testWidgets('in inglese: «Photo: autore»', (t) async {
      expect(AppStrings.forLanguages(['en']).photoBy('X'), 'Photo: X');
      expect(AppStrings.forLanguages(['it']).photoBy('X'), 'Foto: X');
    });

    testWidgets('schermo largo: il contenuto resta nella colonna <= 600', (t) async {
      await _monta(t, _foto(), size: const Size(1400, 900));
      await t.tap(find.byType(MiniaturaFoto));
      await t.pumpAndSettle();
      for (final f in [find.text('Foto: Mario Rossi'), find.text('Le Mura al tramonto'), find.descendant(of: find.byType(DettaglioFoto), matching: find.byType(Image))]) {
        final r = t.getRect(f);
        expect(r.width, lessThanOrEqualTo(600.5));
      }
      expect(t.getRect(find.text('Foto: Mario Rossi')).center.dx, closeTo(700, 300));
    });

    testWidgets('390x844: nessun overflow ne\' scorrimento orizzontale', (t) async {
      await _monta(t, _foto());
      await t.tap(find.byType(MiniaturaFoto));
      await t.pumpAndSettle();
      expect(t.takeException(), isNull);
      for (final s in t.widgetList<Scrollable>(find.byType(Scrollable))) {
        expect(s.axisDirection, anyOf(AxisDirection.down, AxisDirection.up));
      }
      expect(t.getRect(find.byType(DettaglioFoto)).width, 390);
    });

    testWidgets('contrasto dei testi nuovi >= 4,5 sui loro sfondi reali', (t) async {
      await _monta(t, _foto());
      await t.tap(find.byType(MiniaturaFoto));
      await t.pumpAndSettle();
      final sfondo = t.widget<Scaffold>(find.descendant(of: find.byType(DettaglioFoto), matching: find.byType(Scaffold))).backgroundColor ??
          Theme.of(t.element(find.byType(DettaglioFoto))).scaffoldBackgroundColor;
      for (final testo in ['Le Mura al tramonto', 'Foto: Mario Rossi']) {
        final w = t.widget<Text>(find.text(testo));
        final colore = w.style?.color ?? DefaultTextStyle.of(t.element(find.text(testo))).style.color!;
        expect(rapportoContrasto(colore, sfondo), greaterThanOrEqualTo(4.5), reason: testo);
      }
    });
  });

  group('repo', () {
    test('foto.json committato e` {} e nessun jpg in assets/foto', () {
      final dir = Directory('assets/foto');
      expect(jsonDecode(File('assets/foto/foto.json').readAsStringSync()), <String, dynamic>{});
      final jpg = dir.listSync().where((e) => e.path.toLowerCase().endsWith('.jpg') || e.path.toLowerCase().endsWith('.jpeg'));
      expect(jpg, isEmpty);
    });

    test('la foto non esce dall\'app: nessun riferimento in modelli e client BFF', () {
      final re = RegExp(r'\bfoto\b|FotoTappa|ArchivioFoto|didascalia', caseSensitive: false);
      for (final d in ['lib/models', 'lib/api']) {
        for (final f in Directory(d).listSync(recursive: true).whereType<File>()) {
          expect(re.hasMatch(f.readAsStringSync()), isFalse, reason: f.path);
        }
      }
      final it = Itinerary(personId: 'p', stops: [_stop('exp-mura')], generatedAt: DateTime.utc(2026, 1, 1));
      expect(jsonEncode(it.toJson()).toLowerCase().contains('foto'), isFalse);
    });

    test('id fluttuante/evento: mai foto, qualunque combinazione', () {
      for (final id in ['fluttuante-1', 'evento-2']) {
        expect(idSenzaFoto(id), isTrue);
        expect(
          risolviFoto(
            experienceId: id,
            assetDisponibili: {'assets/foto/$id.jpg'},
            voci: parseVociFoto('{"$id": {"didascalia": "d", "autore": "a"}}'),
          ),
          isNull,
        );
      }
      expect(idSenzaFoto('exp-fluttuante-x'), isFalse);
    });
  });
}
