// Voce 6: confronto «Prima/Ora» in una riga sopra le tappe, dopo un adattamento.
//
// La "fine" ha la stessa regola di fasciaOrariaGiornata (massimo di
// arrivo + durata, minuti mod 24h): qui si prova su casi reali e di confine.
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
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
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/util/clock.dart';
import 'package:lucca_soul_app/util/foto_tappa.dart';
import 'package:lucca_soul_app/util/riepilogo_cambio.dart';
import 'package:lucca_soul_app/widgets/adaptive_card.dart';

// FIXTURE: itinerari REALI del BFF (POST /itinerary e POST /itinerary/adapt,
// fonte seed di Lucca, nessun Aura), ottenuti eseguendo il BFF in Python con
// il fixture `client` di services/api/tests/test_golden_lucca.py (SeedCandidateSource).
// Profilo contemplativo: curiosita 0.35, contemplazione 0.8, arte 0.5,
// con_bambini false, tempo 180 min, lingue it. Segnale sereno, ore 10:00 del
// 2026-12-12 -> 5 tappe; poi pioggia + stanchezza 0.85 -> 3 tappe.
// Tenuti solo i campi che l'app legge per queste prove.
const _originaleJson = r"""{
  "person_id": "p-demo",
  "generated_at": "2026-11-12T16:47:44.649401",
  "adattato_da_segnale": false,
  "tempo_disponibile_min": 180,
  "tempo_effettivo_min": 180,
  "stops": [
    {
      "experience_id": "exp-giardino-pfanner",
      "titolo": "Il giardino barocco di Palazzo Pfanner",
      "arrivo": "10:00:00",
      "durata_min": 30,
      "reason": "Cerchi silenzio e raccoglimento. Temi: verde e giardini, arte, panorama. All'aperto."
    },
    {
      "experience_id": "exp-interno-san-frediano",
      "titolo": "La basilica di San Frediano e il fonte lustrale",
      "arrivo": "10:33:00",
      "durata_min": 30,
      "reason": "Temi: romanico, arte, medioevo. Al chiuso."
    },
    {
      "experience_id": "exp-facciata-san-michele",
      "titolo": "La facciata scolpita di San Michele in Foro",
      "arrivo": "11:09:00",
      "durata_min": 25,
      "reason": "In questa chiesa il giovane Giacomo Puccini dava lezioni d'organo al suo unico allievo, il sarto Carlo Della Nina; per la festa di San Michele vi si suonano ancora musiche della famiglia Puccini. All'aperto."
    },
    {
      "experience_id": "exp-santi-giovanni-reparata",
      "titolo": "La chiesa dei Santi Giovanni e Reparata e l'area archeologica",
      "arrivo": "11:39:00",
      "durata_min": 40,
      "reason": "Temi: storia, arte, romanico. Al chiuso."
    },
    {
      "experience_id": "exp-via-del-fosso",
      "titolo": "Via del Fosso: il canale e i ponticelli",
      "arrivo": "12:30:00",
      "durata_min": 20,
      "reason": "Temi: silenzio e contemplazione, storia. All'aperto."
    }
  ]
}""";

const _adattatoJson = r"""{
  "person_id": "p-demo",
  "generated_at": "2026-11-12T16:47:44.665471",
  "adattato_da_segnale": true,
  "tempo_disponibile_min": 180,
  "tempo_effettivo_min": 180,
  "stops": [
    {
      "experience_id": "exp-chiesa-chiostro-san-francesco",
      "titolo": "La chiesa di San Francesco e il suo chiostro",
      "arrivo": "10:00:00",
      "durata_min": 30,
      "reason": "Sostituita per la pioggia. Cerchi silenzio e raccoglimento. Temi: musica, silenzio e contemplazione, storia. Al chiuso.",
      "esito_adattamento": "sostituita"
    },
    {
      "experience_id": "exp-interno-san-frediano",
      "titolo": "La basilica di San Frediano e il fonte lustrale",
      "arrivo": "10:38:00",
      "durata_min": 30,
      "reason": "Temi: romanico, arte, medioevo. Al chiuso.",
      "esito_adattamento": "non_toccata"
    },
    {
      "experience_id": "exp-interno-san-michele",
      "titolo": "L'interno di San Michele in Foro",
      "arrivo": "11:14:00",
      "durata_min": 20,
      "reason": "Sostituita per la pioggia. In questa chiesa il giovane Giacomo Puccini dava lezioni d'organo al suo unico allievo, il sarto Carlo Della Nina; per la festa di San Michele vi si suonano ancora musiche della famiglia Puccini. Al chiuso.",
      "esito_adattamento": "sostituita"
    }
  ]
}""";

final _it = AppStrings.forLanguages(['it']);
final _en = AppStrings.forLanguages(['en']);

Itinerary _da(String json) => Itinerary.fromJson(jsonDecode(json) as Map<String, dynamic>);

ItineraryStop _tappa(String arrivo, int durata, [String id = 'x']) => ItineraryStop(
      experienceId: id,
      arrivo: TimeHms.parse(arrivo),
      durataMin: durata,
      reason: 'motivo',
    );

Itinerary _con(List<ItineraryStop> tappe) => Itinerary(
      personId: 'p',
      generatedAt: DateTime.utc(2026, 12, 12, 9),
      stops: tappe,
    );

String _fineDallaFascia(List<ItineraryStop> tappe) =>
    fasciaOrariaGiornata(tappe)!.split('–').last;

String _fineDallaRiga(String riga, {required bool prima}) {
  final parti = riga.split(' · ');
  final m = RegExp(r'(?:fine|ends) (\d\d:\d\d)').firstMatch(parti[prima ? 0 : 1]);
  return m!.group(1)!;
}

void main() {
  group('confrontoInUnaRiga: puro', () {
    test('copione: caso demo reale -> 5 tappe fine 12:50, 3 tappe fine 11:34', () {
      final prima = _da(_originaleJson);
      final ora = _da(_adattatoJson);
      expect(prima.stops, hasLength(5));
      expect(ora.stops, hasLength(3));
      expect(
        confrontoInUnaRiga(originale: prima, mostrato: ora, strings: _it),
        'Prima: 5 tappe, fine 12:50 · Ora: 3 tappe, fine 11:34',
      );
    });

    test('inglese: formato reale di app_strings', () {
      expect(
        confrontoInUnaRiga(originale: _da(_originaleJson), mostrato: _da(_adattatoJson), strings: _en),
        'Before: 5 stops, ends 12:50 · Now: 3 stops, ends 11:34',
      );
    });

    test('originale senza tappe -> null (anche se il mostrato ne ha)', () {
      expect(confrontoInUnaRiga(originale: _con([]), mostrato: _da(_adattatoJson), strings: _it), isNull);
      expect(confrontoInUnaRiga(originale: _con([]), mostrato: _con([]), strings: _it), isNull);
      expect(confrontoInUnaRiga(originale: _con([]), mostrato: _da(_adattatoJson), strings: _en), isNull);
    });

    test('mostrato senza tappe -> «... · Ora: nessuna tappa», senza orario', () {
      final r = confrontoInUnaRiga(originale: _da(_originaleJson), mostrato: _con([]), strings: _it);
      expect(r, 'Prima: 5 tappe, fine 12:50 · Ora: nessuna tappa');
      final en = confrontoInUnaRiga(originale: _da(_originaleJson), mostrato: _con([]), strings: _en);
      expect(en, 'Before: 5 stops, ends 12:50 · Now: no stops');
    });

    test('singolare: «1 tappa» (prima e ora), «1 stop» in inglese', () {
      final una = _con([_tappa('10:00:00', 30)]);
      expect(
        confrontoInUnaRiga(originale: _da(_originaleJson), mostrato: una, strings: _it),
        'Prima: 5 tappe, fine 12:50 · Ora: 1 tappa, fine 10:30',
      );
      expect(
        confrontoInUnaRiga(originale: una, mostrato: _da(_adattatoJson), strings: _it),
        'Prima: 1 tappa, fine 10:30 · Ora: 3 tappe, fine 11:34',
      );
      expect(
        confrontoInUnaRiga(originale: una, mostrato: una, strings: _en),
        'Before: 1 stop, ends 10:30 · Now: 1 stop, ends 10:30',
      );
      expect(
        confrontoInUnaRiga(originale: una, mostrato: una, strings: _it),
        isNot(contains('1 tappe')),
      );
    });

    test('tappa che passa la mezzanotte: fine in minuti mod 24h come la fascia', () {
      final notte = _con([_tappa('23:30:00', 60)]);
      expect(fasciaOrariaGiornata(notte.stops), '23:30–00:30');
      expect(
        confrontoInUnaRiga(originale: notte, mostrato: notte, strings: _it),
        'Prima: 1 tappa, fine 00:30 · Ora: 1 tappa, fine 00:30',
      );
      // Il massimo e' preso sui minuti grezzi (arrivo + durata), poi mod 24h:
      // una tappa del mattino non scavalca quella che chiude dopo mezzanotte.
      final mista = _con([_tappa('09:00:00', 30), _tappa('23:50:00', 30)]);
      expect(_fineDallaFascia(mista.stops), '00:20');
      expect(
        confrontoInUnaRiga(originale: mista, mostrato: mista, strings: _it),
        'Prima: 2 tappe, fine 00:20 · Ora: 2 tappe, fine 00:20',
      );
      // Esattamente a mezzanotte: 24:00 -> 00:00.
      final dodici = _con([_tappa('23:00:00', 60)]);
      expect(
        confrontoInUnaRiga(originale: dodici, mostrato: dodici, strings: _it),
        'Prima: 1 tappa, fine 00:00 · Ora: 1 tappa, fine 00:00',
      );
    });

    test('la fine non e quella dell ultima tappa ma il massimo di arrivo + durata', () {
      final lunga = _con([_tappa('09:00:00', 120), _tappa('10:00:00', 15)]);
      expect(
        confrontoInUnaRiga(originale: lunga, mostrato: lunga, strings: _it),
        'Prima: 2 tappe, fine 11:00 · Ora: 2 tappe, fine 11:00',
      );
    });

    test('coerenza: fine == seconda meta di fasciaOrariaGiornata su piu casi', () {
      final casi = <String, List<ItineraryStop>>{
        'demo originale': _da(_originaleJson).stops,
        'demo adattato': _da(_adattatoJson).stops,
        'una tappa': [_tappa('09:05:00', 7)],
        'mezzanotte': [_tappa('23:30:00', 60)],
        'mista con mezzanotte': [_tappa('09:00:00', 30), _tappa('23:50:00', 30)],
        'tappa lunga al centro': [_tappa('09:00:00', 120), _tappa('10:00:00', 15)],
        'ordine invertito': [_tappa('15:00:00', 20), _tappa('08:00:00', 45)],
        'esattamente 24:00': [_tappa('23:00:00', 60)],
        'minuti a 59': [_tappa('00:59:00', 1), _tappa('13:59:00', 61)],
        'durata oltre un giorno': [_tappa('22:00:00', 1500)],
      };
      for (final e in casi.entries) {
        final it = _con(e.value);
        final attesa = _fineDallaFascia(e.value);
        final riga = confrontoInUnaRiga(originale: it, mostrato: it, strings: _it)!;
        expect(_fineDallaRiga(riga, prima: true), attesa, reason: '${e.key} (prima)');
        expect(_fineDallaRiga(riga, prima: false), attesa, reason: '${e.key} (ora)');
        final en = confrontoInUnaRiga(originale: it, mostrato: it, strings: _en)!;
        expect(_fineDallaRiga(en, prima: true), attesa, reason: '${e.key} (en)');
      }
    });
  });

  group('ItineraryScreen: riga di confronto', () {
    const profilo = EmotionalProfile(
      curiosita: 0.35,
      contemplazione: 0.8,
      arte: 0.5,
      conBambini: false,
      tempoDisponibileMin: 180,
      lingue: ['it'],
    );
    const chiave = Key('confronto-in-una-riga');

    BffClient bff(List<String> adapt) => BffClient(
          baseUrl: Uri.parse('http://test'),
          httpClient: MockClient((req) async {
            final corpo = req.url.path == '/itinerary/adapt' ? _adattatoJson : _originaleJson;
            if (req.url.path == '/itinerary/adapt') adapt.add(req.body);
            return http.Response.bytes(
              utf8.encode(corpo),
              200,
              headers: {'content-type': 'application/json; charset=utf-8'},
            );
          }),
        );

    Future<void> monta(WidgetTester t, BffClient client) async {
      t.view.physicalSize = const Size(800, 3000);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.resetPhysicalSize);
      addTearDown(t.view.resetDevicePixelRatio);
      Orologio.impostaPerTest(() => DateTime.utc(2026, 12, 12, 9));
      addTearDown(() => Orologio.impostaPerTest(null));
      await t.pumpWidget(MaterialApp(
        theme: buildAppTheme(),
        home: ItineraryScreen(
          bffClient: client,
          personId: 'p',
          profile: profilo,
          tileProvider: _TileKo(),
          archivioFoto: const ArchivioFoto(),
        ),
      ),);
      await t.pumpAndSettle();
    }

    Future<void> premi(WidgetTester t, String etichetta) async {
      await t.tap(find.widgetWithText(InterruttoreSegnale, etichetta));
      await t.pumpAndSettle();
    }

    testWidgets('con l originale la riga non c e', (t) async {
      await monta(t, bff([]));
      expect(find.byType(StopCard), findsNWidgets(5));
      expect(find.byKey(chiave), findsNothing);
      expect(find.byType(FasciaRiepilogo), findsNothing);
    });

    testWidgets('dopo un adattamento la riga c e, sopra le tappe, e la fascia esiste ancora', (t) async {
      final adapt = <String>[];
      await monta(t, bff(adapt));
      await premi(t, _it.signalRain);
      await premi(t, _it.signalTired);
      expect(adapt, hasLength(2));
      expect(find.byType(StopCard), findsNWidgets(3));

      final riga = find.byKey(chiave);
      expect(riga, findsOneWidget);
      expect(
        t.widget<Text>(riga).data,
        'Prima: 5 tappe, fine 12:50 · Ora: 3 tappe, fine 11:34',
      );

      // Sopra la prima tappa (e sopra il titolo dell elenco).
      final primaTappa = t.getRect(find.byType(StopCard).first);
      expect(t.getRect(riga).bottom, lessThanOrEqualTo(primaTappa.top));
      expect(t.getRect(riga).top, lessThan(primaTappa.top));

      // La fascia di riepilogo esistente resta, con i segnali accesi.
      expect(find.byType(FasciaRiepilogo), findsOneWidget);
      expect(t.widget<FasciaRiepilogo>(find.byType(FasciaRiepilogo)).testo, startsWith('${_it.signalRain}, ${_it.signalTired}:'));
    });

    testWidgets('spegnendo i segnali si torna all originale e la riga sparisce', (t) async {
      await monta(t, bff([]));
      await premi(t, _it.signalRain);
      expect(find.byKey(chiave), findsOneWidget);
      await premi(t, _it.signalRain);
      expect(find.byKey(chiave), findsNothing);
      expect(find.byType(StopCard), findsNWidgets(5));
    });
  });
}

class _TileKo extends TileProvider {
  @override
  ImageProvider getImage(TileCoordinates coordinates, TileLayer options) =>
      MemoryImage(Uint8List(0));
}
