// Coerenza tra interruttori dei segnali, fascia di riepilogo e itinerario
// mostrato (schermata completa). Nessuna rete: BffClient finto che conta le
// chiamate e lascia decidere al test QUANDO e in che ordine rispondono; tile
// provider finto; archivio foto iniettato.
//
// L'invariante: l'interruttore acceso <=> l'itinerario mostrato e' quello
// adattato <=> c'e' la fascia di riepilogo del segnale. Nessuna ipotesi sulla
// causa: i test decidono.
import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/models/adapt_request.dart';
import 'package:lucca_soul_app/models/emotional_profile.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/meteo.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/models/visitor_context.dart';
import 'package:lucca_soul_app/screens/itinerary_screen.dart';
import 'package:lucca_soul_app/theme/app_theme.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/util/clock.dart';
import 'package:lucca_soul_app/util/foto_tappa.dart';
import 'package:lucca_soul_app/widgets/adaptive_card.dart';

class _TileKo extends TileProvider {
  @override
  ImageProvider getImage(TileCoordinates coordinates, TileLayer options) =>
      MemoryImage(Uint8List(0));
}

const _profilo = EmotionalProfile(
  curiosita: 0.5,
  contemplazione: 0.5,
  arte: 0.5,
  conBambini: false,
  tempoDisponibileMin: 240,
);

final _it = AppStrings.forLanguages(['it']);

const _nTappe = 40;

Itinerary _costruisci(String prefisso, {required bool adattato}) => Itinerary(
      personId: 'p',
      generatedAt: DateTime.utc(2026, 12, 12, 9),
      adattatoDaSegnale: adattato,
      stops: [
        for (var i = 0; i < _nTappe; i++)
          ItineraryStop(
            experienceId: '$prefisso-$i',
            arrivo: TimeHms.parse('09:00:00'),
            durataMin: 30,
            titolo: '$prefisso $i',
            reason: 'Motivo della tappa $i: ${'lungo ' * 12}',
            esitoAdattamento: adattato && i < 3 ? 'sostituita' : null,
            puntoArrivo:
                i < 5 ? Punto(lat: 43.84 + i / 1000, lon: 10.50 + i / 1000) : null,
          ),
      ],
    );

/// BFF finto: conta le chiamate; `adapt` risponde solo quando lo decide il test.
class FakeBff extends BffClient {
  FakeBff() : super(baseUrl: Uri.parse('http://test'));

  int chiamateItinerary = 0;
  final List<VisitorContext> contesti = [];
  final List<AdaptRequest> richieste = [];
  final List<Completer<Itinerary>> pendenti = [];

  int get chiamateAdapt => richieste.length;

  @override
  Future<Itinerary> itinerary(VisitorContext context) async {
    chiamateItinerary++;
    contesti.add(context);
    // Un'istanza NUOVA a ogni chiamata, come la rete vera.
    return _costruisci('Originale', adattato: false);
  }

  @override
  Future<Itinerary> adaptItinerary(AdaptRequest request) {
    richieste.add(request);
    final c = Completer<Itinerary>();
    pendenti.add(c);
    return c.future;
  }

  /// Risponde alla richiesta numero [i] (0-based) con un adattamento "Adattata<i>".
  void rispondi(int i) =>
      pendenti[i].complete(_costruisci('Adattata$i', adattato: true));
}

Future<void> _monta(WidgetTester t, FakeBff bff,
    {Size size = const Size(390, 844),}) async {
  t.view.physicalSize = size;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  Orologio.impostaPerTest(() => DateTime.utc(2026, 12, 12, 9));
  addTearDown(() => Orologio.impostaPerTest(null));
  await t.pumpWidget(
    MaterialApp(
      theme: buildAppTheme(),
      home: ItineraryScreen(
        bffClient: bff,
        personId: 'p',
        profile: _profilo,
        tileProvider: _TileKo(),
        archivioFoto: const ArchivioFoto(),
      ),
    ),
  );
  await t.pump();
  await t.pump(const Duration(milliseconds: 300));
}

Finder _interruttore(String etichetta) =>
    find.widgetWithText(InterruttoreSegnale, etichetta);

bool _acceso(WidgetTester t, String etichetta) =>
    t.widget<InterruttoreSegnale>(_interruttore(etichetta)).acceso;

Future<void> _premi(WidgetTester t, String etichetta) async {
  await t.tap(_interruttore(etichetta));
  await t.pump();
}

ScrollableState _scorrimentoLista(WidgetTester t) => t.state<ScrollableState>(
      find
          .descendant(of: find.byType(ListView), matching: find.byType(Scrollable))
          .first,
    );

Future<void> _pompa(WidgetTester t) async {
  await t.pump();
  await t.pump(const Duration(milliseconds: 100));
}

Future<void> _vaiInFondo(WidgetTester t) async {
  final p = _scorrimentoLista(t).position;
  p.jumpTo(p.maxScrollExtent);
  await _pompa(t);
}

Future<void> _vaiInCima(WidgetTester t) async {
  _scorrimentoLista(t).position.jumpTo(0);
  await _pompa(t);
}

/// Cosa vede l'utente (a inizio lista): quale itinerario, quali interruttori, quale fascia.
class _Vista {
  final bool pioveAcceso;
  final String primaTappa;
  final int cambiate;
  final bool fascia;
  final String? testoFascia;
  _Vista(this.pioveAcceso, this.primaTappa, this.cambiate, this.fascia,
      this.testoFascia,);
  bool get mostraAdattato => primaTappa.startsWith('Adattata');
  @override
  String toString() =>
      'interruttore Piove=${pioveAcceso ? "ACCESO" : "spento"}, prima tappa="$primaTappa", '
      'card "Cambiata dal segnale"=$cambiate, fascia=${fascia ? '"$testoFascia"' : "assente"}';
}

Future<_Vista> _leggi(WidgetTester t) async {
  await _vaiInCima(t);
  final acceso = _acceso(t, _it.signalRain);
  final fasce = find.byType(FasciaRiepilogo);
  final fascia = fasce.evaluate().isNotEmpty;
  final testoFascia = fascia ? t.widget<FasciaRiepilogo>(fasce).testo : null;
  // La prima tappa puo' stare oltre la cache del ListView: scorro a gradini.
  final tappe = find.byWidgetPredicate(
      (w) => w is Text && RegExp(r'^(Originale|Adattata\d+) 0$').hasMatch(w.data ?? ''),);
  for (var passo = 0; passo < 15 && tappe.evaluate().isEmpty; passo++) {
    _scorrimentoLista(t).position.jumpTo(passo * 150.0);
    await _pompa(t);
  }
  final primo =
      tappe.evaluate().isEmpty ? '(nessuna)' : (t.widget<Text>(tappe.first).data ?? '');
  final cambiate = find.text(_it.changedStop).evaluate().length;
  await _vaiInCima(t);
  return _Vista(acceso, primo, cambiate, fascia, testoFascia);
}

void _coerenteAdattato(_Vista v) {
  expect(v.pioveAcceso, isTrue, reason: 'incoerente: $v');
  expect(v.mostraAdattato, isTrue, reason: 'incoerente: $v');
  expect(v.cambiate, greaterThan(0), reason: 'incoerente: $v');
  expect(v.fascia, isTrue, reason: 'incoerente: $v');
  expect(v.testoFascia, startsWith('${_it.signalRain}:'), reason: 'incoerente: $v');
}

void _coerenteOriginale(_Vista v) {
  expect(v.pioveAcceso, isFalse, reason: 'incoerente: $v');
  expect(v.primaTappa, 'Originale 0', reason: 'incoerente: $v');
  expect(v.cambiate, 0, reason: 'incoerente: $v');
  // La fascia di ripristino dopo uno spegnimento e' legittima; mai un riepilogo "Piove: ...".
  if (v.fascia) {
    expect(v.testoFascia, _it.backToOriginalSummary, reason: 'incoerente: $v');
  }
}

/// Acceso Piove + risposta arrivata.
Future<void> _accendiPiove(WidgetTester t, FakeBff bff) async {
  await _premi(t, _it.signalRain);
  expect(bff.chiamateAdapt, 1);
  bff.rispondi(0);
  await _pompa(t);
  // Lascia finire l'effetto d'inchiostro del tocco: finche' dura, l'InkWell
  // tiene viva la card nel ListView (keep-alive) e lo scorrimento non la smonta.
  await t.pump(const Duration(seconds: 2));
}

void main() {
  testWidgets('premessa: montata la schermata, Piove e\' spento e l\'itinerario e\' l\'originale',
      (t) async {
    final bff = FakeBff();
    await _monta(t, bff);
    _coerenteOriginale(await _leggi(t));
    expect(bff.chiamateItinerary, 1);
    expect(bff.chiamateAdapt, 0);
  });

  testWidgets(
      'a) Piove acceso -> spento: itinerario originale, nessuna card cambiata, nessun riepilogo "Piove:"',
      (t) async {
    final bff = FakeBff();
    await _monta(t, bff);
    await _accendiPiove(t, bff);
    _coerenteAdattato(await _leggi(t));

    await _premi(t, _it.signalRain);
    await _pompa(t);
    _coerenteOriginale(await _leggi(t));
    expect(bff.chiamateAdapt, 1, reason: 'spegnere non deve chiamare adapt');
  });

  testWidgets(
      'b) Piove acceso, card scorsa in fondo alla lista e rientrata: interruttore acceso, fascia presente, itinerario adattato',
      (t) async {
    final bff = FakeBff();
    await _monta(t, bff);
    await _accendiPiove(t, bff);
    _coerenteAdattato(await _leggi(t));

    await _vaiInFondo(t);
    // Premessa del test: la card e' davvero uscita dall'albero (oltre la cache).
    expect(find.byType(AdaptiveCard), findsNothing,
        reason: 'la card doveva uscire dalla cache del ListView',);
    // Anche contando i figli fuori schermo (keep-alive): se ci fosse ancora, il test non proverebbe lo smontaggio.
    expect(find.byType(AdaptiveCard, skipOffstage: false), findsNothing,
        reason: 'card ancora nell albero (keep-alive): lo scorrimento non la smonta',);

    final v = await _leggi(t);
    expect(find.byType(AdaptiveCard), findsOneWidget);
    _coerenteAdattato(v);
    expect(bff.chiamateAdapt, 1);
    expect(bff.chiamateItinerary, 1);
  });

  testWidgets(
      'b2) Piove acceso, scorrimento a meta\' lista (card fuori dalla vista) e ritorno: stato coerente',
      (t) async {
    final bff = FakeBff();
    await _monta(t, bff);
    await _accendiPiove(t, bff);
    _scorrimentoLista(t).position.jumpTo(1500);
    await _pompa(t);
    _scorrimentoLista(t).position.jumpTo(0);
    await _pompa(t);
    _coerenteAdattato(await _leggi(t));
  });

  testWidgets(
      'c) 1280x800 -> 390x844 -> 1280x800 con Piove acceso: interruttore, fascia e itinerario invariati',
      (t) async {
    final bff = FakeBff();
    await _monta(t, bff, size: const Size(1280, 800));
    await _accendiPiove(t, bff);
    _coerenteAdattato(await _leggi(t));

    for (final s in const [Size(390, 844), Size(1280, 800)]) {
      t.view.physicalSize = s;
      await _pompa(t);
      await t.pump(const Duration(milliseconds: 300));
      _coerenteAdattato(await _leggi(t));
    }
    expect(bff.chiamateAdapt, 1);
    expect(bff.chiamateItinerary, 1);
  });

  testWidgets(
      'd) acceso-spento-acceso con risposte in ordine invertito: vale l\'ultima pressione',
      (t) async {
    final bff = FakeBff();
    await _monta(t, bff);
    await _premi(t, _it.signalRain); // richiesta 0
    await _premi(t, _it.signalRain); // spento: nessuna richiesta
    await _premi(t, _it.signalRain); // richiesta 1
    expect(bff.chiamateAdapt, 2);
    bff.rispondi(1); // arriva prima la piu' recente
    await _pompa(t);
    bff.rispondi(0); // poi la vecchia (superata)
    await _pompa(t);

    final v = await _leggi(t);
    _coerenteAdattato(v);
    expect(v.primaTappa, 'Adattata1 0',
        reason: 'la risposta superata ha sovrascritto la piu\' recente: $v',);
  });

  testWidgets(
      'd2) acceso-spento con la risposta dell\'acceso che arriva DOPO lo spegnimento: resta spento e originale',
      (t) async {
    final bff = FakeBff();
    await _monta(t, bff);
    await _premi(t, _it.signalRain); // richiesta 0 in volo
    await _premi(t, _it.signalRain); // spento
    bff.rispondi(0); // risposta tardiva
    await _pompa(t);
    _coerenteOriginale(await _leggi(t));
  });

  testWidgets(
      'e) conteggio: una pressione = una adapt; scorrere o ridimensionare = nessuna chiamata',
      (t) async {
    final bff = FakeBff();
    await _monta(t, bff);
    expect(bff.chiamateItinerary, 1);
    expect(bff.chiamateAdapt, 0);

    await _premi(t, _it.signalRain);
    expect(bff.chiamateAdapt, 1);
    bff.rispondi(0);
    await _pompa(t);

    await _vaiInFondo(t);
    await _vaiInCima(t);
    t.view.physicalSize = const Size(1280, 800);
    await _pompa(t);
    t.view.physicalSize = const Size(390, 844);
    await _pompa(t);
    await _vaiInFondo(t);
    await _vaiInCima(t);

    expect(bff.chiamateAdapt, 1,
        reason: 'scorrere/ridimensionare non deve chiamare adapt',);
    expect(bff.chiamateItinerary, 1,
        reason: 'scorrere/ridimensionare non deve chiamare itinerary',);
  });

  testWidgets(
      'refresh (trascinamento in alto) con Piove acceso: interruttori e itinerario coerenti dopo il refresh',
      (t) async {
    final bff = FakeBff();
    await _monta(t, bff);
    await _accendiPiove(t, bff);
    _coerenteAdattato(await _leggi(t));

    await t.fling(find.byType(ListView), const Offset(0, 400), 1000);
    await t.pump();
    await t.pump(const Duration(seconds: 1));
    await t.pump(const Duration(seconds: 1));
    await t.pump(const Duration(milliseconds: 500));
    expect(bff.chiamateItinerary, 2, reason: 'il refresh doveva richiamare itinerary');

    final v = await _leggi(t);
    // O entrambi azzerati o entrambi conservati.
    if (v.pioveAcceso) {
      _coerenteAdattato(v);
    } else {
      _coerenteOriginale(v);
    }
  });

  group('Compito B: stanchezza di partenza a 0 (widget)', () {
    testWidgets(
        '"Sono stanco/a" acceso e poi spento: itinerario di partenza, richiesta iniziale con stanchezza 0.0',
        (t) async {
      final bff = FakeBff();
      await _monta(t, bff);
      expect(bff.contesti.single.signal.stanchezza, 0.0,
          reason: 'segnale di partenza di /itinerary',);

      await _premi(t, _it.signalTired);
      expect(bff.richieste.single.signal.stanchezza, 0.85);
      bff.rispondi(0);
      await _pompa(t);
      await _premi(t, _it.signalTired); // spento: nessuna richiesta
      await _pompa(t);

      expect(bff.chiamateAdapt, 1);
      final v = await _leggi(t);
      expect(v.primaTappa, 'Originale 0');
      expect(bff.contesti.single.signal.stanchezza, 0.0);
      expect(bff.contesti.single.signal.meteo, Meteo.sereno);
    });
  });
}
