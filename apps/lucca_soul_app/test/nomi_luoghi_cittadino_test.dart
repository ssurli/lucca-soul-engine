// Correzione 4: il menu Cittadino mostra i nomi dei luoghi, non gli id.
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lucca_soul_app/api/bff_client.dart';
import 'package:lucca_soul_app/screens/citizen_screen.dart';
import 'package:lucca_soul_app/util/known_places.dart';

void main() {
  test('ogni id noto ha un nome e la mappa non ha id extra', () {
    expect(kKnownPlaceNames.keys.toSet(), kKnownPlaceIds.toSet());
  });

  test('ogni Luogo del seed e in kKnownPlaceIds e il numero coincide con il seed', () {
    final cypher = File('../../services/graph/cypher/01_seed_lucca.cypher').readAsStringSync();
    final idNelSeed = RegExp(r"MERGE \(l:Luogo \{id: '([^']+)'\}\)")
        .allMatches(cypher)
        .map((m) => m.group(1)!)
        .toList();
    expect(idNelSeed, isNotEmpty, reason: 'nessun Luogo letto dal seed: regex o percorso errati');
    expect(idNelSeed.toSet().length, idNelSeed.length, reason: 'id duplicati nel seed');
    final mancanti = idNelSeed.where((id) => !kKnownPlaceIds.contains(id)).toList();
    expect(mancanti, isEmpty, reason: 'Luoghi del seed assenti da kKnownPlaceIds');
    expect(kKnownPlaceIds.length, idNelSeed.length);
    expect(kKnownPlaceIds.toSet().length, kKnownPlaceIds.length, reason: 'duplicati in kKnownPlaceIds');
  });

  test('i nomi coincidono con il seed del grafo', () {
    final cypher = File('../../services/graph/cypher/01_seed_lucca.cypher').readAsStringSync();
    final righe = const LineSplitter().convert(cypher);
    final nelSeed = <String, String>{};
    final reId = RegExp(r"MERGE \(l:Luogo \{id: '([^']+)'\}\)");
    final reNome = RegExp(r"l\.nome = '(.*?)', l\.categoria");
    for (var i = 0; i < righe.length - 1; i++) {
      final m = reId.firstMatch(righe[i]);
      if (m == null) continue;
      final n = reNome.firstMatch(righe[i + 1]);
      expect(n, isNotNull, reason: 'nome mancante per ${m.group(1)}');
      nelSeed[m.group(1)!] = n!.group(1)!.replaceAll(r"\'", "'");
    }
    for (final e in kKnownPlaceNames.entries) {
      expect(nelSeed.containsKey(e.key), isTrue, reason: '${e.key} assente dal seed');
      expect(e.value, nelSeed[e.key], reason: 'nome diverso per ${e.key}');
    }
  });

  testWidgets('il menu mostra i nomi in ordine e la selezione passa l\'id', (t) async {
    final richiesti = <String>[];
    final client = BffClient(
      baseUrl: Uri.parse('http://test'),
      httpClient: MockClient((req) async {
        richiesti.add(req.url.path);
        return http.Response('[]', 200, headers: {'content-type': 'application/json; charset=utf-8'});
      }),
    );
    t.view.physicalSize = const Size(800, 1600);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    addTearDown(t.view.resetDevicePixelRatio);
    await t.pumpWidget(MaterialApp(home: CitizenScreen(bffClient: client, personId: 'c')));
    await t.pumpAndSettle();
    await t.tap(find.byType(DropdownButtonFormField<String>));
    await t.pumpAndSettle();

    final attesi = kKnownPlaceNames.values.toList()..sort((a, b) => a.toLowerCase().compareTo(b.toLowerCase()));
    final voci = t
        .widgetList<DropdownButton<String>>(find.byType(DropdownButton<String>))
        .map((d) => d.items ?? const <DropdownMenuItem<String>>[])
        .firstWhere((items) => items.length == kKnownPlaceIds.length);
    expect(voci.map((DropdownMenuItem<String> v) => (v.child as Text).data).toList(), attesi);
    expect(voci.map((DropdownMenuItem<String> v) => v.value).toList(), [for (final n in attesi) kKnownPlaceNames.entries.firstWhere((e) => e.value == n).key]);

    await t.tap(find.text('Duomo di San Martino').last);
    await t.pumpAndSettle();
    expect(richiesti.last, contains('duomo-san-martino'));
  });
}
