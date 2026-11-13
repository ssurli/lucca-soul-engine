// Nome del prodotto sul web: manifest e index.html (lettura dei file).
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('manifest.json: name «Lucca Soul Lab», short_name «Lucca Soul»', () {
    final m = jsonDecode(File('web/manifest.json').readAsStringSync())
        as Map<String, dynamic>;
    expect(m['name'], 'Lucca Soul Lab');
    expect(m['short_name'], 'Lucca Soul');
  });

  test(
      'index.html: title «Lucca Soul Lab», apple-mobile-web-app-title «Lucca Soul»',
      () {
    final h = File('web/index.html').readAsStringSync();
    expect(h, contains('<title>Lucca Soul Lab</title>'));
    expect(
      RegExp(r'<meta\s+name="apple-mobile-web-app-title"\s+content="Lucca Soul"\s*/?>')
          .hasMatch(h),
      isTrue,
    );
  });
}
