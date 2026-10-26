// Direzione C: contrasti dei token, layout a 390 px e su schermo largo,
// riepilogo del cambio, nessun prezzo nelle stringhe.
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
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
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/util/clock.dart';
import 'package:lucca_soul_app/util/riepilogo_cambio.dart';
import 'package:lucca_soul_app/widgets/adaptive_card.dart';
import 'package:lucca_soul_app/widgets/mura_logo.dart';

const _json = {'content-type': 'application/json; charset=utf-8'};
final _it = AppStrings.forLanguages(['it']);

ItineraryStop _stop(
  String id, {
  String? esito,
  Punto? punto,
  String titolo = 'Passeggiata sulle Mura',
}) =>
    ItineraryStop(
      experienceId: id,
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 60,
      reason: 'Perché ti piace camminare e perderti tra le vie.',
      titolo: titolo,
      esitoAdattamento: esito,
      puntoArrivo: punto,
    );

Itinerary _itin(List<ItineraryStop> stops, {List<TappaEsclusa> escluse = const []}) => Itinerary(
      personId: 'p',
      stops: stops,
      generatedAt: DateTime.utc(2026, 12, 12, 9),
      tappeEscluse: escluse,
    );

const _profilo = EmotionalProfile(
  curiosita: 0.5,
  contemplazione: 0.5,
  arte: 0.5,
  conBambini: false,
  tempoDisponibileMin: 240,
);

Future<void> _montaSchermata(WidgetTester tester, Size size) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final itinerario = _itin([
    _stop('a', punto: const Punto(lat: 43.84, lon: 10.5)),
    _stop('b', esito: 'sostituita', titolo: 'Laboratorio al chiuso'),
    _stop('c', esito: 'mantenuta_senza_alternativa'),
  ]);
  final client = BffClient(
    baseUrl: Uri.parse('http://test'),
    httpClient: MockClient((_) async => http.Response(jsonEncode(itinerario.toJson()), 200, headers: _json)),
  );
  Orologio.impostaPerTest(() => DateTime.utc(2026, 12, 12, 9));
  addTearDown(() => Orologio.impostaPerTest(null));
  await tester.pumpWidget(
    MaterialApp(
      theme: buildAppTheme(),
      home: ItineraryScreen(bffClient: client, personId: 'p', profile: _profilo),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  group('contrasto WCAG dei token', () {
    void atteso(Color a, Color b, double valore) =>
        expect(rapportoContrasto(a, b), closeTo(valore, 0.1), reason: '$a su $b');

    test('coppie dichiarate dal committente', () {
      atteso(Tk.testo, Tk.sfondo, 13.2);
      atteso(Tk.testo, Tk.cardSfondo, 14.5);
      atteso(Tk.testoSecondario, Tk.sfondo, 6.6);
      atteso(Tk.testoSecondario, Tk.cardSfondo, 7.2);
      atteso(Tk.accento, Tk.sfondo, 5.3);
      atteso(Tk.accento, Tk.cardSfondo, 5.8);
      atteso(Tk.testoSuAccento, Tk.accento, 5.9);
      atteso(Tk.accento, Tk.avviso, 4.6);
      atteso(Tk.sostituitaTesto, Tk.sostituitaSfondo, 6.6);
      atteso(Tk.mantenutaTesto, Tk.mantenutaSfondo, 11.6);
      atteso(Tk.testoSuTestata, Tk.testata, 13.2);
    });

    test('ogni coppia testo/sfondo del tema è >= 4,5', () {
      for (final c in kCoppieTestoSfondo) {
        expect(rapportoContrasto(c.testo, c.sfondo), greaterThanOrEqualTo(4.5), reason: c.nome);
      }
    });

    test('il mattone non sta mai sulla testata scura', () {
      expect(rapportoContrasto(Tk.accento, Tk.testata), lessThan(3));
      expect(
        kCoppieTestoSfondo.where((c) => c.sfondo == Tk.testata && c.testo == Tk.accento),
        isEmpty,
      );
    });

    test('il grigio #6B7A80 non è colore di testo nel tema', () {
      final tema = buildAppTheme();
      final colori = <Color?>[
        for (final s in [
          tema.textTheme.displayLarge,
          tema.textTheme.displayMedium,
          tema.textTheme.displaySmall,
          tema.textTheme.headlineLarge,
          tema.textTheme.headlineMedium,
          tema.textTheme.headlineSmall,
          tema.textTheme.titleLarge,
          tema.textTheme.titleMedium,
          tema.textTheme.titleSmall,
          tema.textTheme.bodyLarge,
          tema.textTheme.bodyMedium,
          tema.textTheme.bodySmall,
          tema.textTheme.labelLarge,
          tema.textTheme.labelMedium,
          tema.textTheme.labelSmall,
          tema.appBarTheme.titleTextStyle,
          tema.snackBarTheme.contentTextStyle,
        ])
          s?.color,
        tema.colorScheme.onSurface,
        tema.colorScheme.onSurfaceVariant,
        tema.colorScheme.onPrimary,
        tema.colorScheme.onSecondary,
        tema.colorScheme.onError,
      ];
      expect(colori, isNot(contains(Tk.grigioNonTestuale)));
    });

    test('il grigio compare nel sorgente solo nel file dei token', () {
      for (final f in Directory('lib').listSync(recursive: true).whereType<File>()) {
        if (!f.path.endsWith('.dart') || f.path.endsWith('tokens.dart')) continue;
        expect(f.readAsStringSync().toUpperCase(), isNot(contains('6B7A80')), reason: f.path);
      }
    });
  });

  group('schermata a 390x844', () {
    testWidgets('nessun overflow, nessuno scorrimento orizzontale, testata col logo', (tester) async {
      final semantica = tester.ensureSemantics();
      await _montaSchermata(tester, const Size(390, 844));
      expect(tester.takeException(), isNull);
      // Nessuno Scrollable orizzontale.
      for (final s in tester.widgetList<Scrollable>(find.byType(Scrollable))) {
        expect(s.axisDirection, anyOf(AxisDirection.down, AxisDirection.up));
      }
      expect(find.bySemanticsLabel('Le Mura di Lucca: dieci baluardi e una piattaforma'), findsOneWidget);
      expect(find.text('Lucca Soul'), findsOneWidget);
      expect(find.textContaining('3 tappe'), findsOneWidget);
      expect(find.textContaining('a piedi'), findsOneWidget);
      expect(find.byType(MuraLogo), findsOneWidget);
      semantica.dispose();
    });

    testWidgets('interruttori e "Come arrivo qui" alti almeno 44 px', (tester) async {
      await _montaSchermata(tester, const Size(390, 844));
      final interruttori = find.byType(InterruttoreSegnale);
      expect(interruttori, findsNWidgets(3));
      for (var i = 0; i < 3; i++) {
        expect(tester.getSize(interruttori.at(i)).height, greaterThanOrEqualTo(44));
      }
      final come = find.widgetWithText(TextButton, 'Come arrivo qui');
      expect(come, findsOneWidget);
      expect(tester.getSize(come).height, greaterThanOrEqualTo(44));
    });

    testWidgets('etichette dell\'esito solo dove c\'è un esito; numeri nell\'ordine', (tester) async {
      await _montaSchermata(tester, const Size(390, 2400));
      expect(find.byType(EtichettaEsito, skipOffstage: false), findsNWidgets(2));
      expect(find.text('Cambiata dal segnale'), findsOneWidget);
      for (final n in ['1', '2', '3']) {
        expect(find.text(n, skipOffstage: false), findsOneWidget);
      }
    });
  });

  testWidgets('schermo largo: colonna centrata di al massimo 600 px', (tester) async {
    await _montaSchermata(tester, const Size(1400, 900));
    expect(tester.takeException(), isNull);
    final card = find.byType(StopCard).first;
    final r = tester.getRect(card);
    expect(r.width, lessThanOrEqualTo(600));
    expect(r.center.dx, closeTo(700, 1));
  });

  group('riepilogo del cambio dagli esiti', () {
    final originale = _itin([_stop('a'), _stop('b'), _stop('c')]);

    test('sostituite + mantenute', () {
      final adattato = _itin([
        _stop('a2', esito: 'sostituita'),
        _stop('b2', esito: 'sostituita'),
        _stop('c', esito: 'mantenuta_senza_alternativa'),
      ]);
      expect(
        riepilogoCambio(segnali: ['Piove'], adattato: adattato, originale: originale, strings: _it),
        'Piove: 2 tappe cambiate, 1 resta in programma.',
      );
    });

    test('tappe tolte contate solo se nuove rispetto all\'originale', () {
      const nuova = TappaEsclusa(experienceId: 'x', esito: 'esclusa', reason: 'r');
      const vecchia = TappaEsclusa(experienceId: 'y', esito: 'esclusa', reason: 'r');
      final orig = _itin([_stop('a')], escluse: const [vecchia]);
      final adattato = _itin([_stop('a')], escluse: const [vecchia, nuova]);
      expect(
        riepilogoCambio(segnali: ['Piove', 'Sono stanco/a'], adattato: adattato, originale: orig, strings: _it),
        'Piove, Sono stanco/a: 1 tappa tolta.',
      );
    });

    test('nulla di cambiato e inglese', () {
      final adattato = _itin([_stop('a', esito: 'non_toccata')]);
      expect(
        riepilogoCambio(segnali: ['Piove'], adattato: adattato, originale: originale, strings: _it),
        'Piove: nessuna tappa cambiata.',
      );
      final en = AppStrings.forLanguages(['en']);
      final a2 = _itin([_stop('a', esito: 'sostituita'), _stop('b', esito: 'mantenuta_senza_alternativa')]);
      expect(
        riepilogoCambio(segnali: ['It is raining'], adattato: a2, originale: originale, strings: en),
        'It is raining: 1 stop changed, 1 stays in plan.',
      );
    });

    test('fascia oraria della giornata', () {
      expect(fasciaOrariaGiornata(const []), isNull);
      expect(fasciaOrariaGiornata([_stop('a'), _stop('b')]), '09:00–10:00');
    });
  });

  testWidgets('la fascia di riepilogo compare dopo un cambio, con Annulla', (tester) async {
    final originale = _itin([_stop('a'), _stop('b')]);
    final adattato = _itin([_stop('a', esito: 'sostituita'), _stop('b', esito: 'mantenuta_senza_alternativa')]);
    final client = BffClient(
      baseUrl: Uri.parse('http://test'),
      httpClient: MockClient((_) async => http.Response(jsonEncode(adattato.toJson()), 200, headers: _json)),
    );
    await tester.pumpWidget(
      MaterialApp(
        theme: buildAppTheme(),
        home: Scaffold(
          body: SingleChildScrollView(
            child: AdaptiveCard(
              bffClient: client,
              original: originale,
              profile: _profilo,
              strings: _it,
              onShown: (_) {},
            ),
          ),
        ),
      ),
    );
    expect(find.text('Annulla'), findsNothing);
    await tester.tap(find.text('Piove'));
    await tester.pumpAndSettle();
    expect(find.text('Piove: 1 tappa cambiata, 1 resta in programma.'), findsOneWidget);
    expect(find.text('Annulla'), findsOneWidget);
    expect(find.text('Torna al percorso iniziale'), findsOneWidget);
  });

  test('nessun "gratis", "gratuit" o "€" nelle stringhe dell\'app', () {
    final vietato = RegExp('gratis|gratuit|€|euro', caseSensitive: false);
    for (final f in Directory('lib').listSync(recursive: true).whereType<File>()) {
      if (!f.path.endsWith('.dart')) continue;
      expect(vietato.hasMatch(f.readAsStringSync()), isFalse, reason: f.path);
    }
  });
}
