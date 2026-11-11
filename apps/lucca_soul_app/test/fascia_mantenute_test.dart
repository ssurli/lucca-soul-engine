// Correzione 3: la fascia dice "senza alternativa adatta", invariabile al plurale.
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/util/app_strings.dart';

void main() {
  test('keptStopsPart: singolare e plurale', () {
    final it = AppStrings.forLanguages(['it']);
    final en = AppStrings.forLanguages(['en']);
    expect(it.keptStopsPart(1), '1 senza alternativa adatta');
    expect(it.keptStopsPart(3), '3 senza alternativa adatta');
    expect(en.keptStopsPart(1), '1 with no suitable alternative');
    expect(en.keptStopsPart(3), '3 with no suitable alternative');
  });

  test('l\'etichetta sulla card non cambia', () {
    expect(AppStrings.forLanguages(['it']).keptNoAlternative, 'Resta in programma: nessuna alternativa adatta');
  });
}
