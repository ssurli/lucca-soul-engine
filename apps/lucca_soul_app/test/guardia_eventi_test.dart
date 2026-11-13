// Guardia sul sorgente: se il codice dell'app chiama l'endpoint /events,
// la costante kAppRegistraEventi deve essere true. Altrimenti la dashboard
// direbbe "l'app non registra i percorsi" mentre li registra.
// Nessuna esclusione di file: si scartano solo i commenti.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/util/registrazione_eventi.dart';

/// Rimuove commenti di riga (// e ///) e di blocco, rispettando le stringhe.
String _senzaCommenti(String src) {
  final out = StringBuffer();
  var i = 0;
  String? quote;
  var raw = false;
  while (i < src.length) {
    final c = src[i];
    final next = i + 1 < src.length ? src[i + 1] : '';
    if (quote != null) {
      out.write(c);
      if (c == r'\' && !raw && next.isNotEmpty) {
        out.write(next);
        i += 2;
        continue;
      }
      if (c == quote) quote = null;
      i++;
    } else if (c == '/' && next == '/') {
      while (i < src.length && src[i] != '\n') {
        i++;
      }
    } else if (c == '/' && next == '*') {
      final fine = src.indexOf('*/', i + 2);
      i = fine == -1 ? src.length : fine + 2;
    } else {
      if (c == "'" || c == '"') {
        quote = c;
        raw = i > 0 && src[i - 1] == 'r';
      }
      out.write(c);
      i++;
    }
  }
  return out.toString();
}

List<File> _fileLib() {
  final lib = Directory('lib');
  if (!lib.existsSync()) return [];
  return lib
      .listSync(recursive: true)
      .whereType<File>()
      .where((f) => f.path.endsWith('.dart'))
      .toList();
}

bool _finisceCon(File f, String suffisso) => f.path.replaceAll('\\', '/').endsWith(suffisso);

void main() {
  test('la guardia legge davvero i file di lib/ (non passa a vuoto)', () {
    final files = _fileLib();
    expect(
      files,
      isNotEmpty,
      reason: 'nessun .dart trovato in lib/: eseguire da apps/lucca_soul_app',
    );
    expect(files.any((f) => _finisceCon(f, 'lib/main.dart')), isTrue);
    expect(files.any((f) => _finisceCon(f, 'lib/api/bff_client.dart')), isTrue);
  });

  test('il filtro dei commenti scarta i commenti ma non le stringhe', () {
    expect(_senzaCommenti("// '/events'\nfinal a = 1;"), isNot(contains('/events')));
    expect(_senzaCommenti('/* /events */ final a = 1;'), isNot(contains('/events')));
    expect(_senzaCommenti("final a = '/events'; // x"), contains("'/events'"));
    expect(_senzaCommenti("final a = 'http://x'; final b = '/events';"), contains("'/events'"));
  });

  test('chiamate a /events solo se kAppRegistraEventi è true', () {
    final trovati = <String>[];
    for (final f in _fileLib()) {
      final righe = _senzaCommenti(f.readAsStringSync()).split('\n');
      for (var n = 0; n < righe.length; n++) {
        if (righe[n].contains('/events')) {
          trovati.add('${f.path}: riga ${n + 1} del testo senza commenti');
        }
      }
    }
    if (trovati.isNotEmpty) {
      expect(
        kAppRegistraEventi,
        isTrue,
        reason: "L'app chiama l'endpoint /events ma kAppRegistraEventi è false: "
            "la dashboard direbbe che i percorsi non vengono registrati. "
            "Imposta kAppRegistraEventi = true in lib/util/registrazione_eventi.dart "
            "(e rimuovi l'avviso di prova) oppure togli la chiamata. Occorrenze:\n"
            '${trovati.join('\n')}',
      );
    }
  });
}
