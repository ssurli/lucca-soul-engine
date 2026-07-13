/// Rispecchia `EmotionalProfile` in `docs/DATA_CONTRACTS.md` §1.
///
/// Rappresentazione dinamica, temporanea e NON identificante di ciò che una
/// persona cerca in questo momento. Nessun campo qui è un dato personale.
class EmotionalProfile {
  final double curiosita; // 0..1 — "hai voglia di perderti?"
  final double contemplazione; // 0..1 — silenzio vs musica
  final double arte; // 0..1 — bellezza vs storie
  final bool conBambini;
  final int tempoDisponibileMin;
  final bool accessibilitaRichiesta;
  final bool haGiaVistoFirenze;
  final List<String> lingue;

  const EmotionalProfile({
    required this.curiosita,
    required this.contemplazione,
    required this.arte,
    required this.conBambini,
    required this.tempoDisponibileMin,
    this.accessibilitaRichiesta = false,
    this.haGiaVistoFirenze = false,
    this.lingue = const ['it'],
  });

  factory EmotionalProfile.fromJson(Map<String, dynamic> json) {
    return EmotionalProfile(
      curiosita: (json['curiosita'] as num).toDouble(),
      contemplazione: (json['contemplazione'] as num).toDouble(),
      arte: (json['arte'] as num).toDouble(),
      conBambini: json['con_bambini'] as bool,
      tempoDisponibileMin: json['tempo_disponibile_min'] as int,
      accessibilitaRichiesta: json['accessibilita_richiesta'] as bool? ?? false,
      haGiaVistoFirenze: json['ha_gia_visto_firenze'] as bool? ?? false,
      lingue: (json['lingue'] as List<dynamic>?)?.map((e) => e as String).toList() ??
          const ['it'],
    );
  }

  Map<String, dynamic> toJson() => {
        'curiosita': curiosita,
        'contemplazione': contemplazione,
        'arte': arte,
        'con_bambini': conBambini,
        'tempo_disponibile_min': tempoDisponibileMin,
        'accessibilita_richiesta': accessibilitaRichiesta,
        'ha_gia_visto_firenze': haGiaVistoFirenze,
        'lingue': lingue,
      };
}
