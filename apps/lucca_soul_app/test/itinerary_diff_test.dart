import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/models/itinerary.dart';
import 'package:lucca_soul_app/models/time_hms.dart';
import 'package:lucca_soul_app/util/itinerary_diff.dart';

ItineraryStop _stop(String id, {String arrivo = '09:00:00', String reason = 'motivo', String? esito}) =>
    ItineraryStop(
      experienceId: id,
      arrivo: TimeHms.parse(arrivo),
      durataMin: 30,
      reason: reason,
      esitoAdattamento: esito,
    );

void main() {
  test('nessuna tappa evidenziata se l\'itinerario non e\' stato adattato (esito null)', () {
    expect(tappeSostituite([_stop('a'), _stop('b')]), isEmpty);
  });

  test('evidenzia solo la tappa sostituita (es. pioggia -> al chiuso)', () {
    final dopo = [_stop('laboratorio', esito: 'sostituita'), _stop('museo', esito: 'non_toccata')];
    expect(tappeSostituite(dopo), {0});
  });

  test('un reason diverso non evidenzia mai, se l\'esito non e\' sostituita', () {
    expect(tappeSostituite([_stop('a', reason: 'riscritto', esito: 'non_toccata')]), isEmpty);
  });

  test('uno slittamento dell\'arrivo non evidenzia mai', () {
    expect(tappeSostituite([_stop('a', arrivo: '15:30:00', esito: 'non_toccata')]), isEmpty);
  });

  test('mantenuta_senza_alternativa non e\' "Cambiata": ha il proprio indicatore', () {
    final s = _stop('a', esito: 'mantenuta_senza_alternativa');
    expect(tappaSostituita(s), isFalse);
    expect(tappaMantenutaSenzaAlternativa(s), isTrue);
    expect(tappeSostituite([s]), isEmpty);
  });

  test('sequenza reale demo|curioso|pioggia-15: evidenziate solo la prima e l\'ultima', () {
    const esiti = [
      'sostituita', 'non_toccata', 'non_toccata', 'non_toccata', 'non_toccata', 'sostituita',
    ];
    const ids = [
      'exp-interno-san-michele', 'exp-interno-san-frediano', 'exp-santi-giovanni-reparata',
      'exp-duomo-volto-santo', 'exp-chiesa-chiostro-san-francesco', 'exp-sortita-san-paolino',
    ];
    // Arrivi slittati rispetto all'originale (15:00, 15:35, 16:15, 17:05, 17:50, 18:30).
    const arrivi = ['15:00:00', '15:30:00', '16:10:00', '17:00:00', '17:45:00', '18:25:00'];
    final dopo = [
      for (var i = 0; i < ids.length; i++) _stop(ids[i], arrivo: arrivi[i], reason: 'r$i', esito: esiti[i]),
    ];
    expect(tappeSostituite(dopo), {0, 5});
  });
}
