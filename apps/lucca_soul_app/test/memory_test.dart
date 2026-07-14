// Test di contratto per la Urban Memory (Wave 2): verificano che
// `MemoryContribution` produca/consumi esattamente i campi JSON canonici di
// `docs/DATA_CONTRACTS.md` §4 / `packages/contracts`, e che la regola pura
// di invio (`puoConferire`) non ammetta MAI eccezioni sul consenso. Nessuna
// dipendenza da widget: gira senza device.
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/memory_contribution.dart';
import 'package:lucca_soul_app/models/memory_kind.dart';
import 'package:lucca_soul_app/models/person_kind.dart';
import 'package:lucca_soul_app/util/memory_gate.dart';

void main() {
  group('MemoryContribution', () {
    test('fromJson/toJson usa i campi canonici di docs/DATA_CONTRACTS.md §4', () {
      final json = {
        'id': 'memoria_abc123',
        'kind': 'racconto',
        'testo': 'Il vento sulle mura al tramonto.',
        'media_uri': null,
        'riguarda': ['mura-urbane'],
        'contributor_id': 'visitor_abc',
        'contributor_kind': 'turista',
        'esperienza_id': 'exp-passeggiata-mura',
        'consenso': true,
        'licenza': 'CC-BY-SA-4.0',
        'creato_il': '2026-07-14T18:30:00.000Z',
        'curato': false,
      };
      final memoria = MemoryContribution.fromJson(json);
      expect(memoria.kind, MemoryKind.racconto);
      expect(memoria.testo, 'Il vento sulle mura al tramonto.');
      expect(memoria.mediaUri, isNull);
      expect(memoria.riguarda, ['mura-urbane']);
      expect(memoria.contributorId, 'visitor_abc');
      expect(memoria.contributorKind, PersonKind.turista);
      expect(memoria.esperienzaId, 'exp-passeggiata-mura');
      expect(memoria.consenso, true);
      expect(memoria.licenza, 'CC-BY-SA-4.0');
      expect(memoria.curato, false);
      expect(memoria.toJson(), json);
    });

    test('applica il default curato=false quando il campo manca (nuovo conferimento)', () {
      final memoria = MemoryContribution.fromJson({
        'id': 'memoria_1',
        'kind': 'fotografia',
        'riguarda': ['torre-guinigi'],
        'contributor_id': 'visitor_xyz',
        'contributor_kind': 'cittadino',
        'consenso': true,
        'licenza': 'CC0-1.0',
        'creato_il': '2026-07-14T09:00:00.000Z',
      });
      expect(memoria.curato, false);
      expect(memoria.testo, isNull);
      expect(memoria.esperienzaId, isNull);
    });

    test('nessun campo in più: le chiavi del JSON sono esattamente quelle del contratto', () {
      final memoria = MemoryContribution(
        id: 'memoria_1',
        kind: MemoryKind.fotografia,
        riguarda: const ['torre-guinigi'],
        contributorId: 'visitor_xyz',
        contributorKind: PersonKind.cittadino,
        consenso: true,
        licenza: 'CC0-1.0',
        creatoIl: DateTime.utc(2026, 7, 14, 9),
      );
      expect(memoria.toJson().keys.toSet(), {
        'id',
        'kind',
        'testo',
        'media_uri',
        'riguarda',
        'contributor_id',
        'contributor_kind',
        'esperienza_id',
        'consenso',
        'licenza',
        'creato_il',
        'curato',
      });
    });

    test('il modello marca fedelmente un consenso negato: consenso resta false', () {
      final memoria = MemoryContribution(
        id: 'memoria_2',
        kind: MemoryKind.racconto,
        riguarda: const ['piazza-anfiteatro'],
        contributorId: 'visitor_xyz',
        contributorKind: PersonKind.turista,
        consenso: false,
        licenza: 'CC-BY-SA-4.0',
        creatoIl: DateTime.utc(2026, 7, 14, 9),
      );
      expect(memoria.consenso, false);
      expect(memoria.toJson()['consenso'], false);
    });
  });

  group('puoConferire — la regola di invio del conferimento (mai eccezioni sul consenso)', () {
    test('senza consenso non si può inviare, qualunque sia il resto', () {
      expect(puoConferire(consenso: false, licenza: 'CC-BY-SA-4.0', haContenuto: true), false);
      expect(puoConferire(consenso: false, licenza: '', haContenuto: false), false);
    });

    test('senza licenza tracciata (vuota o solo spazi) non si può inviare', () {
      expect(puoConferire(consenso: true, licenza: '', haContenuto: true), false);
      expect(puoConferire(consenso: true, licenza: '   ', haContenuto: true), false);
    });

    test('senza alcun contenuto (né testo né media) non si può inviare', () {
      expect(puoConferire(consenso: true, licenza: 'CC-BY-SA-4.0', haContenuto: false), false);
    });

    test('con consenso esplicito, licenza tracciata e un contenuto si può inviare', () {
      expect(puoConferire(consenso: true, licenza: 'CC-BY-SA-4.0', haContenuto: true), true);
    });
  });
}
