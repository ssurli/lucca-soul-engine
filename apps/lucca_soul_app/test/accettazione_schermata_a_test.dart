// Accettazione schermata A. Dati ricopiati dal golden
// services/api/tests/golden/lucca_itinerari.json, chiave `demo|curioso|pioggia-15`
// (richiesta.itinerary = iniziale, atteso = adattato con la pioggia).
// Nel golden l'adattato non ha `titolo` ne' `punto_arrivo` per le tappe
// sostituite: i loro titoli vengono da services/graph/graph/seed_lucca.py
// (sola lettura) e non hanno punto sulla mappa.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/models/emotional_profile.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/theme/app_theme.dart';
import 'package:lucca_soul_app/widgets/mappa_itinerario.dart';

class _TileKo extends TileProvider {
  @override
  ImageProvider getImage(TileCoordinates coordinates, TileLayer options) =>
      MemoryImage(Uint8List(0));
}

const _json = {'content-type': 'application/json; charset=utf-8'};

const _profilo = EmotionalProfile(
  curiosita: 0.75,
  contemplazione: 0.5,
  arte: 0.5,
  conBambini: false,
  tempoDisponibileMin: 180,
  lingue: ['it'],
);

ItineraryStop _t(String id, String titolo, String arrivo, int durata, String reason,
        {String? esito, Punto? p,}) =>
    ItineraryStop(
      experienceId: id,
      titolo: titolo,
      arrivo: TimeHms.parse(arrivo),
      durataMin: durata,
      reason: reason,
      esitoAdattamento: esito,
      puntoArrivo: p,
    );

const _pFrediano = Punto(lat: 43.84611439494372, lon: 10.504828564629559);
const _pReparata = Punto(lat: 43.84119039780105, lon: 10.504274232740409);
const _pMichele = Punto(lat: 43.843206920716746, lon: 10.502521515682991);
const _pPaolino = Punto(lat: 43.840816169243126, lon: 10.496989849819938);
const _pDuomo = Punto(lat: 43.8407348442907, lon: 10.50546424867784);

final _iniziale = Itinerary(
  personId: 'golden-curioso',
  generatedAt: DateTime.utc(2026, 12, 12, 15),
  stops: [
    _t('exp-facciata-san-michele', 'La facciata scolpita di San Michele in Foro', '15:00:00', 25,
        'Hai voglia di perderti e lasciarti sorprendere. All\'aperto.',
        p: const Punto(lat: 43.843206920716746, lon: 10.502521515682991),),
    _t('exp-interno-san-frediano', 'La basilica di San Frediano e il fonte lustrale', '15:31:00', 30,
        'Temi: romanico, arte, medioevo. Al chiuso.', p: _pFrediano,),
    _t('exp-solchi-san-pietro-somaldi', 'I solchi sulla porta di San Pietro Somaldi', '16:06:00', 10,
        'Temi: storia, romanico. All\'aperto.',
        p: const Punto(lat: 43.84555613789234, lon: 10.508002871124265),),
    _t('exp-santi-giovanni-reparata', 'La chiesa dei Santi Giovanni e Reparata e l\'area archeologica',
        '16:26:00', 40, 'Temi: storia, arte, romanico. Al chiuso.', p: _pReparata,),
    _t('exp-duomo-volto-santo', 'Il Volto Santo e il labirinto del Duomo', '17:08:00', 35,
        'Luigi Boccherini debuttò come voce bianca in questa cattedrale. Al chiuso.', p: _pDuomo,),
  ],
);

final _adattato = Itinerary(
  personId: 'golden-curioso',
  generatedAt: DateTime.utc(2026, 12, 12, 15),
  adattatoDaSegnale: true,
  stops: [
    _t('exp-interno-san-michele', 'L\'interno di San Michele in Foro', '15:00:00', 20,
        'Sostituita per la pioggia. Hai voglia di perderti e lasciarti sorprendere. Al chiuso.',
        esito: 'sostituita', p: _pMichele,),
    _t('exp-interno-san-frediano', 'La basilica di San Frediano e il fonte lustrale', '15:26:00', 30,
        'Temi: romanico, arte, medioevo. Al chiuso.', esito: 'non_toccata', p: _pFrediano,),
    _t('exp-sortita-san-paolino', 'La sortita sotterranea del Baluardo San Paolino', '16:10:00', 20,
        'Sostituita per la pioggia. Temi: storia. Al chiuso.', esito: 'sostituita', p: _pPaolino,),
    _t('exp-santi-giovanni-reparata', 'La chiesa dei Santi Giovanni e Reparata e l\'area archeologica',
        '16:40:00', 40, 'Temi: storia, arte, romanico. Al chiuso.', esito: 'non_toccata', p: _pReparata,),
    _t('exp-duomo-volto-santo', 'Il Volto Santo e il labirinto del Duomo', '17:22:00', 35,
        'Luigi Boccherini debuttò come voce bianca in questa cattedrale. Al chiuso.',
        esito: 'non_toccata', p: _pDuomo,),
  ],
);

Future<void> _monta(WidgetTester t, Size size) async {
  t.view.physicalSize = size;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final client = BffClient(
    baseUrl: Uri.parse('http://test'),
    httpClient: MockClient((r) async {
      final it = r.url.path.endsWith('/adapt') ? _adattato : _iniziale;
      return http.Response(jsonEncode(it.toJson()), 200, headers: _json);
    }),
  );
  await t.pumpWidget(MaterialApp(
    theme: buildAppTheme(),
    home: ItineraryScreen(
      bffClient: client,
      personId: 'golden-curioso',
      profile: _profilo,
      tileProvider: _TileKo(),
    ),
  ),);
  await t.pumpAndSettle();
}

Future<void> _accendiPiove(WidgetTester t) async {
  await t.tap(find.text('Piove'));
  await t.pumpAndSettle();
}

Finder _segnaposto(int n) => find.byWidgetPredicate((w) => w is Segnaposto && w.numero == n);

bool _orizzontale(WidgetTester t) => find.byType(Scrollable).evaluate().any((e) {
      final d = (e.widget as Scrollable).axisDirection;
      return d == AxisDirection.left || d == AxisDirection.right;
    });

void main() {
  setUpAll(() async {
    final n = FontLoader('NunitoSans')
      ..addFont(rootBundle.load('assets/fonts/nunitosans/NunitoSans-Variable.ttf'));
    await n.load();
    final d = FontLoader('Domine')
      ..addFont(rootBundle.load('assets/fonts/domine/Domine-Variable.ttf'));
    await d.load();
  });

  testWidgets('1. 390x844: dopo Piove, senza scorrere, il titolo della prima tappa e\' tutto in vista',
      (t) async {
    await _monta(t, const Size(390, 844));
    await _accendiPiove(t);
    expect(t.takeException(), isNull);
    final titolo = find.text('L\'interno di San Michele in Foro');
    expect(titolo, findsOneWidget);
    final r = t.getRect(titolo);
    // ignore: avoid_print
    print('MISURA titolo prima tappa: $r');
    expect(r.top, greaterThanOrEqualTo(0));
    expect(r.bottom, lessThanOrEqualTo(844));
    expect(r.left, greaterThanOrEqualTo(0));
    expect(r.right, lessThanOrEqualTo(390));
    // non coperto da altro: il tocco al centro del titolo lo raggiunge
    expect(titolo.hitTestable(), findsOneWidget);
    // tutte le Scrollable verticali a offset 0
    final verticali = find.byType(Scrollable).evaluate().where((e) {
      final d = (e.widget as Scrollable).axisDirection;
      return d == AxisDirection.down || d == AxisDirection.up;
    });
    expect(verticali, isNotEmpty);
    for (final e in verticali) {
      expect(((e as StatefulElement).state as ScrollableState).position.pixels, 0);
    }
  });

  for (final dopo in [false, true]) {
    testWidgets('2. 360x800 ${dopo ? "dopo" : "prima di"} Piove: nessun overflow, nessuno scorrimento orizzontale',
        (t) async {
      await _monta(t, const Size(360, 800));
      expect(t.takeException(), isNull);
      if (dopo) {
        await _accendiPiove(t);
        expect(find.text('L\'interno di San Michele in Foro'), findsOneWidget);
      }
      expect(t.takeException(), isNull);
      expect(_orizzontale(t), isFalse);
    });
  }

  testWidgets('3. tocco sul segnaposto 3: tappa 3 aperta e visibile (itinerario iniziale)', (t) async {
    await _monta(t, const Size(390, 844));
    expect(_segnaposto(3), findsOneWidget);
    const motivo = 'Temi: storia, romanico. All\'aperto.';
    expect(find.text(motivo), findsNothing);
    await t.tap(_segnaposto(3));
    await t.pumpAndSettle();
    expect(t.takeException(), isNull);
    final card = find.ancestor(
        of: find.text('I solchi sulla porta di San Pietro Somaldi'), matching: find.byType(StopCard),);
    expect(card, findsOneWidget);
    expect(t.widget<StopCard>(card).aperta, isTrue);
    expect(find.text(motivo), findsOneWidget);
    final vista = t.getRect(find.byType(RefreshIndicator));
    final rc = t.getRect(card);
    final rm = t.getRect(find.text(motivo));
    // ignore: avoid_print
    print('MISURA tappa 3: card $rc, vista $vista, motivo $rm');
    expect(rc.top, greaterThanOrEqualTo(vista.top - 0.5));
    expect(rc.bottom, lessThanOrEqualTo(vista.bottom + 0.5));
    expect(rm.bottom, lessThanOrEqualTo(vista.bottom + 0.5));
  });

  testWidgets('3. tocco sul segnaposto 3: tappa 3 aperta e visibile (adattato con Piove)', (t) async {
    await _monta(t, const Size(390, 844));
    await _accendiPiove(t);
    expect(_segnaposto(3), findsOneWidget);
    const motivo = 'Sostituita per la pioggia. Temi: storia. Al chiuso.';
    expect(find.text(motivo), findsNothing);
    await t.tap(_segnaposto(3));
    await t.pumpAndSettle();
    expect(t.takeException(), isNull);
    final card = find.ancestor(
        of: find.text('La sortita sotterranea del Baluardo San Paolino'), matching: find.byType(StopCard),);
    expect(card, findsOneWidget);
    expect(t.widget<StopCard>(card).aperta, isTrue);
    expect(find.text(motivo), findsOneWidget);
    final vista = t.getRect(find.byType(RefreshIndicator));
    final rc = t.getRect(card);
    final rm = t.getRect(find.text(motivo));
    // ignore: avoid_print
    print('MISURA tappa 3 adattato: card $rc, vista $vista, motivo $rm');
    expect(rc.top, greaterThanOrEqualTo(vista.top - 0.5));
    expect(rc.bottom, lessThanOrEqualTo(vista.bottom + 0.5));
    expect(rm.bottom, lessThanOrEqualTo(vista.bottom + 0.5));
  });
}
