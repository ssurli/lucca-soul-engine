import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/theme/app_theme.dart';
import 'package:lucca_soul_app/theme/tokens.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/util/minuti_a_piedi.dart';

const _punto = Punto(lat: 43.84, lon: 10.5);

ItineraryStop _stop({
  String id = 'a',
  int ora = 15,
  int min = 0,
  int durata = 20,
  String? titolo = 'Torre Guinigi',
  Punto? punto = _punto,
}) =>
    ItineraryStop(
      experienceId: id,
      arrivo: TimeHms(hour: ora, minute: min),
      durataMin: durata,
      reason: 'Perché è un panorama sui tetti.',
      titolo: titolo,
      puntoArrivo: punto,
      curiosita: const [
        Curiosita(
          testo: 'Sulla cima crescono delle querce.',
          tipo: CuriosityKind.fatto,
          fonte: 'Archivio storico',
          fontePubblica: true,
        ),
      ],
    );

Future<void> _monta(WidgetTester t, Widget child, {Size size = const Size(390, 844)}) async {
  t.view.physicalSize = size;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(MaterialApp(
    theme: buildAppTheme(),
    home: Scaffold(body: SingleChildScrollView(child: child)),
  ),);
  await t.pump();
}

StopCard _card(
  ItineraryStop s, {
  AppStrings? strings,
  bool evidenziata = false,
  bool mantenuta = false,
  int? minuti,
  int numero = 1,
}) =>
    StopCard(
      stop: s,
      evidenziata: evidenziata,
      mantenutaSenzaAlternativa: mantenuta,
      strings: strings ?? AppStrings.forLanguages(['it']),
      onLasciaRicordo: () {},
      numero: numero,
      conLinea: true,
      minutiAllaProssima: minuti,
    );

void main() {
  group('minutiAPiedi (funzione pura)', () {
    test('entrambi i punti: arrivo[n+1] - (arrivo[n] + durata[n])', () {
      final a = _stop(ora: 15, durata: 20);
      final b = _stop(ora: 15, min: 35);
      expect(minutiAPiedi(a, b), 15);
    });

    test('un punto mancante (primo o secondo): nessuna riga', () {
      final con = _stop(ora: 15, durata: 20);
      final senza = _stop(ora: 16, punto: null);
      expect(minutiAPiedi(con, senza), isNull);
      expect(minutiAPiedi(senza, con), isNull);
      expect(minutiAPiedi(senza, senza), isNull);
    });

    test('N <= 0: nessuna riga (zero e negativo)', () {
      expect(minutiAPiedi(_stop(ora: 15, durata: 20), _stop(ora: 15, min: 20)), isNull);
      expect(minutiAPiedi(_stop(ora: 15, durata: 20), _stop(ora: 15, min: 10)), isNull);
    });

    test('passaggio della mezzanotte: nessuna riga', () {
      expect(minutiAPiedi(_stop(ora: 23, min: 50, durata: 30), _stop(ora: 0, min: 10)), isNull);
    });
  });

  group('riga chiusa e aperta', () {
    testWidgets('chiusa: numero, ora·durata, titolo, esito, freccia; NON il motivo', (t) async {
      await _monta(t, _card(_stop(), evidenziata: true));
      expect(find.text('1'), findsOneWidget);
      expect(find.text('15:00 · 20 min'), findsOneWidget);
      expect(find.text('Torre Guinigi'), findsOneWidget);
      expect(find.text('Cambiata dal segnale'), findsOneWidget);
      expect(find.byIcon(Icons.expand_more), findsOneWidget);
      expect(find.text('Perché è un panorama sui tetti.'), findsNothing);
      expect(find.text('Come arrivo qui'), findsNothing);
      expect(find.text('Lascia un ricordo'), findsNothing);
      // ordine nella riga: numero | ora · durata, titolo
      final ora = t.getRect(find.text('15:00 · 20 min'));
      final titolo = t.getRect(find.text('Torre Guinigi'));
      expect(t.getRect(find.text('1')).right, lessThanOrEqualTo(ora.left));
      expect(ora.bottom, lessThanOrEqualTo(titolo.top));
      expect(t.getSize(find.byType(InkWell)).height, greaterThanOrEqualTo(44));
    });

    testWidgets('esito "resta in programma" nella riga chiusa', (t) async {
      await _monta(t, _card(_stop(), mantenuta: true));
      expect(find.text('Resta in programma: nessuna alternativa adatta'), findsOneWidget);
    });

    testWidgets('tocco apre (motivo, curiosita con fonte, link, ricordo); secondo tocco chiude', (t) async {
      await _monta(t, _card(_stop()));
      await t.tap(find.text('Torre Guinigi'));
      await t.pumpAndSettle();
      expect(find.text('Perché è un panorama sui tetti.'), findsOneWidget);
      expect(find.text('Sulla cima crescono delle querce.'), findsOneWidget);
      expect(find.text('Fonte: Archivio storico'), findsOneWidget);
      expect(find.text('Come arrivo qui'), findsOneWidget);
      expect(find.text('Lascia un ricordo'), findsOneWidget);
      // ordine del contenuto aperto
      final motivo = t.getRect(find.text('Perché è un panorama sui tetti.'));
      final cur = t.getRect(find.text('Sulla cima crescono delle querce.'));
      final come = t.getRect(find.text('Come arrivo qui'));
      final ricordo = t.getRect(find.text('Lascia un ricordo'));
      expect(t.getRect(find.text('Torre Guinigi')).bottom, lessThanOrEqualTo(motivo.top));
      expect(motivo.bottom, lessThanOrEqualTo(cur.top));
      expect(cur.bottom, lessThanOrEqualTo(come.top));
      expect(come.bottom, lessThanOrEqualTo(ricordo.top));

      await t.tap(find.text('15:00 · 20 min')); // tocco su un altro punto della riga
      await t.pumpAndSettle();
      expect(find.text('Perché è un panorama sui tetti.'), findsNothing);
      expect(find.text('Lascia un ricordo'), findsNothing);
    });

    testWidgets('semantica: aperto/chiuso annunciato (expanded)', (t) async {
      final sem = t.ensureSemantics();
      await _monta(t, _card(_stop()));
      bool? espansa() {
        final s = t
            .widgetList<Semantics>(find.descendant(of: find.byType(StopCard), matching: find.byType(Semantics)))
            .where((w) => w.properties.expanded != null);
        expect(s, hasLength(1));
        return s.single.properties.expanded;
      }

      expect(espansa(), isFalse);
      await t.tap(find.text('Torre Guinigi'));
      await t.pumpAndSettle();
      expect(espansa(), isTrue);
      await t.tap(find.text('Torre Guinigi'));
      await t.pumpAndSettle();
      expect(espansa(), isFalse);
      sem.dispose();
    });

    testWidgets('controllo esterno: aperta + onToggle comandano lo stato', (t) async {
      var aperta = false;
      late StateSetter ricostruisci;
      await _monta(
        t,
        StatefulBuilder(builder: (context, setState) {
          ricostruisci = setState;
          return StopCard(
            stop: _stop(),
            evidenziata: false,
            strings: AppStrings.forLanguages(['it']),
            onLasciaRicordo: () {},
            numero: 1,
            aperta: aperta,
            onToggle: () => ricostruisci(() => aperta = !aperta),
          );
        },),
      );
      expect(find.text('Lascia un ricordo'), findsNothing);
      ricostruisci(() => aperta = true); // come farebbe un tocco sulla mappa
      await t.pumpAndSettle();
      expect(find.text('Lascia un ricordo'), findsOneWidget);
      await t.tap(find.text('Torre Guinigi'));
      await t.pumpAndSettle();
      expect(find.text('Lascia un ricordo'), findsNothing);
    });
  });

  group('riga "circa N min a piedi"', () {
    testWidgets('presente con minuti (it e en), 13/600 secondario; assente senza', (t) async {
      await _monta(t, _card(_stop(), minuti: 15));
      expect(find.text('circa 15 min a piedi'), findsOneWidget);
      final stile = t.widget<Text>(find.text('circa 15 min a piedi')).style!;
      expect(stile.fontSize, 13);
      expect(stile.fontWeight, FontWeight.w600);
      expect(stile.color, Tk.testoSecondario);
      // sotto la tappa, nella colonna di destra (allineata al titolo)
      expect(t.getRect(find.text('circa 15 min a piedi')).left, t.getRect(find.text('Torre Guinigi')).left);

      await _monta(t, _card(_stop(), minuti: 7, strings: AppStrings.forLanguages(['en'])));
      expect(find.text('about 7 min on foot'), findsOneWidget);

      await _monta(t, _card(_stop()));
      expect(find.textContaining('a piedi'), findsNothing);
      expect(find.textContaining('on foot'), findsNothing);
    });

    testWidgets('con la funzione pura: solo se entrambe le tappe hanno il punto', (t) async {
      final a = _stop(ora: 15, durata: 20);
      final b = _stop(ora: 15, min: 40);
      final c = _stop(ora: 16, punto: null);
      await _monta(
        t,
        Column(children: [
          _card(a, minuti: minutiAPiedi(a, b)),
          _card(b, numero: 2, minuti: minutiAPiedi(b, c)),
          _card(c, numero: 3),
        ],),
      );
      expect(find.text('circa 20 min a piedi'), findsOneWidget);
      expect(find.textContaining('a piedi'), findsOneWidget);
    });
  });

  group('larghezza stretta', () {
    for (final w in [360.0, 390.0]) {
      testWidgets('${w.toInt()} px con titolo lungo: a capo, nessun overflow, riga aperta e chiusa', (t) async {
        const lungo = 'Passeggiata panoramica lungo le Mura rinascimentali e i bastioni di San Paolino';
        await _monta(
          t,
          _card(_stop(titolo: lungo), evidenziata: true, minuti: 12),
          size: Size(w, 800),
        );
        expect(t.takeException(), isNull);
        expect(find.text(lungo), findsOneWidget);
        expect(t.widget<Text>(find.text(lungo)).overflow, isNot(TextOverflow.ellipsis));
        expect(t.getSize(find.text(lungo)).height, greaterThan(40)); // a capo su piu' righe
        await t.tap(find.text(lungo));
        await t.pumpAndSettle();
        expect(t.takeException(), isNull);
        for (final e in find.byType(Text).evaluate()) {
          final r = e.renderObject! as RenderBox;
          expect(r.localToGlobal(Offset(r.size.width, 0)).dx, lessThanOrEqualTo(w + 0.5), reason: '${(e.widget as Text).data}');
        }
      });
    }
  });
}
