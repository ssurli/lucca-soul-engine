import 'urban_intelligence_index.dart';

/// Rispecchia `DashboardIndexResponse` in `docs/DATA_CONTRACTS.md` §7 /
/// `packages/contracts`. Uscita di `GET /dashboard/index`.
///
/// Vincolo di coerenza dello stesso contratto (`model_validator` lato BFF,
/// qui rispecchiato per costruzione: nessun costruttore pubblico che
/// permetta di violarlo — l'unico modo di ottenere un'istanza è
/// `fromJson`, che riflette fedelmente ciò che il BFF ha già validato):
/// `disponibile=true` implica `index` non nullo e `motivoIndisponibilita`
/// nullo; `disponibile=false` implica il contrario. Nessuno stato
/// intermedio, MAI un cruscotto fabbricato con valori a zero quando il
/// periodo è "dato insufficiente" (soglia k=10, privacy by design).
class DashboardIndexResponse {
  final String periodo;
  final bool disponibile;
  final UrbanIntelligenceIndex? index; // popolato SOLO se disponibile=true
  final String? motivoIndisponibilita; // popolato SOLO se disponibile=false, IT

  const DashboardIndexResponse._({
    required this.periodo,
    required this.disponibile,
    this.index,
    this.motivoIndisponibilita,
  });

  factory DashboardIndexResponse.fromJson(Map<String, dynamic> json) {
    final disponibile = json['disponibile'] as bool;
    final indexJson = json['index'] as Map<String, dynamic>?;
    return DashboardIndexResponse._(
      periodo: json['periodo'] as String,
      disponibile: disponibile,
      index: indexJson == null ? null : UrbanIntelligenceIndex.fromJson(indexJson),
      motivoIndisponibilita: json['motivo_indisponibilita'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'periodo': periodo,
        'disponibile': disponibile,
        'index': index?.toJson(),
        'motivo_indisponibilita': motivoIndisponibilita,
      };
}
