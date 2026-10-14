import 'package:flutter/material.dart';

import '../api/bff_client.dart';
import '../api/bff_exception.dart';
import '../models/emotional_profile.dart';
import '../models/onboarding.dart';
import 'itinerary_screen.dart';

/// Una singola risposta possibile a una domanda della conversazione:
/// l'etichetta è quello che l'utente vede (chip), `risposta` è il testo
/// libero italiano che finisce in `OnboardingAnswer.risposta` — il parsing
/// semantico verso `EmotionalProfile` è del servizio RAG, non del client.
class OnboardingOption {
  final String label;
  final String risposta;

  const OnboardingOption(this.label, this.risposta);
}

/// Una domanda della conversazione di onboarding.
class OnboardingQuestion {
  final String domandaId;
  final String testo;
  final List<OnboardingOption> opzioni;

  const OnboardingQuestion({
    required this.domandaId,
    required this.testo,
    required this.opzioni,
  });
}

/// Le sette domande della conversazione (`docs/DATA_CONTRACTS.md` §7,
/// `domanda_id` allineati alla consegna di Wave 1). Non una guida a form:
/// una conversazione breve, pensata per stare sotto i due minuti.
const List<OnboardingQuestion> kOnboardingQuestions = [
  OnboardingQuestion(
    domandaId: 'perdersi',
    testo: 'Hai voglia di perderti?',
    opzioni: [
      OnboardingOption('Sì, senza meta', 'Sì, mi piace perdermi senza una meta precisa'),
      OnboardingOption('Un po\'', 'Un po\', ma con qualche punto fermo'),
      OnboardingOption('No, un percorso chiaro', 'No, preferisco un percorso chiaro e preciso'),
    ],
  ),
  OnboardingQuestion(
    domandaId: 'silenzio_musica',
    testo: 'Silenzio o musica?',
    opzioni: [
      OnboardingOption('Silenzio', 'Silenzio e contemplazione'),
      OnboardingOption('Un mix', 'Un mix tra silenzio e musica'),
      OnboardingOption('Musica', 'Musica ed energia'),
    ],
  ),
  OnboardingQuestion(
    domandaId: 'bellezza_storie',
    testo: 'Ti attira di più la bellezza o le storie?',
    opzioni: [
      OnboardingOption('La bellezza', 'La bellezza silenziosa dei luoghi'),
      OnboardingOption('Entrambe', 'Un po\' di bellezza e un po\' di storie'),
      OnboardingOption('Le storie', 'I racconti e gli aneddoti'),
    ],
  ),
  OnboardingQuestion(
    domandaId: 'bambini',
    testo: 'Con bambini?',
    opzioni: [
      OnboardingOption('Sì', 'Sì, sono con bambini'),
      OnboardingOption('No', 'No, non sono con bambini'),
    ],
  ),
  OnboardingQuestion(
    domandaId: 'tempo',
    testo: 'Quanto tempo hai a disposizione?',
    opzioni: [
      OnboardingOption('Un\'ora', 'Circa un\'ora, poco tempo'),
      OnboardingOption('Mezza giornata', 'Mezza giornata, circa tre ore'),
      OnboardingOption('Tutto il giorno', 'Tutto il giorno, senza fretta'),
    ],
  ),
  OnboardingQuestion(
    domandaId: 'accessibilita',
    testo: 'Hai bisogno di percorsi accessibili?',
    opzioni: [
      OnboardingOption('Sì', 'Sì, mi serve un percorso accessibile'),
      OnboardingOption('No', 'No, nessuna esigenza di accessibilità'),
    ],
  ),
  OnboardingQuestion(
    domandaId: 'firenze',
    testo: 'Hai già visto Firenze?',
    opzioni: [
      OnboardingOption('Sì', 'Sì, ho già visto Firenze'),
      OnboardingOption('No', 'No, non ho ancora visto Firenze'),
    ],
  ),
];

/// Le lingue in cui può svolgersi la conversazione. Scelta esplicita
/// dell'utente prima che esista un `EmotionalProfile` (che a sua volta
/// porta `lingue` per il resto dell'app).
const Map<String, String> kOnboardingLanguages = {
  'it': 'Italiano',
  'en': 'English',
};

/// Schermata di onboarding: una conversazione breve (non una guida) che in
/// meno di due minuti produce un `EmotionalProfile` chiamando
/// `POST /session/onboarding`.
class OnboardingScreen extends StatefulWidget {
  final BffClient bffClient;
  final String personId;

  const OnboardingScreen({super.key, required this.bffClient, required this.personId});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final PageController _pageController = PageController();
  final Map<String, String> _risposte = {};
  String _lingua = 'it';
  int _stepCorrente = 0;
  bool _inviando = false;
  String? _erroreInvio;

  bool get _completato => _risposte.length == kOnboardingQuestions.length;

  void _scegli(OnboardingQuestion domanda, OnboardingOption opzione) {
    setState(() {
      _risposte[domanda.domandaId] = opzione.risposta;
      _erroreInvio = null;
    });
    if (_stepCorrente < kOnboardingQuestions.length - 1) {
      final prossimo = _stepCorrente + 1;
      _pageController.animateToPage(
        prossimo,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    }
  }

  Future<void> _invia() async {
    setState(() {
      _inviando = true;
      _erroreInvio = null;
    });
    try {
      final request = OnboardingRequest(
        risposte: kOnboardingQuestions
            .map((d) => OnboardingAnswer(domandaId: d.domandaId, risposta: _risposte[d.domandaId]!))
            .toList(),
        lingua: _lingua,
      );
      final EmotionalProfile profilo = await widget.bffClient.onboarding(request);
      if (!mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => ItineraryScreen(
            bffClient: widget.bffClient,
            personId: widget.personId,
            profile: profilo,
          ),
        ),
      );
    } on BffException catch (error) {
      setState(() => _erroreInvio = error.message);
    } finally {
      if (mounted) setState(() => _inviando = false);
    }
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Lucca Soul Lab'),
        actions: [
          DropdownButton<String>(
            value: _lingua,
            underline: const SizedBox.shrink(),
            items: kOnboardingLanguages.entries
                .map((e) => DropdownMenuItem(value: e.key, child: Text(e.value)))
                .toList(),
            onChanged: (value) {
              if (value != null) setState(() => _lingua = value);
            },
          ),
          const SizedBox(width: 12),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            LinearProgressIndicator(
              value: (_stepCorrente + 1) / kOnboardingQuestions.length,
              minHeight: 4,
            ),
            Expanded(
              child: PageView.builder(
                controller: _pageController,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: kOnboardingQuestions.length,
                onPageChanged: (index) => setState(() => _stepCorrente = index),
                itemBuilder: (context, index) {
                  final domanda = kOnboardingQuestions[index];
                  return _QuestionView(
                    domanda: domanda,
                    selezionata: _risposte[domanda.domandaId],
                    onScegli: (opzione) => _scegli(domanda, opzione),
                  );
                },
              ),
            ),
            if (_erroreInvio != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text(_erroreInvio!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _completato && !_inviando ? _invia : null,
                  child: _inviando
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Scopri il mio itinerario'),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _QuestionView extends StatelessWidget {
  final OnboardingQuestion domanda;
  final String? selezionata;
  final ValueChanged<OnboardingOption> onScegli;

  const _QuestionView({required this.domanda, required this.selezionata, required this.onScegli});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(domanda.testo, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 24),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: domanda.opzioni.map((opzione) {
              final selezionato = selezionata == opzione.risposta;
              return ChoiceChip(
                label: Text(opzione.label),
                selected: selezionato,
                onSelected: (_) => onScegli(opzione),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}
