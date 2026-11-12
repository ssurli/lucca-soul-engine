// Voce 5: guardia sul sorgente. L'unico punto di log dell'app e' `_log` in
// bff_client.dart, e scrive solo in debug (`kDebugMode`): in release url e
// corpi di risposta non escono. Un secondo `debugPrint(` o un `print(` in
// lib/ rompe la guardia.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Toglie commenti di riga e di blocco (semplice: non capisce le stringhe;
/// `://` degli URL non e' trattato come inizio di commento).
String senzaCommenti(String sorgente) => sorgente
    .replaceAll(RegExp(r'/\*[\s\S]*?\*/'), '')
    .replaceAll(RegExp(r'(?<!:)//[^\n]*'), '');

/// `print(` come chiamata, non come suffisso di `debugPrint(`/`blueprint(`.
final RegExp _print = RegExp(r'(?<![A-Za-z0-9_$])print\s*\(');
final RegExp _debugPrint = RegExp(r'(?<![A-Za-z0-9_$])debugPrint\s*\(');

List<File> _fileDart() => Directory('lib')
    .listSync(recursive: true)
    .whereType<File>()
    .where((f) => f.path.endsWith('.dart'))
    .toList();

void main() {
  group('il rilevatore', () {
    test('non scambia debugPrint( per print(', () {
      expect(_print.hasMatch('debugPrint(x);'), isFalse);
      expect(_print.hasMatch('  print(x);'), isTrue);
      expect(_print.hasMatch('print (x);'), isTrue);
      expect(_print.hasMatch('foo.print(x);'), isTrue);
      expect(_debugPrint.allMatches('debugPrint(a); debugPrint(b);').length, 2);
    });

    test('ignora i commenti', () {
      const s = '// print(x)\n/* debugPrint(y) */\nfinal u = "http://a"; // print(z)\n';
      expect(_print.hasMatch(senzaCommenti(s)), isFalse);
      expect(_debugPrint.hasMatch(senzaCommenti(s)), isFalse);
      expect(senzaCommenti(s), contains('http://a'));
    });
  });

  group('lib/', () {
    test('si leggono dei sorgenti (la guardia non e vuota)', () {
      final files = _fileDart();
      expect(files.length, greaterThan(20));
      expect(files.any((f) => f.path.replaceAll('\\', '/').endsWith('lib/api/bff_client.dart')), isTrue);
    });

    test('nessun print( in tutto lib/', () {
      final colpevoli = <String>[
        for (final f in _fileDart())
          if (_print.hasMatch(senzaCommenti(f.readAsStringSync()))) f.path,
      ];
      expect(colpevoli, isEmpty);
    });

    test('debugPrint( compare una sola volta in tutto lib/, dentro bff_client.dart', () {
      final conteggi = <String, int>{
        for (final f in _fileDart())
          f.path.replaceAll('\\', '/'): _debugPrint.allMatches(senzaCommenti(f.readAsStringSync())).length,
      }..removeWhere((_, n) => n == 0);
      expect(conteggi.values.fold<int>(0, (a, b) => a + b), 1, reason: '$conteggi');
      expect(conteggi.keys.single, endsWith('lib/api/bff_client.dart'));
    });

    test('quell unico debugPrint( e nell helper _log, preceduto da kDebugMode', () {
      final src = senzaCommenti(File('lib/api/bff_client.dart').readAsStringSync());
      final helper = RegExp(r'void _log\(String \w+\)\s*\{\s*if \(kDebugMode\)\s*\{?\s*debugPrint\(');
      expect(helper.allMatches(src).length, 1);
      // L'import deve portare kDebugMode accanto a debugPrint.
      expect(src, matches(RegExp(r"import 'package:flutter/foundation\.dart'[^;]*\bkDebugMode\b[^;]*;")));
    });

    test('_log e l unico helper di log: nessun altro uso di kDebugMode da cui scrivere', () {
      // Ogni scrittura passa da _log: il client non chiama altre funzioni di log.
      final src = senzaCommenti(File('lib/api/bff_client.dart').readAsStringSync());
      expect(RegExp(r'\bstdout\b|\bstderr\b|developer\.log|\blog\(').hasMatch(src.replaceAll('_log(', '')), isFalse);
    });
  });
}
