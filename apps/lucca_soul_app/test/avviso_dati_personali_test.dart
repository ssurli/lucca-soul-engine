// Avviso "niente dati personali" nel foglio dei ricordi: sempre visibile,
// posizionato tra racconto e media, senza alcun controllo sul testo.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/models/person_kind.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/widgets/memory_contribution_sheet.dart';

const _itAvviso =
    'Non scrivere nomi, indirizzi o altri dati personali, tuoi o di altre persone.';
const _enAvviso =
    "Don't write names, addresses or other personal details, yours or anyone else's.";
const _chiave = Key('memory-no-personal-data');

final _it = AppStrings.forLanguages(['it']);
final _en = AppStrings.forLanguages(['en']);

BffClient _client(List<String> inviati) => BffClient(
      baseUrl: Uri.parse('http://test'),
      httpClient: MockClient((req) async {
        inviati.add(utf8.decode(req.bodyBytes));
        return http.Response('{}', 500);
      }),
    );

Future<void> _apri(WidgetTester t, AppStrings s, {List<String>? inviati}) async {
  t.view.physicalSize = const Size(800, 2400);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(MaterialApp(
    home: Scaffold(
      body: SingleChildScrollView(
        child: MemoryContributionSheet(
          bffClient: _client(inviati ?? []),
          contributorId: 'c',
          contributorKind: PersonKind.cittadino,
          riguarda: const ['mura-urbane'],
          strings: s,
        ),
      ),
    ),
  ),);
  await t.pumpAndSettle();
}

FilledButton _bottone(WidgetTester t) => t.widget<FilledButton>(find.byType(FilledButton));

void main() {
  group('unit: AppStrings.memoryNoPersonalData', () {
    test('non vuoto e diverso tra it ed en', () {
      expect(_it.memoryNoPersonalData.trim(), isNotEmpty);
      expect(_en.memoryNoPersonalData.trim(), isNotEmpty);
      expect(_en.memoryNoPersonalData, isNot(_it.memoryNoPersonalData));
    });
  });

  group('widget: avviso dati personali', () {
    testWidgets('italiano: testo esatto a foglio aperto, resta dopo testo e consenso', (t) async {
      await _apri(t, _it);
      expect(t.widget<Text>(find.byKey(_chiave)).data, _itAvviso);
      expect(find.text(_itAvviso), findsOneWidget);

      await t.enterText(find.byType(TextField).first, 'un ricordo');
      await t.pumpAndSettle();
      expect(find.text(_itAvviso), findsOneWidget);

      await t.tap(find.byType(CheckboxListTile));
      await t.pumpAndSettle();
      expect(find.text(_itAvviso), findsOneWidget);
    });

    testWidgets('posizione: sotto il racconto e sopra il media', (t) async {
      await _apri(t, _it);
      final campi = find.byType(TextField);
      expect(campi, findsNWidgets(2));
      final racconto = t.getRect(campi.at(0));
      final media = t.getRect(campi.at(1));
      final avviso = t.getRect(find.byKey(_chiave));
      expect(avviso.top, greaterThanOrEqualTo(racconto.bottom));
      expect(avviso.bottom, lessThanOrEqualTo(media.top));
    });

    testWidgets('inglese: testo inglese esatto, italiano assente', (t) async {
      await _apri(t, _en);
      expect(t.widget<Text>(find.byKey(_chiave)).data, _enAvviso);
      expect(find.text(_enAvviso), findsOneWidget);
      expect(find.text(_itAvviso), findsNothing);
    });

    testWidgets('nessun controllo sul testo: nome e indirizzo non bloccano ne alterano l invio',
        (t) async {
      const testo = 'Mario Rossi, via Roma 1';
      final inviati = <String>[];
      await _apri(t, _it, inviati: inviati);

      await t.enterText(find.byType(TextField).first, 'un ricordo qualunque');
      await t.tap(find.byType(CheckboxListTile));
      await t.pumpAndSettle();
      final abilitatoNormale = _bottone(t).onPressed != null;
      expect(abilitatoNormale, isTrue);

      await t.enterText(find.byType(TextField).first, testo);
      await t.pumpAndSettle();
      expect(_bottone(t).onPressed != null, abilitatoNormale);
      expect(find.text(_itAvviso), findsOneWidget);

      await t.tap(find.text(_it.memorySubmit));
      await t.pumpAndSettle();
      expect(inviati, hasLength(1));
      final corpo = jsonDecode(inviati.single) as Map<String, dynamic>;
      expect(corpo['testo'], testo);
    });
  });
}
