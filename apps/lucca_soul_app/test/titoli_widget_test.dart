import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/util/app_strings.dart';

final _strings = AppStrings.forLanguages(['it']);

ItineraryStop _stop({String? titolo}) => ItineraryStop(
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
