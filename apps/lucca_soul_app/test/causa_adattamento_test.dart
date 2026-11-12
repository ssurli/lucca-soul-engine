// causa_adattamento: etichetta della tappa sostituita e specchio del campo.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/util/app_strings.dart';

Map<String, dynamic> _json({String? causa, String? esito}) => {
      'experience_id': 'a',
      'arrivo': '09:00:00',
      'durata_min': 30,
      'reason': 'm',
      if (esito != null) 'esito_adattamento': esito,
      if (causa != null) 'causa_adattamento': causa,
    };

Future<void> _monta(
  WidgetTester t, {
  String? causa,
  bool evidenziata = true,
  bool mantenuta = false,
  String lingua = 'it',
}) =>
    t.pumpWidget(MaterialApp(
      home: Scaffold(
        body: StopCard(
          stop: ItineraryStop(
            experienceId: 'a',
            arrivo: TimeHms.parse('09:00:00'),
            durataMin: 30,
            reason: 'm',
            titolo: 'Titolo',
            causaAdattamento: causa,
          ),
          evidenziata: evidenziata,
          mantenutaSenzaAlternativa: mantenuta,
          onLasciaRicordo: () {},
          strings: AppStrings.forLanguages([lingua]),
        ),
      ),
    ),);

void main() {
  group('changedStopFor', () {
    final it = AppStrings.forLanguages(['it']);
    final en = AppStrings.forLanguages(['en']);

    test('italiano: pioggia, affollamento, ripiego', () {
      expect(it.changedStopFor('pioggia'), 'Cambiata per la pioggia');
      expect(it.changedStopFor('affollamento'), 'Cambiata per la folla');
      expect(it.changedStopFor(null), 'Cambiata dal segnale');
      expect(it.changedStopFor('stanchezza'), 'Cambiata dal segnale');
      expect(it.changedStopFor(''), 'Cambiata dal segnale');
    });

    test('inglese: pioggia, affollamento, ripiego', () {
      expect(en.changedStopFor('pioggia'), 'Changed because of the rain');
      expect(en.changedStopFor('affollamento'), 'Changed because of the crowd');
      expect(en.changedStopFor(null), 'Changed by the signal');
      expect(en.changedStopFor('xyz'), 'Changed by the signal');
    });
  });

  group('ItineraryStop.causaAdattamento', () {
    test('fromJson legge il campo, toJson lo riemette', () {
      for (final causa in ['pioggia', 'affollamento']) {
        final j = _json(causa: causa, esito: 'sostituita');
        final s = ItineraryStop.fromJson(j);
        expect(s.causaAdattamento, causa);
        expect(s.toJson()['causa_adattamento'], causa);
        expect(ItineraryStop.fromJson(s.toJson()).causaAdattamento, causa);
      }
    });

    test('assente: null e non emesso', () {
      final s = ItineraryStop.fromJson(_json(esito: 'sostituita'));
      expect(s.causaAdattamento, isNull);
      expect(s.toJson().containsKey('causa_adattamento'), isFalse);
    });

    test('valore sconosciuto: conservato com\'e\' (stringa grezza)', () {
      final s = ItineraryStop.fromJson(_json(causa: 'caldo', esito: 'sostituita'));
      expect(s.causaAdattamento, 'caldo');
    });
  });

  group('StopCard: etichetta della tappa sostituita', () {
    testWidgets('pioggia', (t) async {
      await _monta(t, causa: 'pioggia');
      expect(find.text('Cambiata per la pioggia'), findsOneWidget);
    });

    testWidgets('affollamento', (t) async {
      await _monta(t, causa: 'affollamento');
      expect(find.text('Cambiata per la folla'), findsOneWidget);
    });

    testWidgets('senza causa: ripiego Cambiata dal segnale', (t) async {
      await _monta(t);
      expect(find.text('Cambiata dal segnale'), findsOneWidget);
    });

    testWidgets('causa sconosciuta: ripiego Cambiata dal segnale', (t) async {
      await _monta(t, causa: 'caldo');
      expect(find.text('Cambiata dal segnale'), findsOneWidget);
    });

    testWidgets('in inglese', (t) async {
      await _monta(t, causa: 'pioggia', lingua: 'en');
      expect(find.text('Changed because of the rain'), findsOneWidget);
      expect(find.text('Cambiata per la pioggia'), findsNothing);
    });

    testWidgets('la mantenuta non cambia etichetta, con o senza causa', (t) async {
      final atteso = AppStrings.forLanguages(['it']).keptNoAlternative;
      for (final causa in [null, 'pioggia', 'affollamento']) {
        await _monta(t, causa: causa, evidenziata: false, mantenuta: true);
        expect(find.text(atteso), findsOneWidget, reason: '$causa');
        expect(find.textContaining('Cambiata'), findsNothing, reason: '$causa');
      }
    });
  });
}
