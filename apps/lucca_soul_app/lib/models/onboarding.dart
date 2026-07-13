/// Rispecchia `OnboardingAnswer` in `docs/DATA_CONTRACTS.md` §7.
/// Una risposta della conversazione ("Hai voglia di perderti?"...), in
/// testo libero: il parsing semantico avviene lato servizio RAG, non qui.
class OnboardingAnswer {
  final String domandaId;
  final String risposta;

  const OnboardingAnswer({required this.domandaId, required this.risposta});

  Map<String, dynamic> toJson() => {
        'domanda_id': domandaId,
        'risposta': risposta,
      };
}

/// Rispecchia `OnboardingRequest` in `docs/DATA_CONTRACTS.md` §7.
/// Input di `POST /session/onboarding` (output: `EmotionalProfile`).
class OnboardingRequest {
  final List<OnboardingAnswer> risposte;
  final String lingua;

  const OnboardingRequest({required this.risposte, this.lingua = 'it'});

  Map<String, dynamic> toJson() => {
        'risposte': risposte.map((r) => r.toJson()).toList(),
        'lingua': lingua,
      };
}
