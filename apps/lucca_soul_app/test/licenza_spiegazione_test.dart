// Voce 1: nel foglio di conferimento la licenza scelta e' spiegata in chiaro,
// e l'avvertenza di irrevocabilita' e' sempre visibile, vicino al consenso.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/models/person_kind.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/widgets/memory_contribution_sheet.dart';

const _itCcBySa =
    'Chiunque può riusare e modificare il tuo ricordo, anche a fini commerciali, citando la fonte e mantenendo la stessa licenza.';
const _itCcBy =
    'Chiunque può riusare e modificare il tuo ricordo, anche a fini commerciali, citando la fonte.';
const _itCc0 =
    'Rinunci a ogni diritto: chiunque può usare il tuo ricordo senza condizioni e senza citare nessuno.';
const _itIrrevocabile =
    'La scelta non si può ritirare: chi ha già ricevuto il ricordo con questa licenza può continuare a usarlo.';

const _attesiIt = {
  'CC-BY-SA-4.0': _itCcBySa,
  'CC-BY-4.0': _itCcBy,
  'CC0-1.0': _itCc0,
};

final _it = AppStrings.forLanguages(['it']);
final _en = AppStrings.forLanguages(['en']);

/// BFF che registra i corpi inviati.
BffClient _client(List<String> inviati) => BffClient(
      baseUrl: Uri.parse('http://test'),
      httpClient: MockClient((req) async {
        inviati.add(req.body);
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

String _spiegazione(WidgetTester t) =>
    t.widget<Text>(find.byKey(const Key('license-explanation'))).data!;

Future<void> _scegli(WidgetTester t, String sigla) async {
  await t.tap(find.byType(DropdownButtonFormField<String>));
  await t.pumpAndSettle();
  await t.tap(find.text(sigla).last);
  await t.pumpAndSettle();
}

void main() {
  group('unit: AppStrings.licenseExplanation', () {
    test('sigla ignota -> ArgumentError, nessun testo di ripiego', () {
      expect(() => _it.licenseExplanation('GPL-3.0'), throwsArgumentError);
      expect(() => _en.licenseExplanation('GPL-3.0'), throwsArgumentError);
      expect(() => _it.licenseExplanation(''), throwsArgumentError);
      expect(() => _it.licenseExplanation('cc0-1.0'), throwsArgumentError);
    });

    test('ogni sigla di kMemoryLicenseOptions ha una spiegazione non vuota in it e en', () {
      expect(kMemoryLicenseOptions, isNotEmpty);
      for (final s in [_it, _en]) {
        for (final sigla in kMemoryLicenseOptions) {
          expect(s.licenseExplanation(sigla).trim(), isNotEmpty, reason: sigla);
        }
      }
    });

    test('le spiegazioni sono diverse tra loro (una per sigla), in it e in en', () {
      for (final s in [_it, _en]) {
        final testi = kMemoryLicenseOptions.map(s.licenseExplanation).toSet();
        expect(testi.length, kMemoryLicenseOptions.length);
      }
    });

    test('testi italiani esatti', () {
      for (final e in _attesiIt.entries) {
        expect(_it.licenseExplanation(e.key), e.value);
      }
      expect(_it.licenseIrrevocable, _itIrrevocabile);
    });

    test('inglese diverso dall italiano', () {
      for (final sigla in kMemoryLicenseOptions) {
        expect(_en.licenseExplanation(sigla), isNot(_it.licenseExplanation(sigla)));
      }
      expect(_en.licenseIrrevocable, isNot(_it.licenseIrrevocable));
      expect(_en.licenseIrrevocable.trim(), isNotEmpty);
    });
  });

  group('widget: foglio di conferimento', () {
    testWidgets('all apertura la spiegazione e quella della prima licenza', (t) async {
      await _apri(t, _it);
      expect(kMemoryLicenseOptions.first, 'CC-BY-SA-4.0');
      expect(_spiegazione(t), _itCcBySa);
    });

    testWidgets('cambiando la selezione la spiegazione cambia per ognuna delle tre', (t) async {
      await _apri(t, _it);
      final viste = <String>[];
      for (final sigla in ['CC-BY-4.0', 'CC0-1.0', 'CC-BY-SA-4.0', 'CC0-1.0']) {
        await _scegli(t, sigla);
        expect(_spiegazione(t), _attesiIt[sigla], reason: sigla);
        viste.add(_spiegazione(t));
      }
      expect(viste.toSet().length, 3);
    });

    testWidgets('l avvertenza e visibile anche senza consenso e con ogni licenza', (t) async {
      await _apri(t, _it);
      expect(find.byKey(const Key('license-irrevocable')), findsOneWidget);
      expect(find.text(_itIrrevocabile), findsOneWidget);
      expect(t.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value, isFalse);
      for (final sigla in kMemoryLicenseOptions) {
        await _scegli(t, sigla);
        expect(find.text(_itIrrevocabile), findsOneWidget, reason: sigla);
      }
      await t.tap(find.byType(CheckboxListTile));
      await t.pumpAndSettle();
      expect(find.text(_itIrrevocabile), findsOneWidget);
    });

    testWidgets('l avvertenza sta subito sopra la checkbox del consenso', (t) async {
      await _apri(t, _it);
      final avvertenza = t.getRect(find.byKey(const Key('license-irrevocable')));
      final consenso = t.getRect(find.byType(CheckboxListTile));
      final spiegazione = t.getRect(find.byKey(const Key('license-explanation')));
      expect(avvertenza.bottom, lessThanOrEqualTo(consenso.top));
      expect(consenso.top - avvertenza.bottom, lessThan(24));
      // Ordine: spiegazione, poi avvertenza, poi consenso.
      expect(spiegazione.bottom, lessThanOrEqualTo(avvertenza.top));
    });

    testWidgets('inglese: testi inglesi, uno per sigla, diversi tra loro', (t) async {
      await _apri(t, _en);
      final viste = <String>{};
      for (final sigla in kMemoryLicenseOptions) {
        await _scegli(t, sigla);
        final testo = _spiegazione(t);
        expect(testo, _en.licenseExplanation(sigla), reason: sigla);
        expect(testo, isNot(_it.licenseExplanation(sigla)), reason: sigla);
        viste.add(testo);
      }
      expect(viste.length, kMemoryLicenseOptions.length);
      expect(find.text(_en.licenseIrrevocable), findsOneWidget);
      expect(find.text(_itIrrevocabile), findsNothing);
    });

    testWidgets('regole di invio invariate: senza consenso il bottone e disabilitato', (t) async {
      await _apri(t, _it);
      await t.enterText(find.byType(TextField).first, 'un ricordo');
      await t.pumpAndSettle();
      FilledButton bottone() => t.widget<FilledButton>(find.byType(FilledButton));
      expect(bottone().onPressed, isNull);
      // Cambiare licenza non abilita nulla.
      await _scegli(t, 'CC0-1.0');
      expect(bottone().onPressed, isNull);
      await t.tap(find.byType(CheckboxListTile));
      await t.pumpAndSettle();
      expect(bottone().onPressed, isNotNull);
      await t.tap(find.byType(CheckboxListTile));
      await t.pumpAndSettle();
      expect(bottone().onPressed, isNull);
    });

    testWidgets('la licenza inviata e quella spiegata a schermo', (t) async {
      final inviati = <String>[];
      await _apri(t, _it, inviati: inviati);
      await _scegli(t, 'CC0-1.0');
      await t.enterText(find.byType(TextField).first, 'un ricordo');
      await t.tap(find.byType(CheckboxListTile));
      await t.pumpAndSettle();
      await t.tap(find.text(_it.memorySubmit));
      await t.pumpAndSettle();
      expect(inviati, hasLength(1));
      expect(inviati.single, contains('"licenza":"CC0-1.0"'));
      expect(_spiegazione(t), _itCc0);
    });
  });
}
