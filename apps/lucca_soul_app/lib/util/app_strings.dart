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
      _isEn ? 'Could not reach the BFF for the index.' : 'Non riesco a contattare il BFF per l\'index.';
  String get dashboardErrorFlows => _isEn
      ? 'Could not reach the BFF for the flow heatmap.'
      : 'Non riesco a contattare il BFF per la heatmap dei flussi.';

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
}
