import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/util/itinerary_diff.dart';

ItineraryStop _stop(String id, {String reason = 'motivo'}) => ItineraryStop(
      experienceId: id,
      arrivo: TimeHms.parse('09:00:00'),
      durataMin: 30,
      reason: reason,
    );

void main() {
  test('nessuna tappa cambiata se le liste sono identiche', () {
    final prima = [_stop('a'), _stop('b')];
    final dopo = [_stop('a'), _stop('b')];
    expect(tappeCambiate(prima: prima, dopo: dopo), isEmpty);
  });

  test('rileva la sostituzione di una tappa (es. pioggia -> al chiuso)', () {
    final prima = [_stop('passeggiata-mura'), _stop('museo-guinigi')];
    final dopo = [_stop('laboratorio-liuteria'), _stop('museo-guinigi')];
    expect(tappeCambiate(prima: prima, dopo: dopo), {0});
  });

  test('rileva un reason cambiato anche a parità di experience_id', () {
    final prima = [_stop('a', reason: 'motivo iniziale')];
    final dopo = [_stop('a', reason: 'motivo riscritto per affollamento')];
    expect(tappeCambiate(prima: prima, dopo: dopo), {0});
  });

  test('marca come cambiate le tappe aggiunte oltre la lunghezza precedente', () {
    final prima = [_stop('a')];
    final dopo = [_stop('a'), _stop('b')];
    expect(tappeCambiate(prima: prima, dopo: dopo), {1});
  });
}
