// Gate indipendente sulla grafica (direzione C): completa grafica_test.dart.
// Ogni verifica qui puo' FALLIRE se il requisito del committente viene violato.
import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;

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
import 'package:lucca_soul_app/util/interruttori_controller.dart';
import 'package:lucca_soul_app/util/clock.dart';
import 'package:lucca_soul_app/widgets/adaptive_card.dart';
import 'package:lucca_soul_app/widgets/mura_logo.dart';
import 'package:lucca_soul_app/widgets/testata_giornata.dart';

const _json = {'content-type': 'application/json; charset=utf-8'};
final _it = AppStrings.forLanguages(['it']);

const _etichettaLogo = 'Le Mura di Lucca: dieci baluardi e una piattaforma';
const _profilo = EmotionalProfile(
  curiosita: 0.5,
  contemplazione: 0.5,
  arte: 0.5,
  conBambini: false,
  tempoDisponibileMin: 240,
);

// Colori letterali del committente, indipendenti da Tk.
const _testo = Color(0xFF1F2A2E);
const _secondario = Color(0xFF4C585D);
const _sfondo = Color(0xFFF6F2EA);
const _card = Color(0xFFFFFDF9);
const _mattone = Color(0xFFA4482A);
const _avviso = Color(0xFFEFE1CF);
const _sostSfondo = Color(0xFFF3DCCF);
const _sostTesto = Color(0xFF7E351E);
const _mantSfondo = Color(0xFFDCE7DF);
const _bianco = Color(0xFFFFFFFF);
const _errore = Color(0xFF8C2B1B);
const _grigio = Color(0xFF6B7A80);

ItineraryStop _stop(
  String id, {
  String? esito,
  Punto? punto,
  String titolo = 'Passeggiata sulle Mura',
  bool curiosita = false,
}) =>
    ItineraryStop(
      experienceId: id,
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 60,
      reason: 'Perché ti piace camminare.',
      titolo: titolo,
      esitoAdattamento: esito,
      puntoArrivo: punto,
      curiosita: curiosita
          ? const [Curiosita(testo: 'Le Mura sono alberate.', tipo: CuriosityKind.fatto, fonte: 'x')]
          : const [],
    );

Itinerary _itin(List<ItineraryStop> s) =>
    Itinerary(personId: 'p', stops: s, generatedAt: DateTime.utc(2026, 12, 12, 9));

BffClient _client(Itinerary i) => BffClient(
      baseUrl: Uri.parse('http://test'),
      httpClient: MockClient((_) async => http.Response(jsonEncode(i.toJson()), 200, headers: _json)),
    );

/// Raccoglie le eccezioni di layout invece di lasciarle al framework.
List<FlutterErrorDetails> _catturaErrori() {
  final errori = <FlutterErrorDetails>[];
  final vecchio = FlutterError.onError;
  FlutterError.onError = errori.add;
  addTearDown(() => FlutterError.onError = vecchio);
  return errori;
}

Future<void> _monta(WidgetTester t, Size size, {Itinerary? itin}) async {
  t.view.physicalSize = size;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  final i = itin ??
      _itin([
        _stop('a', punto: const Punto(lat: 43.84, lon: 10.5), curiosita: true),
        _stop('b', esito: 'sostituita', titolo: 'Laboratorio al chiuso'),
        _stop('c', esito: 'mantenuta_senza_alternativa'),
      ]);
  Orologio.impostaPerTest(() => DateTime.utc(2026, 12, 12, 9));
  addTearDown(() => Orologio.impostaPerTest(null));
  await t.pumpWidget(MaterialApp(
    theme: buildAppTheme(),
    home: ItineraryScreen(bffClient: _client(i), personId: 'p', profile: _profilo),
  ),);
  await t.pumpAndSettle();
}

/// Colore effettivo di un Text (stile proprio fuso con quello ereditato).
Color? _colore(WidgetTester t, Finder f) {
  final w = t.widget<Text>(f);
  return DefaultTextStyle.of(t.element(f)).style.merge(w.style).color;
}

double _lum(Color c) {
  double ch(double v) => v <= 0.03928 ? v / 12.92 : math.pow((v + 0.055) / 1.055, 2.4).toDouble();
  return 0.2126 * ch(c.r) + 0.7152 * ch(c.g) + 0.0722 * ch(c.b);
}

double _rapporto(Color a, Color b) {
  final la = _lum(a), lb = _lum(b);
  return ((la > lb ? la : lb) + 0.05) / ((la > lb ? lb : la) + 0.05);
}

void main() {
  group('1. contrasto, calcolo indipendente dai Tk', () {
    void atteso(Color a, Color b, double v) => expect(_rapporto(a, b), closeTo(v, 0.06), reason: '$a su $b');

    test('valori del committente', () {
      atteso(_testo, _sfondo, 13.2);
      atteso(_testo, _card, 14.5);
      atteso(_secondario, _sfondo, 6.6);
      atteso(_secondario, _card, 7.2);
      atteso(_mattone, _sfondo, 5.3);
      atteso(_mattone, _card, 5.8);
      atteso(_bianco, _mattone, 5.9);
      atteso(_mattone, _avviso, 4.6);
      atteso(_sostTesto, _sostSfondo, 6.6);
      atteso(_testo, _mantSfondo, 11.6);
      atteso(_sfondo, _testo, 13.2);
    });

    test('i token coincidono con i valori esadecimali del committente', () {
      expect(Tk.testo, _testo);
      expect(Tk.testoSecondario, _secondario);
      expect(Tk.sfondo, _sfondo);
      expect(Tk.cardSfondo, _card);
      expect(Tk.accento, _mattone);
      expect(Tk.avviso, _avviso);
      expect(Tk.sostituitaSfondo, _sostSfondo);
      expect(Tk.sostituitaTesto, _sostTesto);
      expect(Tk.mantenutaSfondo, _mantSfondo);
      expect(Tk.testata, _testo);
      expect(Tk.testoSuTestata, _sfondo);
      expect(Tk.grigioNonTestuale, _grigio);
    });

    test('colore di errore del tema >= 4,5 su ogni sfondo su cui compare', () {
      final err = buildAppTheme().colorScheme.error;
      expect(err, _errore);
      // sfondo pagina (onboarding, schermata itinerario), card (card adattiva),
      // sheet della memoria (card), avviso, contenitore errore.
      for (final s in [_sfondo, _card, _avviso, _sostSfondo]) {
        expect(_rapporto(err, s), greaterThanOrEqualTo(4.5), reason: 'errore su $s');
      }
    });

    test('coppie colorScheme/testo del tema >= 4,5', () {
      final tema = buildAppTheme();
      final s = tema.colorScheme;
      final coppie = <(Color, Color, String)>[
        (s.onSurface, s.surface, 'onSurface'),
        (s.onSurfaceVariant, s.surface, 'onSurfaceVariant/surface'),
        (s.onSurfaceVariant, s.surfaceContainerLow, 'onSurfaceVariant/card'),
        (s.onPrimary, s.primary, 'onPrimary'),
        (s.onSecondary, s.secondary, 'onSecondary'),
        (s.onTertiary, s.tertiary, 'onTertiary'),
        (s.onError, s.error, 'onError'),
        (s.onErrorContainer, s.errorContainer, 'onErrorContainer'),
        (s.onPrimaryContainer, s.primaryContainer, 'onPrimaryContainer'),
        (s.onSecondaryContainer, s.secondaryContainer, 'onSecondaryContainer'),
        (s.onInverseSurface, s.inverseSurface, 'onInverseSurface'),
        (s.primary, s.surface, 'primary/surface'),
        (s.primary, s.surfaceContainerLow, 'primary/card'),
      ];
      for (final (a, b, n) in coppie) {
        expect(_rapporto(a, b), greaterThanOrEqualTo(4.5), reason: n);
      }
      final tt = tema.textTheme;
      for (final st in [
        tt.bodyLarge,
        tt.bodyMedium,
        tt.bodySmall,
        tt.labelMedium,
        tt.labelSmall,
        tt.titleMedium,
        tt.headlineSmall,
      ]) {
        expect(_rapporto(st!.color!, _card), greaterThanOrEqualTo(4.5));
        expect(_rapporto(st.color!, _sfondo), greaterThanOrEqualTo(4.5));
      }
    });

    test('mattone non su sfondo scuro: contrasto basso e assente nella testata del tema', () {
      expect(_rapporto(_mattone, _testo), lessThan(3));
      final tema = buildAppTheme();
      expect(tema.appBarTheme.backgroundColor, _testo);
      expect(tema.appBarTheme.foregroundColor, isNot(_mattone));
      expect(tema.appBarTheme.titleTextStyle!.color, _sfondo);
      expect(tema.snackBarTheme.backgroundColor, _testo);
      expect(tema.snackBarTheme.actionTextColor, isNot(_mattone));
    });
  });

  group('1b. nella schermata montata', () {
    testWidgets('nessun testo/icona renderizzato e\' #6B7A80; la testata non ha mattone', (t) async {
      await _monta(t, const Size(390, 844));
      for (final f in find.byType(Text, skipOffstage: false).evaluate()) {
        final w = f.widget as Text;
        final c = DefaultTextStyle.of(f).style.merge(w.style).color;
        expect(c, isNot(_grigio), reason: 'Text "${w.data}"');
      }
      for (final f in find.byType(Icon, skipOffstage: false).evaluate()) {
        expect((f.widget as Icon).color, isNot(_grigio));
      }
      for (final radice in [find.byType(AppBar), find.byType(TestataGiornata), find.byType(MuraLogo)]) {
        final testi = find.descendant(of: radice, matching: find.byType(Text));
        for (var i = 0; i < testi.evaluate().length; i++) {
          expect(_colore(t, testi.at(i)), _sfondo);
        }
        for (final ic in find.descendant(of: radice, matching: find.byType(Icon)).evaluate()) {
          expect((ic.widget as Icon).color, isNot(_mattone));
        }
      }
      expect(t.widget<MuraLogo>(find.byType(MuraLogo)).colore, _sfondo);
      final cont = t.widget<Container>(
        find.descendant(of: find.byType(TestataGiornata), matching: find.byType(Container)).first,
      );
      expect(cont.color, _testo);
    });

    testWidgets('ogni Text dentro una StopCard ha contrasto >= 4,5 sul suo sfondo', (t) async {
      await _monta(t, const Size(390, 2400));
      for (final card in find.byType(StopCard).evaluate()) {
        for (final f in find.descendant(of: find.byWidget(card.widget), matching: find.byType(Text)).evaluate()) {
          final w = f.widget as Text;
          final c = DefaultTextStyle.of(f).style.merge(w.style).color!;
          final Color su;
          if (w.data == '1' || w.data == '2' || w.data == '3') {
            su = _mattone;
          } else if (w.data == 'Cambiata dal segnale') {
            su = _sostSfondo;
          } else if (w.data == 'Resta in programma') {
            su = _mantSfondo;
          } else {
            su = _card;
          }
          expect(_rapporto(c, su), greaterThanOrEqualTo(4.5), reason: 'Text "${w.data}"');
        }
      }
    });
  });

  group('2. schermata 390x844', () {
    testWidgets('nessuna eccezione di layout/overflow, nessuno scorrimento orizzontale', (t) async {
      final errori = _catturaErrori();
      await _monta(t, const Size(390, 844));
      expect(errori.map((e) => e.exceptionAsString()), isEmpty);
      expect(t.takeException(), isNull);
      for (final e in find.byType(Text).evaluate()) {
        final r = e.renderObject! as RenderBox;
        final right = r.localToGlobal(Offset(r.size.width, 0)).dx;
        expect(right, lessThanOrEqualTo(390.5), reason: 'Text "${(e.widget as Text).data}"');
      }
      for (final s in t.stateList<ScrollableState>(find.byType(Scrollable))) {
        expect(axisDirectionToAxis(s.position.axisDirection), Axis.vertical);
        expect(s.position.maxScrollExtent, greaterThanOrEqualTo(0));
      }
    });

    testWidgets('testi leggibili (>= 12 px)', (t) async {
      await _monta(t, const Size(390, 844));
      for (final f in find.byType(Text).evaluate()) {
        final w = f.widget as Text;
        final size = DefaultTextStyle.of(f).style.merge(w.style).fontSize ?? 14;
        expect(size, greaterThanOrEqualTo(12), reason: '"${w.data}"');
      }
    });

    testWidgets('interruttori e "Come arrivo qui" >= 44 px', (t) async {
      await _monta(t, const Size(390, 844));
      final tutti = [
        for (var i = 0; i < 3; i++) find.byType(InterruttoreSegnale).at(i),
        find.widgetWithText(TextButton, 'Come arrivo qui'),
      ];
      for (final f in tutti) {
        final s = t.getSize(f);
        expect(s.height, greaterThanOrEqualTo(44));
        expect(s.width, greaterThanOrEqualTo(44));
      }
    });

    testWidgets('etichetta di accessibilita\' ESATTA della testata', (t) async {
      final sem = t.ensureSemantics();
      expect(kMuraLogoLabel, _etichettaLogo);
      await _monta(t, const Size(390, 844));
      expect(t.getSemantics(find.byType(MuraLogo)).label, _etichettaLogo);
      sem.dispose();
    });

    testWidgets('schermo largo: contenuto in colonna <= 600 px, centrata, senza errori', (t) async {
      final errori = _catturaErrori();
      await _monta(t, const Size(1400, 900));
      expect(errori, isEmpty);
      for (final f in [find.byType(ListView), find.byType(AdaptiveCard), find.byType(StopCard).first]) {
        final r = t.getRect(f);
        expect(r.width, lessThanOrEqualTo(600), reason: '$f');
        expect(r.center.dx, closeTo(700, 1));
      }
      final riga = t.getRect(find.textContaining('a piedi'));
      expect(riga.left, greaterThanOrEqualTo(400));
      expect(riga.right, lessThanOrEqualTo(1000));
    });
  });

  group('3-4. interruttori e fascia di riepilogo', () {
    Future<void> montaCard(WidgetTester t) async {
      t.view.physicalSize = const Size(390, 844);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      final orig = _itin([_stop('a'), _stop('b'), _stop('c')]);
      final adat = _itin([
        _stop('a2', esito: 'sostituita'),
        _stop('b2', esito: 'sostituita'),
        _stop('c', esito: 'mantenuta_senza_alternativa'),
      ]);
      final controller = InterruttoriController(bffClient: _client(adat), originale: orig, profilo: _profilo);
      addTearDown(controller.dispose);
      await t.pumpWidget(MaterialApp(
        theme: buildAppTheme(),
        home: Scaffold(
          body: SingleChildScrollView(
            child: AdaptiveCard(
              controller: controller,
              strings: _it,
            ),
          ),
        ),
      ),);
    }

    testWidgets('etichette esatte; spento = card; acceso = mattone, bianco, spunta', (t) async {
      await montaCard(t);
      for (final e in ['Piove', 'Mura affollate', 'Sono stanco/a']) {
        expect(find.text(e), findsOneWidget);
      }
      Material mat(String e) => t.widget<Material>(
            find
                .descendant(of: find.widgetWithText(InterruttoreSegnale, e), matching: find.byType(Material))
                .first,
          );
      expect(mat('Piove').color, _card);
      expect(find.byIcon(Icons.check), findsNothing);
      expect(_colore(t, find.text('Piove')), _testo);

      await t.tap(find.text('Piove'));
      await t.pumpAndSettle();
      expect(mat('Piove').color, _mattone);
      expect(_colore(t, find.text('Piove')), _bianco);
      expect(
        find.descendant(of: find.widgetWithText(InterruttoreSegnale, 'Piove'), matching: find.byIcon(Icons.check)),
        findsOneWidget,
      );
      expect(mat('Mura affollate').color, _card);
      expect(find.byIcon(Icons.check), findsOneWidget);

      await t.tap(find.text('Sono stanco/a'));
      await t.pumpAndSettle();
      expect(mat('Sono stanco/a').color, _mattone);
      expect(find.byIcon(Icons.check), findsNWidgets(2));
      await t.tap(find.text('Piove'));
      await t.pumpAndSettle();
      expect(mat('Piove').color, _card);
    });

    testWidgets('fascia: testo dagli esiti, Annulla a destra, Torna sotto', (t) async {
      await montaCard(t);
      await t.tap(find.text('Piove'));
      await t.pumpAndSettle();
      final testo = find.text('Piove: 2 tappe cambiate, 1 resta in programma.');
      expect(testo, findsOneWidget);
      final annulla = find.text('Annulla');
      final torna = find.text('Torna al percorso iniziale');
      expect(annulla, findsOneWidget);
      expect(t.getRect(annulla).left, greaterThanOrEqualTo(t.getRect(testo).right - 1),
          reason: 'Annulla a destra del riepilogo',);
      expect(t.getRect(torna).top, greaterThanOrEqualTo(t.getRect(annulla).bottom - 1),
          reason: 'Torna sotto la fascia',);
      final fascia = t.widget<Container>(find.ancestor(of: testo, matching: find.byType(Container)).first);
      expect((fascia.decoration! as BoxDecoration).color, _avviso);
      expect(_colore(t, annulla), _mattone);
      expect(t.getSize(find.widgetWithText(TextButton, 'Annulla')).height, greaterThanOrEqualTo(44));
      expect(t.getSize(find.widgetWithText(TextButton, 'Torna al percorso iniziale')).height,
          greaterThanOrEqualTo(44),);
    });

    testWidgets('due segnali: il riepilogo li elenca; Torna azzera fascia e spunte', (t) async {
      await montaCard(t);
      await t.tap(find.text('Piove'));
      await t.pumpAndSettle();
      await t.tap(find.text('Mura affollate'));
      await t.pumpAndSettle();
      expect(find.textContaining('Piove, Mura affollate:'), findsOneWidget);
      await t.tap(find.text('Torna al percorso iniziale'));
      await t.pumpAndSettle();
      // Per progetto il ritorno al percorso iniziale entra nella storia: la fascia
      // resta, con il testo di ripristino, e Annulla puo' disfarlo.
      expect(find.text('Percorso iniziale ripristinato.'), findsOneWidget);
      expect(find.byIcon(Icons.check), findsNothing);
    });
  });

  group('5. card della tappa', () {
    testWidgets('ordine: numero | titolo, ora e durata, motivo, curiosita\', Come arrivo qui', (t) async {
      await _monta(t, const Size(390, 2400));
      final card = find.byType(StopCard).first;
      Finder d(Finder f) => find.descendant(of: card, matching: f);
      final num = t.getRect(d(find.text('1')));
      final titolo = t.getRect(d(find.text('Passeggiata sulle Mura')));
      final ora = t.getRect(d(find.text('09:00 · 60 min')));
      final motivo = t.getRect(d(find.text('Perché ti piace camminare.')));
      final cur = t.getRect(d(find.text('Le Mura sono alberate.')));
      final come = t.getRect(d(find.text('Come arrivo qui')));
      expect(num.right, lessThanOrEqualTo(titolo.left));
      final cerchioRect = t.getRect(d(find.ancestor(of: find.text('1'), matching: find.byType(Container))).first);
      expect(cerchioRect.size, const Size(32, 32));
      expect(titolo.bottom, lessThanOrEqualTo(ora.top));
      expect(ora.bottom, lessThanOrEqualTo(motivo.top));
      expect(motivo.bottom, lessThanOrEqualTo(cur.top));
      expect(cur.bottom, lessThanOrEqualTo(come.top));
      final cerchio = t.widget<Container>(d(find.ancestor(of: find.text('1'), matching: find.byType(Container))).first);
      final deco = cerchio.decoration! as BoxDecoration;
      expect(deco.shape, BoxShape.circle);
      expect(deco.color, _mattone);
      expect(_colore(t, d(find.text('1'))), _bianco);
    });

    testWidgets('numeri 1..3 in ordine; etichetta esito solo con esito, coi colori giusti', (t) async {
      await _monta(t, const Size(390, 2400));
      final y = [for (final n in ['1', '2', '3']) t.getRect(find.text(n)).top];
      expect(y[0], lessThan(y[1]));
      expect(y[1], lessThan(y[2]));
      final cards = find.byType(StopCard);
      Finder et(int i) => find.descendant(of: cards.at(i), matching: find.byType(EtichettaEsito));
      expect(et(0), findsNothing);
      expect(et(1), findsOneWidget);
      expect(et(2), findsOneWidget);
      final e1 = t.widget<EtichettaEsito>(et(1));
      expect((e1.sfondo, e1.colore), (_sostSfondo, _sostTesto));
      final e2 = t.widget<EtichettaEsito>(et(2));
      expect((e2.sfondo, e2.colore), (_mantSfondo, _testo));
    });

    testWidgets('senza puntoArrivo e senza esito: niente "Come arrivo qui" ne\' etichetta', (t) async {
      await _monta(t, const Size(390, 2400), itin: _itin([_stop('a')]));
      expect(find.text('Come arrivo qui'), findsNothing);
      expect(find.byType(EtichettaEsito), findsNothing);
    });
  });

  group('6. testata', () {
    testWidgets('Lucca Soul, data, fascia, tappe, a piedi, tutto in #F6F2EA, nessun prezzo', (t) async {
      await _monta(t, const Size(390, 844));
      expect(_colore(t, find.text('Lucca Soul')), _sfondo);
      final riga = find.descendant(of: find.byType(TestataGiornata), matching: find.byType(Text));
      expect(riga, findsOneWidget);
      final testo = t.widget<Text>(riga).data!;
      expect(testo, contains('12'));
      expect(testo, contains('09:00–'));
      expect(testo, contains('3 tappe'));
      expect(testo, contains('a piedi'));
      expect(testo, isNot(contains('€')));
      expect(_colore(t, riga), _sfondo);
      expect(t.getRect(find.byType(TestataGiornata)).top, greaterThanOrEqualTo(t.getRect(find.byType(AppBar)).bottom - 1));
    });
  });

  group('7. nessun prezzo', () {
    test('niente gratis/gratuit/euro/€/prezzo in lib, asset JSON e pubspec', () {
      final vietato = RegExp('gratis|gratuit|€|\\beuro\\b|\\beur\\b|prezzo|price', caseSensitive: false);
      final file = [
        ...Directory('lib').listSync(recursive: true).whereType<File>().where((f) => f.path.endsWith('.dart')),
        File('assets/brand/mura_punti.json'),
        File('pubspec.yaml'),
      ];
      for (final f in file) {
        // I commenti che dichiarano l'ASSENZA di un prezzo non contano.
        final codice = f
            .readAsStringSync()
            .split(RegExp(r'\r?\n'))
            .where((r) => !r.trimLeft().startsWith('//'))
            .join(' ');
        final m = vietato.firstMatch(codice);
        expect(m, isNull, reason: '${f.path}: ${m?.group(0)}');
      }
    });
  });

  group('8. font incorporati', () {
    final pubspec = File('pubspec.yaml').readAsStringSync();

    test('pubspec dichiara Domine e NunitoSans con file esistenti e OFL.txt', () {
      expect(pubspec, contains('family: Domine'));
      expect(pubspec, contains('family: NunitoSans'));
      final percorsi = RegExp(r'asset:\s*(\S+\.ttf)').allMatches(pubspec).map((m) => m.group(1)!).toList();
      expect(percorsi, hasLength(2));
      for (final p in percorsi) {
        final f = File(p);
        expect(f.existsSync(), isTrue, reason: p);
        expect(f.lengthSync(), greaterThan(50 * 1024), reason: '$p troppo piccolo per un font');
        final ofl = File('${f.parent.path}/OFL.txt');
        expect(ofl.existsSync(), isTrue, reason: 'OFL.txt accanto a $p');
        expect(ofl.readAsStringSync().toUpperCase(), contains('SIL OPEN FONT LICENSE'));
      }
    });

    test('nessuna dipendenza google_fonts (pubspec, lock, sorgenti)', () {
      expect(pubspec, isNot(contains('google_fonts')));
      expect(File('pubspec.lock').readAsStringSync(), isNot(contains('google_fonts')));
      for (final f in Directory('lib').listSync(recursive: true).whereType<File>()) {
        if (f.path.endsWith('.dart')) {
          expect(f.readAsStringSync(), isNot(contains('google_fonts')), reason: f.path);
        }
      }
    });

    test('il tema usa le famiglie dichiarate', () {
      final tt = buildAppTheme().textTheme;
      expect(tt.titleMedium!.fontFamily, 'Domine');
      expect(tt.bodyMedium!.fontFamily, 'NunitoSans');
    });
  });
}
