import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/api/bff_client.dart';

void main() {
  test('define presente: vince, anche sul web', () {
    final u = risolviBffUrl(
      define: 'http://localhost:9000',
      isWeb: true,
      base: Uri.parse('http://altro:1234/x'),
    );
    expect(u.toString(), 'http://localhost:9000');
  });

  test('web senza define: stessa origine, percorsi assoluti', () {
    final u = risolviBffUrl(
      define: '',
      isWeb: true,
      base: Uri.parse('https://demo.example.org:8443/app/?istante=1#/x'),
    );
    expect(u.toString(), 'https://demo.example.org:8443/');
    expect(
      u.resolve('/itinerary').toString(),
      'https://demo.example.org:8443/itinerary',
    );
    final senzaPorta = risolviBffUrl(
      define: '',
      isWeb: true,
      base: Uri.parse('http://127.0.0.1/'),
    );
    expect(senzaPorta.toString(), 'http://127.0.0.1/');
  });

  test('non web senza define: localhost:8000', () {
    final u =
        risolviBffUrl(define: '', isWeb: false, base: Uri.parse('file:///x'));
    expect(u.toString(), 'http://localhost:8000');
  });
}
