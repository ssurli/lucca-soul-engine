import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/util/excluded_stop_line.dart';

TappaEsclusa _esclusa(String id, String reason) =>
    TappaEsclusa(experienceId: id, esito: 'esclusa', reason: reason);

void main() {
  test('la riga contiene experience_id e reason', () {
    final riga = rigaTappaEsclusa(_esclusa('museo-x', 'Chiuso oggi'));
    expect(riga, contains('museo-x'));
    expect(riga, contains('Chiuso oggi'));
    expect(riga, 'museo-x: Chiuso oggi');
  });

  test('tre tappe tagliate per lo stesso motivo danno tre righe diverse', () {
    const reason = 'Tagliata per mancanza di tempo';
    final righe = [
      for (final id in ['esperienza-a', 'esperienza-b', 'esperienza-c'])
        rigaTappaEsclusa(_esclusa(id, reason)),
    ];
    expect(righe.toSet().length, 3);
    for (final r in righe) {
      expect(r, contains(reason));
    }
  });
}
