import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/screens/onboarding_screen.dart';

void main() {
  test('la domanda su Firenze resta nel codice ma non viene posta', () {
    expect(kOnboardingQuestions.map((d) => d.domandaId), contains('firenze'));
    expect(kDomandeVisibili.map((d) => d.domandaId), isNot(contains('firenze')));
    expect(kDomandeVisibili, hasLength(kOnboardingQuestions.length - 1));
    expect(kDomandeVisibili, hasLength(6));
  });
}
