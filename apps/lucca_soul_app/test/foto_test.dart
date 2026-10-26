// Foto delle tappe: chiave = experience_id. La foto si mostra solo se
// esistono il file jpg negli asset E la voce nel json. Immagini finte in
// memoria: nessun jpg nel repo.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/models/emotional_profile.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/theme/app_theme.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/util/foto_tappa.dart';
import 'package:lucca_soul_app/widgets/foto_tappa_widget.dart';

// PNG 1x1 in memoria (il formato non conta: Image decodifica i byte).
final _png = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
);
ImageProvider _finta(String _) => MemoryImage(_png);

const _voceJson = '{"exp-mura": {"didascalia": "Le Mura al tramonto", "autore": "Mario Rossi"}}';
const _percorso = 'assets/foto/exp-mura.jpg';

ItineraryStop _stop(String id) => ItineraryStop(
      experienceId: id,
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 30,
      reason: 'perché sì',
      titolo: 'Passeggiata',
    );

ArchivioFoto _archivio({Set<String>? asset, String? json = _voceJson}) =>
    ArchivioFoto(asset: asset ?? {_percorso}, voci: parseVociFoto(json), fabbricaImmagine: _finta);

Future<void> _montaCard(WidgetTester t, String id, ArchivioFoto a) async {
  t.view.physicalSize = const Size(390, 844);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(
    MaterialApp(
      theme: buildAppTheme(),
      home: Scaffold(
        body: SingleChildScrollView(
          child: StopCard(
            stop: _stop(id),
            evidenziata: false,
            strings: AppStrings.forLanguages(['it']),
            onLasciaRicordo: () {},
            numero: 1,
            foto: a.per(id),
          ),
        ),
      ),
    ),
  );
  await t.pump();
}

void main() {
  group('risoluzione (pura)', () {
    test('file + voce: foto', () {
      final f = risolviFoto(
        experienceId: 'exp-mura',
        assetDisponibili: {_percorso},
        voci: parseVociFoto(_voceJson),
        fabbricaImmagine: _finta,
      );
      expect(f, isNotNull);
      expect(f!.didascalia, 'Le Mura al tramonto');
      expect(f.autore, 'Mario Rossi');
    });

    test('voce senza file, file senza voce: nessuna foto', () {
      expect(_archivio(asset: {}).per('exp-mura'), isNull);
      expect(_archivio(json: '{}').per('exp-mura'), isNull);
      expect(_archivio(asset: {'assets/foto/altro.jpg'}).per('exp-mura'), isNull);
    });

    test('fluttuante- ed evento-: mai una foto, anche con file e voce', () {
      for (final id in ['fluttuante-x', 'evento-y']) {
        final a = ArchivioFoto(
          asset: {'assets/foto/$id.jpg'},
          voci: parseVociFoto('{"$id": {"didascalia": "d", "autore": "a"}}'),
          fabbricaImmagine: _finta,
        );
        expect(a.voci, isNotEmpty);
        expect(a.per(id), isNull, reason: id);
      }
    });

    test('json malformato o di forma sbagliata: nessuna voce, nessun errore', () {
      for (final j in [null, '', '{non json', '[]', '"x"', '{"exp-mura": 3}', '{"exp-mura": {"autore": "a"}}']) {
        expect(parseVociFoto(j), isEmpty, reason: '$j');
      }
      expect(_archivio(json: '{rotto').per('exp-mura'), isNull);
    });

    test('foto.json vuoto negli asset: archivio senza foto', () async {
      final a = await ArchivioFoto.dalBundle(rootBundle);
      expect(a.per('exp-mura'), isNull);
    });
  });

  group('card', () {
    testWidgets('con foto: miniatura 4:3 con didascalia come etichetta', (t) async {
      final sem = t.ensureSemantics();
      await _montaCard(t, 'exp-mura', _archivio());
      expect(find.byType(MiniaturaFoto), findsOneWidget);
      final r = t.getRect(find.byType(MiniaturaFoto));
      expect(r.width / r.height, closeTo(4 / 3, 0.01));
      expect(r.height, greaterThanOrEqualTo(44));
      expect(find.bySemanticsLabel('Le Mura al tramonto'), findsOneWidget);
      expect(t.takeException(), isNull);
      sem.dispose();
    });

    testWidgets('toccando la miniatura: dettaglio con la foto intera e «Foto: autore»', (t) async {
      await _montaCard(t, 'exp-mura', _archivio());
      await t.tap(find.byType(MiniaturaFoto));
      await t.pumpAndSettle();
      expect(find.byType(DettaglioFoto), findsOneWidget);
      expect(find.text('Foto: Mario Rossi'), findsOneWidget);
      expect(find.text('Le Mura al tramonto'), findsOneWidget);
      expect(t.takeException(), isNull);
    });

    for (final caso in {
      'senza foto': _archivio(json: '{}', asset: {}),
      'voce senza file': _archivio(asset: {}),
      'file senza voce': _archivio(json: '{}'),
      'json malformato': _archivio(json: '{rotto'),
    }.entries) {
      testWidgets('${caso.key}: nessuna miniatura e nessun errore', (t) async {
        await _montaCard(t, 'exp-mura', caso.value);
        expect(find.byType(MiniaturaFoto), findsNothing);
        expect(find.text('Passeggiata'), findsOneWidget);
        expect(t.takeException(), isNull);
      });
    }

    testWidgets('id fluttuante con file e voce: nessuna miniatura', (t) async {
      final a = ArchivioFoto(
        asset: {'assets/foto/fluttuante-a.jpg'},
        voci: parseVociFoto('{"fluttuante-a": {"didascalia": "d", "autore": "a"}}'),
        fabbricaImmagine: _finta,
      );
      await _montaCard(t, 'fluttuante-a', a);
      expect(find.byType(MiniaturaFoto), findsNothing);
    });
  });

  testWidgets('schermata a 390x844 con foto: nessun overflow ne\' scorrimento orizzontale', (t) async {
    t.view.physicalSize = const Size(390, 844);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    final it = Itinerary(
      personId: 'p',
      stops: [_stop('exp-mura'), _stop('evento-z')],
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
          profile: const EmotionalProfile(
            curiosita: 0.5,
            contemplazione: 0.5,
            arte: 0.5,
            conBambini: false,
            tempoDisponibileMin: 240,
          ),
          archivioFoto: _archivio(),
        ),
      ),
    );
    await t.pumpAndSettle();
    expect(t.takeException(), isNull);
    expect(find.byType(MiniaturaFoto), findsOneWidget);
    for (final s in t.widgetList<Scrollable>(find.byType(Scrollable))) {
      expect(s.axisDirection, anyOf(AxisDirection.down, AxisDirection.up));
    }
  });
}
