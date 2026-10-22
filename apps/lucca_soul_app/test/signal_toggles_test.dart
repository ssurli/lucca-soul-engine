import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/models/emotional_profile.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/meteo.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/util/signal_presets.dart';
import 'package:lucca_soul_app/util/signal_toggles.dart';
import 'package:lucca_soul_app/widgets/adaptive_card.dart';

const _p = SimulatedSignalKind.pioggia;
const _a = SimulatedSignalKind.affollamento;
const _s = SimulatedSignalKind.stanchezza;
const _json = {'content-type': 'application/json; charset=utf-8'};

ItineraryStop _stop(String id, String esito) => ItineraryStop(
      experienceId: id,
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 30,
      reason: 'm',
      esitoAdattamento: esito,
    );

Itinerary _it(List<ItineraryStop> stops) =>
    Itinerary(personId: 'p', stops: stops, generatedAt: DateTime.utc(2026, 1, 1));

final _originale = _it([
  ItineraryStop(experienceId: 'a', arrivo: TimeHms.parse('09:00:00'), durataMin: 30, reason: 'm'),
  ItineraryStop(experienceId: 'b', arrivo: TimeHms.parse('10:00:00'), durataMin: 30, reason: 'm'),
]);

const _profilo = EmotionalProfile(
  curiosita: 0.5,
  contemplazione: 0.5,
  arte: 0.5,
  conBambini: false,
  tempoDisponibileMin: 240,
);

void main() {
  group('stato interruttori (puro)', () {
    test('toggle: la seconda pressione spegne, non somma', () {
      final uno = const SignalToggleState().premi(_s);
      expect(uno.accesi, {_s});
      expect(uno.premi(_s).accesi, isEmpty);
    });

    test('Annulla ripristina lo stato precedente, passo per passo', () {
      final st = const SignalToggleState().premi(_p).premi(_s);
      expect(st.accesi, {_p, _s});
      expect(st.annulla().accesi, {_p});
      expect(st.annulla().annulla().accesi, isEmpty);
      expect(st.annulla().annulla().annulla().accesi, isEmpty); // niente storia: invariato
    });

    test('Torna al percorso iniziale spegne tutto e Annulla lo disfa', () {
      final st = const SignalToggleState().premi(_p).premi(_a).tornaAlPercorsoIniziale();
      expect(st.accesi, isEmpty);
      expect(st.annulla().accesi, {_p, _a});
    });
  });

  group('richiesta (pura, senza rete)', () {
    test('nessun interruttore acceso: nessuna richiesta', () {
      final st = const SignalToggleState().premi(_s).premi(_s);
      expect(richiestaDiAdattamento(accesi: st.accesi, originale: _originale, profilo: _profilo), isNull);
    });

    test('Piove + Sono stanco/a: una richiesta con entrambe le dimensioni, dall\'originale', () {
      final st = const SignalToggleState().premi(_p).premi(_s);
      final r = richiestaDiAdattamento(
        accesi: st.accesi,
        originale: _originale,
        profilo: _profilo,
        now: DateTime.utc(2026, 6, 1, 13),
      )!;
      expect(r.itinerary, same(_originale));
      expect(r.signal.meteo, Meteo.pioggia);
      expect(r.signal.stanchezza, 0.85);
      expect(r.signal.affollamento, isEmpty);
      expect(r.profile, isNotNull);
      expect(r.signal.istante, DateTime.utc(2026, 6, 1, 13));
    });

    test('Mura affollate applica la mappa dei luoghi affollati a 0.95', () {
      final r = richiestaDiAdattamento(accesi: {_a}, originale: _originale, profilo: null)!;
      expect(r.signal.affollamento, isNotEmpty);
      expect(r.signal.affollamento.values, everyElement(0.95));
      expect(r.signal.meteo, Meteo.sereno);
    });
  });

  group('senza effetto', () {
    test('tutte non_toccata, stessi id nello stesso ordine', () {
      final ad = _it([_stop('a', 'non_toccata'), _stop('b', 'non_toccata')]);
      expect(adattamentoSenzaEffetto(originale: _originale, adattato: ad), isTrue);
    });

    test('una sostituita, ordine diverso o mantenuta: ha effetto', () {
      bool senza(List<ItineraryStop> s) =>
          adattamentoSenzaEffetto(originale: _originale, adattato: _it(s));
      expect(senza([_stop('a', 'non_toccata'), _stop('c', 'sostituita')]), isFalse);
      expect(senza([_stop('b', 'non_toccata'), _stop('a', 'non_toccata')]), isFalse);
      expect(senza([_stop('a', 'mantenuta_senza_alternativa'), _stop('b', 'non_toccata')]), isFalse);
    });
  });

  group('card adattiva (widget, BFF finto)', () {
    final richieste = <Map<String, dynamic>>[];
    final shown = <Itinerary>[];

    Itinerary adattato() => _it([_stop('a', 'sostituita'), _stop('b', 'non_toccata')]);
    String corpo(Itinerary i) => jsonEncode(i.toJson());

    Future<void> monta(WidgetTester tester, Future<http.Response> Function(http.Request) handler) async {
      richieste.clear();
      shown.clear();
      final client = BffClient(
        baseUrl: Uri.parse('http://test'),
        httpClient: MockClient((req) {
          richieste.add(jsonDecode(utf8.decode(req.bodyBytes)) as Map<String, dynamic>);
          return handler(req);
        }),
      );
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: AdaptiveCard(
              bffClient: client,
              original: _originale,
              profile: _profilo,
              strings: AppStrings.forLanguages(['it']),
              onShown: shown.add,
            ),
          ),
        ),
      ),);
    }

    testWidgets('accendere e spegnere Sono stanco/a: torna all\'originale, nessuna nuova richiesta', (tester) async {
      await monta(tester, (_) async => http.Response(corpo(adattato()), 200, headers: _json));
      await tester.tap(find.text('Sono stanco/a'));
      await tester.pumpAndSettle();
      expect(richieste, hasLength(1));
      expect(richieste.single['signal']['stanchezza'], 0.85);
      expect(shown.last.stops.first.esitoAdattamento, 'sostituita');

      await tester.tap(find.text('Sono stanco/a')); // seconda pressione: spegne
      await tester.pumpAndSettle();
      expect(richieste, hasLength(1));
      expect(shown.last, same(_originale));
    });

    testWidgets('Piove + Sono stanco/a: richiesta combinata dall\'originale; Annulla ripristina', (tester) async {
      await monta(tester, (_) async => http.Response(corpo(adattato()), 200, headers: _json));
      await tester.tap(find.text('Piove'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Sono stanco/a'));
      await tester.pumpAndSettle();
      expect(richieste, hasLength(2));
      expect(richieste.last['signal']['meteo'], 'pioggia');
      expect(richieste.last['signal']['stanchezza'], 0.85);
      // L'itinerario inviato e' sempre l'originale: nessun esito di adattamento.
      final stops = richieste.last['itinerary']['stops'] as List<dynamic>;
      expect((stops.first as Map<String, dynamic>).containsKey('esito_adattamento'), isFalse);

      await tester.tap(find.text('Annulla')); // torna a solo pioggia
      await tester.pumpAndSettle();
      expect(richieste, hasLength(3));
      expect(richieste.last['signal']['meteo'], 'pioggia');
      expect(richieste.last['signal']['stanchezza'], 0.1);

      await tester.tap(find.text('Annulla')); // torna a nessuno: originale, nessuna richiesta
      await tester.pumpAndSettle();
      expect(richieste, hasLength(3));
      expect(shown.last, same(_originale));
    });

    testWidgets('adattamento che non tocca nulla: mostra la nota', (tester) async {
      final nulla = _it([_stop('a', 'non_toccata'), _stop('b', 'non_toccata')]);
      await monta(tester, (_) async => http.Response(corpo(nulla), 200, headers: _json));
      await tester.tap(find.text('Mura affollate'));
      await tester.pumpAndSettle();
      expect(find.text('Questo cambiamento non tocca il tuo percorso di oggi.'), findsOneWidget);
    });

    testWidgets('risposte fuori ordine: conta solo l\'ultimo stato richiesto', (tester) async {
      final risposte = <Completer<http.Response>>[];
      await monta(tester, (_) {
        final c = Completer<http.Response>();
        risposte.add(c);
        return c.future;
      });
      await tester.tap(find.text('Piove')); // richiesta 0
      await tester.pump();
      await tester.tap(find.text('Sono stanco/a')); // richiesta 1
      await tester.pump();
      expect(risposte, hasLength(2));
      final ultimo = _it([_stop('a', 'non_toccata'), _stop('b', 'sostituita')]);
      risposte[1].complete(http.Response(corpo(ultimo), 200, headers: _json)); // arriva prima la nuova
      await tester.pumpAndSettle();
      risposte[0].complete(http.Response(corpo(adattato()), 200, headers: _json)); // poi la vecchia
      await tester.pumpAndSettle();
      expect(shown, hasLength(1));
      expect(shown.single.stops.last.esitoAdattamento, 'sostituita');
      expect(shown.single.stops.first.esitoAdattamento, 'non_toccata');
    });
  });
}
