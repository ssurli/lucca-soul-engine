// L'app invia sempre `istante` (UTC, con Z); DEMO_ISTANTE sostituisce
// l'orologio del device per istante, ora e data di fallback.
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/meteo.dart';
import 'package:lucca_soul_app/models/signal.dart';
import 'package:lucca_soul_app/util/clock.dart';
import 'package:lucca_soul_app/util/signal_presets.dart';

void main() {
  tearDown(() => Orologio.impostaPerTest(null));

  group('istante nel segnale', () {
    test('toJson lo serializza ISO 8601 UTC con Z, accanto a ora e data', () {
      final t = Signal.orologio(DateTime.utc(2026, 12, 12, 9));
      final j = Signal(
        meteo: Meteo.sereno,
        affollamento: const {},
        stanchezza: 0.1,
        ora: t.ora,
        data: t.data,
        istante: t.istante,
      ).toJson();
      expect(j['istante'], endsWith('Z'));
      expect(DateTime.parse(j['istante'] as String), DateTime.utc(2026, 12, 12, 9));
      expect(j['ora'], isA<String>());
      expect(j['data'], isA<String>());
    });

    test('un istante non UTC viene normalizzato con Z', () {
      final s = Signal.orologio(DateTime(2026, 6, 1, 12));
      expect(s.istante.isUtc, isTrue);
    });

    test('baselineSignal e segnali simulati portano istante', () {
      Orologio.impostaPerTest(() => DateTime.utc(2026, 12, 12, 9));
      final base = baselineSignal();
      expect(base.istante, DateTime.utc(2026, 12, 12, 9));
      for (final k in SimulatedSignalKind.values) {
        final s = buildSimulatedSignal(k, base);
        expect(s.toJson()['istante'], base.toJson()['istante']);
      }
    });

    test('ora e data di fallback derivano dallo stesso istante (toLocal)', () {
      final fisso = DateTime.utc(2026, 12, 12, 9);
      Orologio.impostaPerTest(() => fisso);
      final s = baselineSignal();
      final loc = fisso.toLocal();
      expect(s.ora.hour, loc.hour);
      expect(s.data, DateTime(loc.year, loc.month, loc.day));
    });
  });

  group('DEMO_ISTANTE', () {
    test('inizializza con un valore valido fissa l\'orologio', () {
      Orologio.inizializza(demo: '2026-12-12T09:00:00Z');
      expect(Orologio.adesso(), DateTime.utc(2026, 12, 12, 9));
    });

    test('vuoto: orologio reale', () {
      Orologio.inizializza(demo: '');
      final d = Orologio.adesso().difference(DateTime.now().toUtc()).abs();
      expect(d.inSeconds, lessThan(5));
    });

    test('non parsabile o senza fuso: FormatException, nessun default muto', () {
      expect(() => Orologio.inizializza(demo: 'domani'), throwsFormatException);
      expect(() => Orologio.inizializza(demo: '2026-12-12T09:00:00'), throwsFormatException);
    });
  });

  group('TappaEsclusa.esito', () {
    test('tagliata_orario e valori ignoti sopravvivono al parsing', () {
      for (final esito in ['tagliata_orario', 'esito_dal_futuro']) {
        final t = TappaEsclusa.fromJson(
            {'experience_id': 'x', 'esito': esito, 'reason': 'perché'},
        );
        expect(t.esito, esito);
        expect(t.toJson()['esito'], esito);
      }
    });
  });
}
