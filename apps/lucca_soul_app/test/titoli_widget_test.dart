import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/util/app_strings.dart';

final _strings = AppStrings.forLanguages(['it']);

ItineraryStop _stop({String? titolo, List<Curiosita> curiosita = const []}) => ItineraryStop(
      curiosita: curiosita,
      experienceId: 'exp-passeggiata-mura',
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 60,
      reason: 'Perche\' ti piace camminare',
      titolo: titolo,
    );

Widget _app(Widget child) => MaterialApp(home: Scaffold(body: SingleChildScrollView(child: child)));

void _nessunId(WidgetTester tester) {
  final testi = tester.widgetList<Text>(find.byType(Text)).map((t) => t.data ?? '').toList();
  for (final t in testi) {
    expect(t, isNot(contains('exp-')));
  }
}

void main() {
  testWidgets('scheda tappa con titolo: titolo visibile, nessun id', (tester) async {
    await tester.pumpWidget(_app(
      StopCard(stop: _stop(titolo: 'Passeggiata sulle Mura'), evidenziata: false, strings: _strings, onLasciaRicordo: () {}),
    ),);
    expect(find.text('Passeggiata sulle Mura'), findsOneWidget);
    _nessunId(tester);
  });

  testWidgets('scheda tappa senza titolo: etichetta generica, nessun id', (tester) async {
    await tester.pumpWidget(_app(
      StopCard(stop: _stop(), evidenziata: false, strings: _strings, onLasciaRicordo: () {}),
    ),);
    expect(find.text('Tappa'), findsOneWidget);
    _nessunId(tester);
  });

  testWidgets('note delle escluse: con e senza titolo, nessun id', (tester) async {
    await tester.pumpWidget(_app(
      TappeEscluseNote(
        strings: _strings,
        escluse: const [
          TappaEsclusa(experienceId: 'exp-a', esito: 'esclusa', reason: 'Chiuso', titolo: 'Museo A'),
          TappaEsclusa(experienceId: 'exp-b', esito: 'esclusa', reason: 'Poco tempo'),
        ],
      ),
    ),);
    expect(find.text('Museo A: Chiuso'), findsOneWidget);
    expect(find.text('Tappa: Poco tempo'), findsOneWidget);
    _nessunId(tester);
  });

  group('curiosita', () {
    const leggenda = Curiosita(
      testo: 'Si racconta che la torre sia nata da un patto.',
      tipo: CuriosityKind.leggenda,
      fonte: 'Tradizione orale',
      fontePubblica: true,
    );
    const fatto = Curiosita(
      testo: 'Le Mura sono lunghe oltre quattro chilometri.',
      tipo: CuriosityKind.fatto,
      fonte: 'Archivio storico',
      fontePubblica: true,
    );

    Future<void> pump(WidgetTester tester, List<Curiosita> c, [AppStrings? s]) => tester.pumpWidget(_app(
          StopCard(
            stop: _stop(titolo: 'T', curiosita: c),
            evidenziata: false,
            strings: s ?? _strings,
            onLasciaRicordo: () {},
          ),
        ),);

    testWidgets('leggenda: etichetta Leggenda, testo Si racconta, fonte', (tester) async {
      await pump(tester, [leggenda]);
      expect(find.text('Leggenda'), findsOneWidget);
      expect(find.text(leggenda.testo), findsOneWidget);
      expect(leggenda.testo.startsWith('Si racconta'), isTrue);
      expect(find.text('Fonte: Tradizione orale'), findsOneWidget);
      _nessunId(tester);
    });

    testWidgets('fatto: nessuna etichetta Leggenda, fonte visibile', (tester) async {
      await pump(tester, [fatto]);
      expect(find.text('Leggenda'), findsNothing);
      expect(find.text('Curiosità'), findsOneWidget);
      expect(find.text(fatto.testo), findsOneWidget);
      expect(find.text('Fonte: Archivio storico'), findsOneWidget);
    });

    testWidgets('fonte non pubblica: riga Fonte nascosta', (tester) async {
      const privata = Curiosita(
        testo: 'Un fatto.',
        tipo: CuriosityKind.fatto,
        fonte: 'Dato del committente',
      );
      await pump(tester, [privata]);
      expect(find.text('Un fatto.'), findsOneWidget);
      expect(find.textContaining('Fonte:'), findsNothing);
      expect(find.textContaining('Dato del committente'), findsNothing);
    });

    test('JSON senza fonte_pubblica -> false; round-trip lo preserva', () {
      final senza = Curiosita.fromJson({'testo': 'x', 'tipo': 'fatto', 'fonte': 'f'});
      expect(senza.fontePubblica, isFalse);
      expect(senza.toJson()['fonte_pubblica'], isFalse);
      final pub = Curiosita.fromJson(
        {'testo': 'x', 'tipo': 'fatto', 'fonte': 'f', 'fonte_pubblica': true},
      );
      expect(pub.fontePubblica, isTrue);
      expect(Curiosita.fromJson(pub.toJson()).fontePubblica, isTrue);
    });

    testWidgets('senza curiosita: nessuna sezione', (tester) async {
      await pump(tester, const []);
      expect(find.text('Leggenda'), findsNothing);
      expect(find.text('Curiosità'), findsNothing);
      expect(find.textContaining('Fonte:'), findsNothing);
    });

    testWidgets('inglese: Legend e Source', (tester) async {
      await pump(tester, [leggenda], AppStrings.forLanguages(['en']));
      expect(find.text('Legend'), findsOneWidget);
      expect(find.text('Source: Tradizione orale'), findsOneWidget);
    });

    test('JSON andata e ritorno; assente = vuota, vuota omessa', () {
      final json = {
        'experience_id': 'exp-x',
        'arrivo': '09:00:00',
        'durata_min': 30,
        'reason': 'r',
        'curiosita': [
          {'testo': leggenda.testo, 'tipo': 'leggenda', 'fonte': 'Tradizione orale', 'fonte_pubblica': true},
          {'testo': fatto.testo, 'tipo': 'fatto', 'fonte': 'Archivio storico', 'fonte_pubblica': true},
        ],
      };
      final s = ItineraryStop.fromJson(json);
      expect(s.curiosita.map((c) => c.tipo), [CuriosityKind.leggenda, CuriosityKind.fatto]);
      expect(s.toJson()['curiosita'], json['curiosita']);
      final senza = ItineraryStop.fromJson(
        {'experience_id': 'exp-x', 'arrivo': '09:00:00', 'durata_min': 30, 'reason': 'r'},
      );
      expect(senza.curiosita, isEmpty);
      expect(senza.toJson().containsKey('curiosita'), isFalse);
    });
  });

  test('titolo: andata e ritorno JSON, omesso se assente', () {
    final con = ItineraryStop.fromJson({
      'experience_id': 'exp-x', 'arrivo': '09:00:00', 'durata_min': 30, 'reason': 'r', 'titolo': 'T',
    });
    expect(con.titolo, 'T');
    expect(con.toJson()['titolo'], 'T');
    expect(_stop().toJson().containsKey('titolo'), isFalse);
    final esc = TappaEsclusa.fromJson({'experience_id': 'exp-x', 'esito': 'e', 'reason': 'r', 'titolo': 'T'});
    expect(esc.toJson()['titolo'], 'T');
  });
}
