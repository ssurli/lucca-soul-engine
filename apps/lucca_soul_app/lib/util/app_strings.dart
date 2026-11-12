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
  String get noConnection => _isEn ? 'No connection. Try again.' : 'Connessione assente. Riprova.';
  String get adaptNoConnection => _isEn
      ? 'Change not applied: no connection. Try again.'
      : 'Modifica non applicata: connessione assente. Riprova.';
  String get serviceUnavailable => _isEn
      ? 'The service is not responding. Try again shortly.'
      : 'Il servizio non risponde. Riprova tra poco.';
  String get adaptServiceUnavailable => _isEn
      ? 'Change not applied: the service is not responding. Try again shortly.'
      : 'Modifica non applicata: il servizio non risponde. Riprova tra poco.';

  /// Testo a schermo per un errore del BFF: mai url, codice o corpo.
  String serviceError({required bool connessioneAssente}) =>
      connessioneAssente ? noConnection : serviceUnavailable;

  /// Come [serviceError], nella card adattiva: dice che la modifica non è
  /// stata applicata (lo schermo mostra ancora l'ultimo risultato valido).
  String adaptServiceError({required bool connessioneAssente}) =>
      connessioneAssente ? adaptNoConnection : adaptServiceUnavailable;
  String get notOnMap => _isEn ? 'Not shown on the map' : 'Non compare sulla mappa';
  String get demoWorkshop =>
      _isEn ? 'Made-up workshop, for the demo' : 'Bottega inventata per la demo';
  String get retry => _isEn ? 'Retry' : 'Riprova';
  String get durationLabel => _isEn ? 'min' : 'min';
  String get adaptiveCardTitle => _isEn ? 'Something changed?' : 'È cambiato qualcosa?';
  String get signalRain => _isEn ? 'It is raining' : 'Piove';
  String get signalCrowd => _isEn ? 'Too crowded' : 'Troppa folla';
  String get signalTired => _isEn ? 'Tired' : 'Stanco/a';
  String get adaptSuccess => _isEn ? 'Itinerary rewritten' : 'Itinerario riscritto';
  String get adaptError => _isEn ? 'Could not adapt the itinerary.' : 'Non riesco ad adattare l\'itinerario.';
  String get emptyStops => _isEn ? 'No stops yet.' : 'Ancora nessuna tappa.';
  String get excludedStopsTitle => _isEn ? 'Left out of today' : 'Rimaste fuori oggi';
  String get mapCaption => _isEn
      ? 'Tap a number to open the stop. The line shows the order, not the route.'
      : "Tocca un numero per aprire la tappa. La linea indica l'ordine, non il percorso.";
  String get genericStop => _isEn ? 'Stop' : 'Tappa';
  String get legendLabel => _isEn ? 'Legend' : 'Leggenda';
  String get curiosityLabel => _isEn ? 'Did you know' : 'Curiosità';
  String sourceLabel(String fonte) => _isEn ? 'Source: $fonte' : 'Fonte: $fonte';
  String get keptNoAlternative =>
      _isEn ? 'Stays in plan: no suitable alternative' : 'Resta in programma: nessuna alternativa adatta';
  String noFurtherChange(String segnale) =>
      _isEn ? '$segnale: no further change.' : '$segnale: nessun altro cambiamento.';
  String get noStopsShort => _isEn ? 'no stops' : 'nessuna tappa';
  String stopsAndEnd(int n, String fine) => _isEn
      ? '$n ${n == 1 ? 'stop' : 'stops'}, ends $fine'
      : '$n ${n == 1 ? 'tappa' : 'tappe'}, fine $fine';
  String compareLine(String prima, String ora) =>
      _isEn ? 'Before: $prima · Now: $ora' : 'Prima: $prima · Ora: $ora';
  String get resetShortAction => _isEn ? 'Original plan' : 'Percorso iniziale';
  String get howToArrive => _isEn ? 'How to get here' : 'Come arrivo qui';
  String minutesOnFoot(int n) => _isEn ? 'about $n min on foot' : 'circa $n min a piedi';
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
  /// Spiegazione della licenza dalla sigla. Una sigla sconosciuta lancia
  /// [ArgumentError]: nessun testo di ripiego che possa descrivere una
  /// licenza diversa da quella inviata.
  String licenseExplanation(String sigla) {
    switch (sigla) {
      case 'CC-BY-SA-4.0':
        return _isEn
            ? 'Anyone can reuse and adapt your memory, even commercially, as long as they credit the source and keep the same licence.'
            : 'Chiunque può riusare e modificare il tuo ricordo, anche a fini commerciali, citando la fonte e mantenendo la stessa licenza.';
      case 'CC-BY-4.0':
        return _isEn
            ? 'Anyone can reuse and adapt your memory, even commercially, as long as they credit the source.'
            : 'Chiunque può riusare e modificare il tuo ricordo, anche a fini commerciali, citando la fonte.';
      case 'CC0-1.0':
        return _isEn
            ? 'You give up all rights: anyone can use your memory without conditions and without crediting anyone.'
            : 'Rinunci a ogni diritto: chiunque può usare il tuo ricordo senza condizioni e senza citare nessuno.';
    }
    throw ArgumentError.value(sigla, 'sigla', 'licenza sconosciuta');
  }

  String get licenseIrrevocable => _isEn
      ? 'This choice cannot be withdrawn: anyone who has already received the memory under this licence can keep using it.'
      : 'La scelta non si può ritirare: chi ha già ricevuto il ricordo con questa licenza può continuare a usarlo.';
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
  String get citizenEmpty => _isEn
      ? 'No curated memories yet for this place.'
      : 'Ancora nessun ricordo curato per questo luogo.';

  // --- Dashboard Urban Intelligence Index (Wave 4) --------------------------
  String get dashboardTitle => _isEn ? 'Urban dashboard' : 'Dashboard urbana';
  String get dashboardAudienceComune => _isEn ? 'Municipality' : 'Comune';
  String get dashboardAudienceHotel => 'Hotel';
  String get dashboardAudienceMuseo => _isEn ? 'Museum' : 'Museo';
  String get dashboardAudienceComuneHint => _isEn
      ? 'The overall cultural health of the city: flow distribution first, '
          'then the full dashboard of the eight indicators.'
      : 'La salute culturale complessiva della città: prima la distribuzione '
          'dei flussi, poi il cruscotto completo degli otto indicatori.';
  String get dashboardAudienceOperatorHint => _isEn
      ? 'Same data as the Municipality view, focused on the two indicators '
          'that show how this place can help spread visitor flows.'
      : 'Gli stessi dati della vista Comune, con il taglio sui due indicatori '
          'che mostrano come questo luogo può contribuire a distribuire i flussi.';

  String get dashboardPeriodLabel => _isEn ? 'Period' : 'Periodo';
  String get dashboardPreviousPeriod => _isEn ? 'Previous month' : 'Mese precedente';
  String get dashboardNextPeriod => _isEn ? 'Next month' : 'Mese successivo';

  String get dashboardLoadingIndex =>
      _isEn ? 'Computing the index…' : 'Sto calcolando l\'index…';
  String get dashboardLoadingFlows =>
      _isEn ? 'Computing the flow heatmap…' : 'Sto calcolando la heatmap dei flussi…';
  String get dashboardErrorIndex =>
      _isEn ? 'Indicators unavailable.' : 'Indicatori non disponibili.';
  String get dashboardErrorFlows =>
      _isEn ? 'Flow heatmap unavailable.' : 'Heatmap dei flussi non disponibile.';

  // Stato "dato insufficiente" (soglia k=10, privacy by design): MAI uno
  // zero, MAI un errore — uno stato esplicito e leggibile, distinto dai due
  // sopra.
  String get dashboardIndexUnavailableTitle =>
      _isEn ? 'Insufficient data for this period' : 'Dato insufficiente per questo periodo';
  String get dashboardIndexUnavailableFallback => _isEn
      ? 'Not enough aggregated activity this period to publish the index '
          'while keeping visitors anonymous.'
      : 'Non c\'è ancora abbastanza attività aggregata in questo periodo per '
          'pubblicare l\'index garantendo l\'anonimato dei visitatori.';
  String get dashboardCellUnavailableBadge => _isEn
      ? 'Insufficient data to guarantee anonymity'
      : 'Dato insufficiente per garantire l\'anonimato';

  String get dashboardIndexSectionTitle =>
      _isEn ? 'Urban Intelligence Index indicators' : 'Indicatori dell\'Urban Intelligence Index';
  String get dashboardFlowsTitle =>
      _isEn ? 'Flow distribution by place' : 'Distribuzione dei flussi per luogo';
  String get dashboardFlowsEmpty =>
      _isEn ? 'No place in the graph yet.' : 'Ancora nessun luogo nel grafo.';
  String get dashboardFlowsFilterDay => _isEn ? 'Day' : 'Giorno';
  String get dashboardFlowsFilterHour => _isEn ? 'Hour' : 'Ora';
  String get dashboardFlowsClearFilters => _isEn ? 'Clear filters' : 'Rimuovi filtri';
  String get dashboardFlowsAnyDay => _isEn ? 'Whole period' : 'Tutto il periodo';
  String get dashboardFlowsAnyHour => _isEn ? 'All hours' : 'Tutte le ore';

  // L'indicatore che ci giudica (CLAUDE.md): sempre in evidenza, mai
  // rimpicciolito.
  String get dashboardHeroLabel =>
      _isEn ? 'Flow distribution' : 'Distribuzione dei flussi';
  String get dashboardHeroDescription => _isEn
      ? 'How evenly visitor flows spread across the city: 1 = well '
          'distributed, 0 = concentrated (overtourism). This is the '
          'indicator this dashboard exists to show.'
      : '1 = flussi ben distribuiti in città, 0 = concentrati (overtourism). '
          'È l\'indicatore che questa dashboard esiste per mostrare a '
          'un\'amministrazione.';

  String get indicatorTempoMedioLabel =>
      _isEn ? 'Average experience time' : 'Tempo medio esperienza';
  String get indicatorCoinvolgimentoLabel => _isEn ? 'Engagement' : 'Coinvolgimento';
  String get indicatorSoddisfazioneLabel => _isEn ? 'Satisfaction' : 'Soddisfazione';
  String get indicatorSoddisfazioneUnavailable => _isEn
      ? 'No data source yet (no reviews/surveys in production)'
      : 'Nessuna fonte dati ancora (nessuna recensione/survey in produzione)';
  String get indicatorTassoRitornoLabel => _isEn ? 'Return rate' : 'Tasso di ritorno';
  String get indicatorNuoviPercorsiLabel => _isEn ? 'New paths' : 'Nuovi percorsi';
  String get indicatorAttivazioneLocaleLabel =>
      _isEn ? 'Local activation' : 'Attivazione locale';
  String get indicatorContributiMemoriaLabel =>
      _isEn ? 'Urban Memory contributions' : 'Contributi alla Urban Memory';

  // --- Grafica (ondata 4): testata, riepilogo del cambio ----------------------
  String photoBy(String autore) => _isEn ? 'Photo: $autore' : 'Foto: $autore';
  String get demoLabel => _isEn ? 'Demo' : 'Demo';
  String get onFoot => _isEn ? 'on foot' : 'a piedi';
  String stopsCount(int n) => _isEn ? (n == 1 ? '1 stop' : '$n stops') : (n == 1 ? '1 tappa' : '$n tappe');
  String get backToOriginalSummary => _isEn ? 'Back to the original plan.' : 'Percorso iniziale ripristinato.';
  String get nothingChangedSummary => _isEn ? 'no stop changed' : 'nessuna tappa cambiata';
  String changedStopsPart(int n) =>
      _isEn ? (n == 1 ? '1 stop changed' : '$n stops changed') : (n == 1 ? '1 tappa cambiata' : '$n tappe cambiate');
  String keptStopsPart(int n) =>
      _isEn ? '$n with no suitable alternative' : '$n senza alternativa adatta';
  String removedStopsPart(int n) =>
      _isEn ? (n == 1 ? '1 stop left out' : '$n stops left out') : (n == 1 ? '1 tappa tolta' : '$n tappe tolte');

  static const _giorniIt = ['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom'];
  static const _giorniEn = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  static const _mesiIt = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic'];
  static const _mesiEn = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  /// Data breve per la testata, es. "sab 12 dic" / "Sat 12 Dec".
  String shortDate(DateTime d) => _isEn
      ? '${_giorniEn[d.weekday - 1]} ${d.day} ${_mesiEn[d.month - 1]}'
      : '${_giorniIt[d.weekday - 1]} ${d.day} ${_mesiIt[d.month - 1]}';
}

/// Etichetta di accessibilità del logo delle Mura (testo prescritto dal
/// committente, uguale in ogni lingua).
const String kMuraLogoLabel = 'Le Mura di Lucca: dieci baluardi e una piattaforma';

/// Identificativo dell'app per le richieste di tile (User-Agent di OSM). Sta
/// qui perché il file è nell'allowlist della guardia città.
const String kUserAgentPackage = 'lucca_soul_app';
