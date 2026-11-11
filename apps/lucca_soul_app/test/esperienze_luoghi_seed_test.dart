// Punto 5: kExperienceIdToPlaceId copre TUTTE le esperienze del seed che
// hanno place_id, con lo stesso luogo del seed.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/util/known_places.dart';

/// experience_id -> place_id letti dal seed generato
/// (`services/graph/cypher/01_seed_lucca.cypher`). Il `place_id` è la
/// prima riga `e.place_id = '...'` dopo il `MERGE (e:Esperienza ...)`,
/// prima del successivo `MERGE`.
Map<String, String> _esperienzeDelSeed() {
  final righe = const LineSplitter()
      .convert(File('../../services/graph/cypher/01_seed_lucca.cypher').readAsStringSync());
  final reEsperienza = RegExp(r"^MERGE \(e:Esperienza \{id: '([^']+)'\}\)");
  final rePlace = RegExp(r"^\s*e\.place_id = '([^']+)'");
  final esito = <String, String>{};
  String? corrente;
  for (final riga in righe) {
    final m = reEsperienza.firstMatch(riga);
    if (m != null) {
      corrente = m.group(1);
      continue;
    }
    if (riga.startsWith('MERGE ') || riga.startsWith('MATCH ')) {
      corrente = null;
      continue;
    }
    final p = rePlace.firstMatch(riga);
    if (corrente != null && p != null) {
      esito[corrente] = p.group(1)!;
      corrente = null;
    }
  }
  return esito;
}

void main() {
  test('il seed contiene esperienze con place_id (il parser funziona)', () {
    expect(_esperienzeDelSeed(), isNotEmpty);
  });

  test('ogni esperienza del seed con place_id è nella mappa, con lo stesso luogo', () {
    final seed = _esperienzeDelSeed();
    for (final e in seed.entries) {
      expect(kExperienceIdToPlaceId.containsKey(e.key), isTrue, reason: '${e.key} manca dalla mappa');
      expect(kExperienceIdToPlaceId[e.key], e.value, reason: 'luogo diverso per ${e.key}');
    }
  });

  test('la mappa non contiene esperienze assenti dal seed', () {
    final seed = _esperienzeDelSeed();
    for (final id in kExperienceIdToPlaceId.keys) {
      expect(seed.containsKey(id), isTrue, reason: '$id non è nel seed');
    }
  });

  test('chiesa-san-francesco è nel menu Cittadino con il suo nome', () {
    expect(kKnownPlaceIds, contains('chiesa-san-francesco'));
    expect(kKnownPlaceNames['chiesa-san-francesco'], 'Chiesa di San Francesco');
  });
}
