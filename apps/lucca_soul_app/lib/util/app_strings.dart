/// Localizzazione minima per la Wave 1.
///
/// L'app è multilingue tramite `EmotionalProfile.lingue` (non tramite le
/// impostazioni del device): la lingua mostrata nell'itinerario e nella
/// card adattiva segue la prima lingua del profilo restituito dal BFF.
/// Copre solo le stringhe di prodotto (non l'onboarding, che raccoglie la
/// lingua scelta esplicitamente prima ancora che esista un profilo).
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
}
