import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/util/raggruppa_escluse.dart';

const _rStanchezza = 'Tolta per la stanchezza: meglio una giornata più leggera.';
const _rOrario =
    "Tolta: all'ora in cui ci arriveresti il luogo è chiuso, o chiude prima della fine della visita.";
const _rTetto = "Tolta: non c'è più tempo prima della mezzanotte.";

final _it = AppStrings.forLanguages(['it']);
final _en = AppStrings.forLanguages(['en']);

TappaEsclusa _t(String id, String esito, String reason, {String? titolo}) =>
    TappaEsclusa(experienceId: id, esito: esito, reason: reason, titolo: titolo);

Widget _app(Widget child) =>
    MaterialApp(home: Scaffold(body: SingleChildScrollView(child: child)));

Future<void> _pump(WidgetTester tester, List<TappaEsclusa> e, [AppStrings? s]) =>
    tester.pumpWidget(_app(TappeEscluseNote(escluse: e, strings: s ?? _it)));

Finder _gruppo(String esito) => find.byKey(Key('gruppo-escluse-$esito'));

void main() {
  group('raggruppaEscluse (unita)', () {
    test("ordine dei gruppi stabile qualunque sia l'ordine d'ingresso; ordine interno preservato", () {
      final a = _t('a', EsitoTaglio.sospesa, 's1');
      final b = _t('b', EsitoTaglio.orario, _rOrario);
      final c = _t('c', EsitoTaglio.stanchezza, _rStanchezza);
      final d = _t('d', EsitoTaglio.orario, _rOrario);
      final e = _t('e', EsitoTaglio.tettoGiornata, _rTetto);
      final r1 = raggruppaEscluse([a, b, c, d, e]);
      final r2 = raggruppaEscluse([e, d, c, b, a]);
      const atteso = [
        EsitoTaglio.stanchezza,
        EsitoTaglio.tettoGiornata,
        EsitoTaglio.orario,
        EsitoTaglio.sospesa,
      ];
      expect(r1.gruppi.map((g) => g.esito), atteso);
      expect(r2.gruppi.map((g) => g.esito), atteso);
      expect(r1.gruppi[2].tappe.map((t) => t.experienceId), ['b', 'd']);
      expect(r2.gruppi[2].tappe.map((t) => t.experienceId), ['d', 'b']);
    });

    test('gruppi vuoti assenti', () {
      final r = raggruppaEscluse([_t('a', EsitoTaglio.orario, _rOrario)]);
      expect(r.gruppi, hasLength(1));
      expect(r.sconosciute, isEmpty);
      expect(raggruppaEscluse(const []).gruppi, isEmpty);
    });

    test('mai per testo: due esiti diversi con lo stesso reason sono due gruppi', () {
      final r = raggruppaEscluse([
        _t('a', EsitoTaglio.stanchezza, 'Stessa frase'),
        _t('b', EsitoTaglio.orario, 'Stessa frase'),
      ]);
      expect(r.gruppi, hasLength(2));
    });

    test('stesso esito con reason diversi: un gruppo, non uniforme', () {
      final r = raggruppaEscluse([
        _t('a', EsitoTaglio.orario, 'uno'),
        _t('b', EsitoTaglio.orario, 'due'),
      ]);
      expect(r.gruppi, hasLength(1));
      expect(r.gruppi.first.reasonUniforme, isFalse);
    });

    test('reason uguali: uniforme', () {
      final r = raggruppaEscluse([
        _t('a', EsitoTaglio.stanchezza, _rStanchezza),
        _t('b', EsitoTaglio.stanchezza, _rStanchezza),
      ]);
      expect(r.gruppi.first.reasonUniforme, isTrue);
    });

    test("esiti sconosciuti in sconosciute, ordine d'arrivo", () {
      final r = raggruppaEscluse([
        _t('x', 'boh', 'r1'),
        _t('a', EsitoTaglio.orario, _rOrario),
        _t('y', 'esclusa', 'r2'),
      ]);
      expect(r.gruppi, hasLength(1));
      expect(r.sconosciute.map((t) => t.experienceId), ['x', 'y']);
    });
  });

  group('titoloGruppoEscluse', () {
    test('it singolare/plurale per ogni esito noto', () {
      for (final e in EsitoTaglio.ordinati) {
        final s = _it.titoloGruppoEscluse(e, 1);
        final p = _it.titoloGruppoEscluse(e, 2);
        expect(s, isNotEmpty);
        expect(p, isNotEmpty);
        expect(s, isNot(p));
      }
      expect(_it.titoloGruppoEscluse(EsitoTaglio.stanchezza, 1),
          'Tolta per la stanchezza, per una giornata più leggera:',);
      expect(_it.titoloGruppoEscluse(EsitoTaglio.stanchezza, 2),
          'Tolte per la stanchezza, per una giornata più leggera:',);
    });

    test('en invariabile', () {
      for (final e in EsitoTaglio.ordinati) {
        expect(_en.titoloGruppoEscluse(e, 1), _en.titoloGruppoEscluse(e, 3));
        expect(_en.titoloGruppoEscluse(e, 1), isNot(_it.titoloGruppoEscluse(e, 1)));
      }
    });

    test('orario e sospesa: testi allineati alle frasi del motore', () {
      expect(_it.titoloGruppoEscluse(EsitoTaglio.orario, 1),
          "Tolta, chiusa all'arrivo o prima della fine della visita:",);
      expect(_it.titoloGruppoEscluse(EsitoTaglio.orario, 2),
          "Tolte, chiuse all'arrivo o prima della fine della visita:",);
      expect(_en.titoloGruppoEscluse(EsitoTaglio.orario, 2),
          'Left out, closed on arrival or before the visit ends:',);
      expect(_en.titoloGruppoEscluse(EsitoTaglio.sospesa, 2),
          'Left out, temporarily closed:',);
    });

    test('sconosciuto: stringa vuota', () {
      expect(_it.titoloGruppoEscluse('esclusa', 1), '');
      expect(_en.titoloGruppoEscluse('esclusa', 2), '');
    });
  });

  group('TappeEscluseNote (widget)', () {
    testWidgets('1. due per stanchezza: un titolo plurale, due voci senza reason ripetuto', (tester) async {
      await _pump(tester, [
        _t('exp-a', EsitoTaglio.stanchezza, _rStanchezza, titolo: 'Museo A'),
        _t('exp-b', EsitoTaglio.stanchezza, _rStanchezza, titolo: 'Torre B'),
      ]);
      expect(find.text('Tolte per la stanchezza, per una giornata più leggera:'), findsOneWidget);
      expect(find.text('Tolta per la stanchezza, per una giornata più leggera:'), findsNothing);
      expect(find.text('Museo A'), findsOneWidget);
      expect(find.text('Torre B'), findsOneWidget);
      expect(find.textContaining('meglio una giornata'), findsNothing);
      expect(_gruppo(EsitoTaglio.stanchezza), findsOneWidget);
    });

    testWidgets('2. una sola per stanchezza: titolo singolare', (tester) async {
      await _pump(tester, [_t('exp-a', EsitoTaglio.stanchezza, _rStanchezza, titolo: 'Museo A')]);
      expect(find.text('Tolta per la stanchezza, per una giornata più leggera:'), findsOneWidget);
      expect(find.text('Museo A'), findsOneWidget);
    });

    testWidgets('3. due per orario con reason diversi: sotto ciascun titolo la sua frase', (tester) async {
      await _pump(tester, [
        _t('exp-a', EsitoTaglio.orario, _rOrario, titolo: 'Museo A'),
        _t('exp-b', EsitoTaglio.orario, 'Tolta: chiude prima della fine della visita.', titolo: 'Torre B'),
      ]);
      expect(find.text("Tolte, chiuse all'arrivo o prima della fine della visita:"), findsOneWidget);
      expect(find.text('Museo A: $_rOrario'), findsOneWidget);
      expect(find.text('Torre B: Tolta: chiude prima della fine della visita.'), findsOneWidget);
    });

    testWidgets('4. esito sconosciuto: riga titolo: reason, nessun titolo di gruppo', (tester) async {
      await _pump(tester, [_t('exp-a', 'esclusa', 'Chiuso', titolo: 'Museo A')]);
      expect(find.text('Museo A: Chiuso'), findsOneWidget);
      for (final e in EsitoTaglio.ordinati) {
        expect(_gruppo(e), findsNothing);
      }
      expect(find.text(''), findsNothing);
    });

    testWidgets('mai per testo: stesso reason, esiti diversi, due gruppi', (tester) async {
      await _pump(tester, [
        _t('exp-a', EsitoTaglio.stanchezza, 'Stessa', titolo: 'A'),
        _t('exp-b', EsitoTaglio.orario, 'Stessa', titolo: 'B'),
      ]);
      expect(_gruppo(EsitoTaglio.stanchezza), findsOneWidget);
      expect(_gruppo(EsitoTaglio.orario), findsOneWidget);
    });

    testWidgets('gruppi a schermo in ordine stabile, sconosciute in coda', (tester) async {
      await _pump(tester, [
        _t('exp-x', 'esclusa', 'Boh', titolo: 'Ignota'),
        _t('exp-s', EsitoTaglio.sospesa, 'sosp', titolo: 'S'),
        _t('exp-o', EsitoTaglio.orario, _rOrario, titolo: 'O'),
        _t('exp-t', EsitoTaglio.stanchezza, _rStanchezza, titolo: 'T'),
      ]);
      double y(Finder f) => tester.getTopLeft(f).dy;
      final ys = [
        y(_gruppo(EsitoTaglio.stanchezza)),
        y(_gruppo(EsitoTaglio.orario)),
        y(_gruppo(EsitoTaglio.sospesa)),
        y(find.text('Ignota: Boh')),
      ];
      expect(ys, orderedEquals([...ys]..sort()));
      expect(ys.toSet(), hasLength(4));
    });

    testWidgets('ordine interno al gruppo preservato', (tester) async {
      await _pump(tester, [
        _t('exp-b', EsitoTaglio.stanchezza, _rStanchezza, titolo: 'Zeta'),
        _t('exp-a', EsitoTaglio.stanchezza, _rStanchezza, titolo: 'Alfa'),
      ]);
      expect(tester.getTopLeft(find.text('Zeta')).dy,
          lessThan(tester.getTopLeft(find.text('Alfa')).dy),);
    });

    testWidgets('en: titoli en, plurale e singolare uguali', (tester) async {
      await _pump(tester, [
        _t('exp-a', EsitoTaglio.stanchezza, _rStanchezza, titolo: 'A'),
        _t('exp-b', EsitoTaglio.stanchezza, _rStanchezza, titolo: 'B'),
      ], _en,);
      expect(find.text('Left out because of tiredness, for a lighter day:'), findsOneWidget);
      await _pump(tester, [_t('exp-a', EsitoTaglio.stanchezza, _rStanchezza, titolo: 'A')], _en);
      expect(find.text('Left out because of tiredness, for a lighter day:'), findsOneWidget);
    });

    testWidgets('senza titolo: etichetta generica, nessun experience_id', (tester) async {
      await _pump(tester, [
        _t('exp-segreto-1', EsitoTaglio.stanchezza, _rStanchezza),
        _t('exp-segreto-2', EsitoTaglio.orario, _rOrario),
        _t('exp-segreto-3', EsitoTaglio.orario, 'altra', titolo: '  '),
        _t('exp-segreto-4', 'esclusa', 'r'),
      ]);
      expect(find.text('Tappa'), findsOneWidget); // gruppo uniforme stanchezza
      expect(find.text('Tappa: $_rOrario'), findsOneWidget);
      expect(find.text('Tappa: altra'), findsOneWidget);
      expect(find.text('Tappa: r'), findsOneWidget);
      for (final t in tester.widgetList<Text>(find.byType(Text))) {
        expect(t.data ?? '', isNot(contains('exp-')));
      }
    });
  });
}
