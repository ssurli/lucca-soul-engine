// Test di contratto: verificano che i modelli Dart producano/consumino
// esattamente i campi JSON canonici di `docs/DATA_CONTRACTS.md` /
// `packages/contracts`. Nessuna dipendenza da widget: girano senza device.
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/adapt_request.dart';
import 'package:lucca_soul_app/models/emotional_profile.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/meteo.dart';
import 'package:lucca_soul_app/models/onboarding.dart';
import 'package:lucca_soul_app/models/person_kind.dart';
import 'package:lucca_soul_app/models/signal.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/models/visitor_context.dart';

void main() {
  group('TimeHms', () {
    test('fa il round-trip di "HH:MM:SS"', () {
      final t = TimeHms.parse('09:30:00');
      expect(t.toJson(), '09:30:00');
      expect(t.label, '09:30');
    });

    test('rifiuta un orario fuori scala', () {
      expect(() => TimeHms.parse('25:00:00'), throwsFormatException);
    });
  });

  group('Signal.data', () {
    Signal base({DateTime? data}) => Signal(
          meteo: Meteo.sereno,
          affollamento: const {},
          stanchezza: 0.1,
          ora: TimeHms.parse('09:00:00'),
          data: data,
        );

    test('serializza "YYYY-MM-DD" con zero-padding', () {
      expect(base(data: DateTime(2026, 3, 7)).toJson()['data'], '2026-03-07');
    });

    test('senza data il campo non viene inviato; fromJson lo rilegge', () {
      expect(base().toJson().containsKey('data'), isFalse);
      final s = Signal.fromJson(base(data: DateTime(2026, 12, 1)).toJson());
      expect(s.data, DateTime(2026, 12, 1));
    });

    test('orologio: ora e data da una sola lettura (mezzanotte)', () {
      final t = Signal.orologio(DateTime(2026, 1, 2, 0, 0, 1));
      expect(t.ora.toJson(), '00:00:01');
      expect(Signal.formatIsoDate(t.data), '2026-01-02');
    });
  });

  group('EmotionalProfile', () {
    test('fromJson/toJson usa i campi canonici italiani', () {
      final json = {
        'curiosita': 0.8,
        'contemplazione': 0.3,
        'arte': 0.6,
        'con_bambini': false,
        'tempo_disponibile_min': 180,
        'accessibilita_richiesta': false,
        'ha_gia_visto_firenze': true,
        'lingue': ['it', 'en'],
      };
      final profile = EmotionalProfile.fromJson(json);
      expect(profile.curiosita, 0.8);
      expect(profile.conBambini, false);
      expect(profile.tempoDisponibileMin, 180);
      expect(profile.haGiaVistoFirenze, true);
      expect(profile.lingue, ['it', 'en']);
      expect(profile.toJson(), json);
    });

    test('applica i default quando i campi opzionali mancano', () {
      final profile = EmotionalProfile.fromJson({
        'curiosita': 0.5,
        'contemplazione': 0.5,
        'arte': 0.5,
        'con_bambini': false,
        'tempo_disponibile_min': 60,
      });
      expect(profile.accessibilitaRichiesta, false);
      expect(profile.haGiaVistoFirenze, false);
      expect(profile.lingue, ['it']);
    });
  });

  group('Signal', () {
    test('fromJson/toJson preserva affollamento per place_id', () {
      final json = {
        'meteo': 'pioggia',
        'affollamento': {'mura-urbane': 0.9},
        'stanchezza': 0.4,
        'ora': '14:05:00',
        'eventi_attivi': <String>[],
      };
      final signal = Signal.fromJson(json);
      expect(signal.meteo, Meteo.pioggia);
      expect(signal.affollamento['mura-urbane'], 0.9);
      expect(signal.toJson(), json);
    });
  });

  group('VisitorContext', () {
    test('serializza person_id, kind e i campi canonici del contesto', () {
      final context = VisitorContext(
        personId: 'visitor_abc',
        kind: PersonKind.cittadino,
        profile: const EmotionalProfile(
          curiosita: 0.5,
          contemplazione: 0.5,
          arte: 0.5,
          conBambini: false,
          tempoDisponibileMin: 90,
        ),
        signal: Signal(
          meteo: Meteo.sereno,
          affollamento: const {},
          stanchezza: 0.1,
          ora: TimeHms.parse('09:00:00'),
        ),
        luoghiGiaVisti: const ['duomo-san-martino'],
      );
      final json = context.toJson();
      expect(json['person_id'], 'visitor_abc');
      expect(json['kind'], 'cittadino');
      expect(json['luoghi_gia_visti'], ['duomo-san-martino']);
      expect(json.containsKey('profile'), true);
      expect(json.containsKey('signal'), true);
    });
  });

  group('Itinerary', () {
    test('fromJson analizza le tappe con orario, durata e reason', () {
      final json = {
        'person_id': 'visitor_abc',
        'stops': [
          {
            'experience_id': 'passeggiata-mura',
            'arrivo': '09:00:00',
            'durata_min': 60,
            'reason': 'Le mura sono libere di mattina presto',
          },
        ],
        'generated_at': '2026-07-13T08:00:00.000Z',
        'adattato_da_segnale': false,
      };
      final itinerary = Itinerary.fromJson(json);
      expect(itinerary.stops, hasLength(1));
      expect(itinerary.stops.first.reason, 'Le mura sono libere di mattina presto');
      expect(itinerary.stops.first.arrivo.label, '09:00');
      expect(itinerary.adattatoDaSegnale, false);
    });
  });

  group('OnboardingRequest', () {
    test('serializza domanda_id e risposta in testo libero', () {
      const request = OnboardingRequest(
        risposte: [
          OnboardingAnswer(domandaId: 'perdersi', risposta: 'Sì, mi piace perdermi'),
        ],
        lingua: 'it',
      );
      final json = request.toJson();
      expect(json['lingua'], 'it');
      expect(json['risposte'], [
        {'domanda_id': 'perdersi', 'risposta': 'Sì, mi piace perdermi'},
      ]);
    });
  });

  group('AdaptRequest', () {
    test('porta itinerario e segnale, nessun campo in più', () {
      final request = AdaptRequest(
        itinerary: Itinerary(
          personId: 'visitor_abc',
          stops: const [],
          generatedAt: DateTime.utc(2026, 7, 13, 8),
        ),
        signal: Signal(
          meteo: Meteo.pioggia,
          affollamento: const {},
          stanchezza: 0.2,
          ora: TimeHms.parse('10:00:00'),
        ),
      );
      final json = request.toJson();
      expect(json.keys.toSet(), {'itinerary', 'signal'});
    });
  });
}
