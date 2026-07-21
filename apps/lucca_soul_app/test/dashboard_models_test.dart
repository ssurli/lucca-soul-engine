// Test di contratto per la dashboard Urban Intelligence Index (Wave 4):
// verificano che i modelli Dart producano/consumino esattamente i campi
// JSON canonici di `docs/DATA_CONTRACTS.md` §7 / `packages/contracts`, e
// soprattutto che lo stato "dato insufficiente" (soglia k=10) resti sempre
// distinguibile da un valore disponibile — mai uno zero fabbricato lato
// client. Nessuna dipendenza da widget: gira senza device (stesso
// principio di `test/models_test.dart`).
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/dashboard_flows_response.dart';
import 'package:lucca_soul_app/models/dashboard_index_response.dart';
import 'package:lucca_soul_app/models/flow_cell.dart';
import 'package:lucca_soul_app/models/urban_intelligence_index.dart';

void main() {
  group('UrbanIntelligenceIndex', () {
    test('fromJson/toJson usa i campi canonici italiani (§7)', () {
      final json = {
        'periodo': '2026-07',
        'tempo_medio_esperienza_min': 42.0,
        'coinvolgimento': 0.68,
        'soddisfazione': 4.2,
        'tasso_ritorno': 0.31,
        'nuovi_percorsi': 0.5,
        'attivazione_locale': 0.44,
        'distribuzione_flussi': 0.72,
        'contributi_memoria': 17,
      };
      final index = UrbanIntelligenceIndex.fromJson(json);
      expect(index.periodo, '2026-07');
      expect(index.distribuzioneFlussi, 0.72);
      expect(index.contributiMemoria, 17);
      expect(index.soddisfazione, 4.2);
      expect(index.toJson(), json);
    });

    test('soddisfazione resta null quando manca (nessuna fonte dati oggi), mai stimata', () {
      final index = UrbanIntelligenceIndex.fromJson({
        'periodo': '2026-07',
        'tempo_medio_esperienza_min': 30.0,
        'coinvolgimento': 0.5,
        'soddisfazione': null,
        'tasso_ritorno': 0.2,
        'nuovi_percorsi': 0.3,
        'attivazione_locale': 0.4,
        'distribuzione_flussi': 0.6,
        'contributi_memoria': 3,
      });
      expect(index.soddisfazione, isNull);
      expect(index.toJson()['soddisfazione'], isNull);
    });
  });

  group('DashboardIndexResponse', () {
    test('disponibile=true porta l\'index e nessun motivo di indisponibilità', () {
      final risposta = DashboardIndexResponse.fromJson({
        'periodo': '2026-07',
        'disponibile': true,
        'index': {
          'periodo': '2026-07',
          'tempo_medio_esperienza_min': 42.0,
          'coinvolgimento': 0.68,
          'soddisfazione': null,
          'tasso_ritorno': 0.31,
          'nuovi_percorsi': 0.5,
          'attivazione_locale': 0.44,
          'distribuzione_flussi': 0.72,
          'contributi_memoria': 17,
        },
        'motivo_indisponibilita': null,
      });
      expect(risposta.disponibile, true);
      expect(risposta.index, isNotNull);
      expect(risposta.index!.distribuzioneFlussi, 0.72);
      expect(risposta.motivoIndisponibilita, isNull);
    });

    test('disponibile=false NON porta un index fabbricato: solo il motivo in italiano', () {
      final risposta = DashboardIndexResponse.fromJson({
        'periodo': '2026-03',
        'disponibile': false,
        'index': null,
        'motivo_indisponibilita': 'meno di 10 persone distinte nel periodo',
      });
      expect(risposta.disponibile, false);
      expect(risposta.index, isNull);
      expect(risposta.motivoIndisponibilita, 'meno di 10 persone distinte nel periodo');
    });
  });

  group('FlowCell', () {
    test('disponibile=true porta un conteggio_tappe intero', () {
      final cella = FlowCell.fromJson({
        'place_id': 'mura-urbane',
        'disponibile': true,
        'conteggio_tappe': 128,
      });
      expect(cella.disponibile, true);
      expect(cella.conteggioTappe, 128);
    });

    test('disponibile=false porta conteggio_tappe null: MAI zero al posto della soppressione', () {
      final cella = FlowCell.fromJson({
        'place_id': 'orto-botanico',
        'disponibile': false,
        'conteggio_tappe': null,
      });
      expect(cella.disponibile, false);
      expect(cella.conteggioTappe, isNull);
      // Uno zero vero e una soppressione sono stati diversi nel contratto:
      // il modello Dart non li confonde in un `?? 0`.
      expect(cella.conteggioTappe == 0, false);
    });
  });

  group('DashboardFlowsResponse', () {
    test('fromJson/toJson con giorno e ora presenti (filtro applicato)', () {
      final json = {
        'periodo': '2026-07',
        'giorno': '2026-07-14',
        'ora': 15,
        'celle': [
          {'place_id': 'mura-urbane', 'disponibile': true, 'conteggio_tappe': 42},
          {'place_id': 'san-frediano', 'disponibile': false, 'conteggio_tappe': null},
        ],
      };
      final risposta = DashboardFlowsResponse.fromJson(json);
      expect(risposta.periodo, '2026-07');
      expect(risposta.giorno, DateTime.parse('2026-07-14'));
      expect(risposta.ora, 15);
      expect(risposta.celle, hasLength(2));
      expect(risposta.celle[0].disponibile, true);
      expect(risposta.celle[1].disponibile, false);
      expect(risposta.toJson(), json);
    });

    test('fromJson senza filtro: giorno e ora restano null, mai un default fabbricato', () {
      final risposta = DashboardFlowsResponse.fromJson({
        'periodo': '2026-07',
        'giorno': null,
        'ora': null,
        'celle': <Map<String, dynamic>>[],
      });
      expect(risposta.giorno, isNull);
      expect(risposta.ora, isNull);
      expect(risposta.celle, isEmpty);
    });
  });
}
