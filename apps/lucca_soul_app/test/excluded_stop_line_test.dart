import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/util/app_strings.dart';
import 'package:lucca_soul_app/util/excluded_stop_line.dart';

final _it = AppStrings.forLanguages(['it']);

TappaEsclusa _esclusa(String id, String reason, {String? titolo}) =>
    TappaEsclusa(experienceId: id, esito: 'esclusa', reason: reason, titolo: titolo);

void main() {
  test('la riga contiene il titolo e il reason, non l\'id', () {
    final riga = rigaTappaEsclusa(_esclusa('exp-museo-x', 'Chiuso oggi', titolo: 'Museo X'), _it);
    expect(riga, 'Museo X: Chiuso oggi');
    expect(riga, isNot(contains('exp-')));
  });

  test('senza titolo la riga usa l\'etichetta generica, mai l\'id', () {
    final riga = rigaTappaEsclusa(_esclusa('exp-museo-x', 'Chiuso oggi'), _it);
    expect(riga, 'Tappa: Chiuso oggi');
    expect(riga, isNot(contains('exp-')));
  });

  test('etichetta generica in inglese', () {
    final riga = rigaTappaEsclusa(_esclusa('exp-a', 'Closed'), AppStrings.forLanguages(['en']));
    expect(riga, 'Stop: Closed');
  });

  test('tre tappe con titoli diversi e stesso motivo danno tre righe diverse', () {
    const reason = 'Tagliata per mancanza di tempo';
    final righe = [
      for (final t in ['Torre A', 'Torre B', 'Torre C'])
        rigaTappaEsclusa(_esclusa('exp-${t.toLowerCase()}', reason, titolo: t), _it),
    ];
    expect(righe.toSet().length, 3);
    for (final r in righe) {
      expect(r, contains(reason));
    }
  });
}
