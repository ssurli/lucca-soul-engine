/// Rispecchia `FlowCell` in `docs/DATA_CONTRACTS.md` §7 / `packages/contracts`.
/// Una riga di heatmap per un luogo, uscita di `GET /dashboard/flows`.
///
/// Gated INDIPENDENTEMENTE dalle altre celle sulla soglia k=10 dei
/// `person_id` distinti di QUESTA cella. Espone SOLO `disponibile` e il
/// conteggio (o `null` se soppressa): MAI un conteggio di popolazione.
/// Vincolo di coerenza (rispecchiato per costruzione, stesso principio di
/// `DashboardIndexResponse`): `disponibile=true` implica `conteggioTappe`
/// non nullo; `disponibile=false` implica `conteggioTappe` nullo — la UI
/// non deve MAI presentare una cella soppressa come uno zero vero: sono due
/// stati diversi, sempre distinguibili.
class FlowCell {
  final String placeId;
  final bool disponibile;
  final int? conteggioTappe; // null se soppressa (sotto k=10 person_id distinti)

  const FlowCell._({required this.placeId, required this.disponibile, this.conteggioTappe});

  factory FlowCell.fromJson(Map<String, dynamic> json) {
    return FlowCell._(
      placeId: json['place_id'] as String,
      disponibile: json['disponibile'] as bool,
      conteggioTappe: json['conteggio_tappe'] as int?,
    );
  }

  Map<String, dynamic> toJson() => {
        'place_id': placeId,
        'disponibile': disponibile,
        'conteggio_tappe': conteggioTappe,
      };
}
