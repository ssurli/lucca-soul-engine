import '../models/memory_kind.dart';
import '../models/person_kind.dart';

/// Localizzazione minima per la Wave 1 (itinerario/card adattiva) e la
/// Wave 2 (conferimento a Urban Memory, vista Cittadino).
///
/// L'app è multilingue tramite `EmotionalProfile.lingue` (non tramite le
/// impostazioni del device): la lingua mostrata nell'itinerario e nella
/// card adattiva segue la prima lingua del profilo restituito dal BFF. La
/// vista Cittadino, che non nasce da un `EmotionalProfile`, offre un
/// selettore di lingua proprio, con lo stesso meccanismo.
class AppStrings {
  final String code;

  const AppStrings._(this.code);

  static const _supported = {'it', 'en'};

  factory AppStrings.forLanguages(List<String> lingue) {
    final code = lingue.firstWhere(_supported.contains, orElse: () => 'it');
    return AppStrings._(code);
  }

  bool get _isEn => code == 'en';

  String get itineraryTitle => _isEn ? 'Your day in Lucca' : 'La tua giornata a Lucca';
  String get itineraryLoading => _isEn ? 'Composing your itinerary…' : 'Sto componendo l\'itinerario…';
  String get itineraryError => _isEn ? 'Could not reach the BFF.' : 'Non riesco a contattare il BFF.';
  String get retry => _isEn ? 'Retry' : 'Riprova';
  String get durationLabel => _isEn ? 'min' : 'min';
  String get adaptedBadge => _isEn ? 'Rewritten' : 'Riscritta';
  String get adaptiveCardTitle => _isEn ? 'Something changed?' : 'È cambiato qualcosa?';
  String get signalRain => _isEn ? 'It is raining' : 'Piove';
  String get signalCrowd => _isEn ? 'Walls are crowded' : 'Mura affollate';
  String get signalTired => _isEn ? 'I am tired' : 'Sono stanco/a';
  String get adaptSuccess => _isEn ? 'Itinerary rewritten' : 'Itinerario riscritto';
  String get adaptError => _isEn ? 'Could not adapt the itinerary.' : 'Non riesco ad adattare l\'itinerario.';
  String get emptyStops => _isEn ? 'No stops yet.' : 'Ancora nessuna tappa.';
  String get changedStop => _isEn ? 'Changed by the signal' : 'Cambiata dal segnale';

  // --- Urban Memory (Wave 2): conferimento contestuale --------------------
  String get leaveMemoryAction => _isEn ? 'Leave a memory' : 'Lascia un ricordo';
  String get memorySheetTitle =>
      _isEn ? 'A contribution to Urban Memory' : 'Un contributo alla Urban Memory';
  String get memoryIntro => _isEn
      ? 'What you share here joins the city\'s collective memory, after a human '
          'review. No personal data: only your session pseudonym.'
      : 'Quello che condividi qui entra nella memoria collettiva della città, dopo '
          'una revisione. Nessun dato personale: solo il tuo pseudonimo di sessione.';
  String get memoryKindLabel => _isEn ? 'What kind of memory is it?' : 'Che tipo di ricordo è?';
  String get memoryTextLabel => _isEn ? 'Your story' : 'Il tuo racconto';
  String get memoryTextHint => _isEn ? 'A few lines are enough…' : 'Bastano poche righe…';
  String get memoryMediaLabel =>
      _isEn ? 'Link to a photo or audio (optional)' : 'Link a una foto o audio (opzionale)';
  String get memoryMediaHint => 'https://…';
  String get memoryLicenseLabel => _isEn ? 'License' : 'Licenza';
  String get memoryConsentLabel => _isEn
      ? 'I explicitly consent to share this contribution with Urban Memory.'
      : 'Do il mio consenso esplicito a condividere questo contributo con la Urban Memory.';
  String get memoryConsentDetail => _isEn
      ? 'Without this consent the contribution cannot be kept. Nothing is '
          'published before a curator review.'
      : 'Senza questo consenso il contributo non può essere conservato. Niente '
          'viene pubblicato prima di una revisione.';
  String get memorySubmit => _isEn ? 'Contribute' : 'Conferisci';
  String get memorySuccess => _isEn
      ? 'Thank you: your contribution is now in review.'
      : 'Grazie: il tuo contributo è ora in revisione.';
  String get memorySubmitError =>
      _isEn ? 'We could not save the contribution.' : 'Non siamo riusciti a salvare il contributo.';

  String memoryKindName(MemoryKind kind) {
    switch (kind) {
      case MemoryKind.racconto:
        return _isEn ? 'Story' : 'Racconto';
      case MemoryKind.fotografia:
        return _isEn ? 'Photograph' : 'Fotografia';
      case MemoryKind.musica:
        return _isEn ? 'Music' : 'Musica';
      case MemoryKind.mestiere:
        return _isEn ? 'Craft' : 'Mestiere';
      case MemoryKind.ricetta:
        return _isEn ? 'Recipe' : 'Ricetta';
      case MemoryKind.dialetto:
        return _isEn ? 'Dialect' : 'Dialetto';
      case MemoryKind.testimonianza:
        return _isEn ? 'Testimony' : 'Testimonianza';
    }
  }

  String contributorKindLabel(PersonKind kind) {
    switch (kind) {
      case PersonKind.turista:
        return _isEn ? 'Visitor' : 'Turista';
      case PersonKind.cittadino:
        return _isEn ? 'Citizen' : 'Cittadino';
    }
  }

  // --- Vista Cittadino ------------------------------------------------------
  String get citizenTitle => _isEn ? 'Citizen view' : 'Vista Cittadino';
  String get citizenIntro => _isEn
      ? 'Citizens do not pay: they feed Urban Memory, and that is the condition '
          'for the whole system\'s social sustainability.'
      : 'Il Cittadino non paga: alimenta la Urban Memory, ed è la condizione di '
          'sostenibilità sociale di tutto il sistema.';
  String get citizenPlaceLabel => _isEn ? 'Place' : 'Luogo';
  String get citizenLoading => _isEn ? 'Loading memories…' : 'Sto caricando i ricordi…';
  String get citizenError => _isEn ? 'Could not reach the BFF.' : 'Non riesco a contattare il BFF.';
  String get citizenEmpty => _isEn
      ? 'No curated memories yet for this place.'
      : 'Ancora nessun ricordo curato per questo luogo.';
}
