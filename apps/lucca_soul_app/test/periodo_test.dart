// Test degli helper puri di `lib/util/periodo.dart`: formattazione dei
// parametri di query "periodo"/"giorno" attesi da `GET /dashboard/*`
// (`docs/DATA_CONTRACTS.md` §7/§8) e navigazione mese per mese senza
// dipendere da `intl`.
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/util/periodo.dart';

void main() {
  group('formatPeriodo', () {
    test('formatta anno e mese con zero padding ("YYYY-MM")', () {
      expect(formatPeriodo(DateTime(2026, 7)), '2026-07');
      expect(formatPeriodo(DateTime(2026, 12)), '2026-12');
    });
  });

  group('formatDateYmd', () {
    test('formatta la data con zero padding ("YYYY-MM-DD"), ignora l\'orario', () {
      expect(formatDateYmd(DateTime(2026, 7, 4, 18, 30)), '2026-07-04');
    });
  });

  group('meseSpostatoDi', () {
    test('avanza di un mese dentro lo stesso anno', () {
      expect(meseSpostatoDi(DateTime(2026, 7), 1), DateTime(2026, 8));
    });

    test('arretra di un mese dentro lo stesso anno', () {
      expect(meseSpostatoDi(DateTime(2026, 7), -1), DateTime(2026, 6));
    });

    test('avanza oltre dicembre: passa all\'anno successivo', () {
      expect(meseSpostatoDi(DateTime(2026, 12), 1), DateTime(2027, 1));
    });

    test('arretra oltre gennaio: passa all\'anno precedente', () {
      expect(meseSpostatoDi(DateTime(2026, 1), -1), DateTime(2025, 12));
    });
  });
}
