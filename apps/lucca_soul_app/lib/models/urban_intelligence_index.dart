/// Rispecchia `UrbanIntelligenceIndex` in `docs/DATA_CONTRACTS.md` §7 /
/// `packages/contracts`. Nessun campo in più.
///
/// "La salute CULTURALE della città, non solo quella economica." Tutti i
/// valori sono già aggregati e anonimizzati dal BFF (soglia k=10 provata al
/// confine dell'API, `DashboardIndexResponse`): questo modello non
/// re-implementa alcun controllo di privacy, si limita a rappresentare
/// fedelmente ciò che il BFF ha già giudicato pubblicabile.
class UrbanIntelligenceIndex {
  final String periodo; // es. "2026-07"
  final double tempoMedioEsperienzaMin;
  final double coinvolgimento; // 0..1
  final double? soddisfazione; // 0..5, null finché non esiste una fonte dati
  // reale: MAI un valore stimato lato client per riempire questo buco.
  final double tassoRitorno; // 0..1
  final double nuoviPercorsi; // 0..1 — itinerari emergenti e inattesi
  final double attivazioneLocale; // 0..1 — quanto il territorio minore è raggiunto
  final double distribuzioneFlussi; // 0..1 — "l'indicatore che ci giudica"
  final int contributiMemoria;

  const UrbanIntelligenceIndex({
    required this.periodo,
    required this.tempoMedioEsperienzaMin,
    required this.coinvolgimento,
    this.soddisfazione,
    required this.tassoRitorno,
    required this.nuoviPercorsi,
    required this.attivazioneLocale,
    required this.distribuzioneFlussi,
    required this.contributiMemoria,
  });

  factory UrbanIntelligenceIndex.fromJson(Map<String, dynamic> json) {
    return UrbanIntelligenceIndex(
      periodo: json['periodo'] as String,
      tempoMedioEsperienzaMin: (json['tempo_medio_esperienza_min'] as num).toDouble(),
      coinvolgimento: (json['coinvolgimento'] as num).toDouble(),
      soddisfazione: (json['soddisfazione'] as num?)?.toDouble(),
      tassoRitorno: (json['tasso_ritorno'] as num).toDouble(),
      nuoviPercorsi: (json['nuovi_percorsi'] as num).toDouble(),
      attivazioneLocale: (json['attivazione_locale'] as num).toDouble(),
      distribuzioneFlussi: (json['distribuzione_flussi'] as num).toDouble(),
      contributiMemoria: json['contributi_memoria'] as int,
    );
  }

  Map<String, dynamic> toJson() => {
        'periodo': periodo,
        'tempo_medio_esperienza_min': tempoMedioEsperienzaMin,
        'coinvolgimento': coinvolgimento,
        'soddisfazione': soddisfazione,
        'tasso_ritorno': tassoRitorno,
        'nuovi_percorsi': nuoviPercorsi,
        'attivazione_locale': attivazioneLocale,
        'distribuzione_flussi': distribuzioneFlussi,
        'contributi_memoria': contributiMemoria,
      };
}
