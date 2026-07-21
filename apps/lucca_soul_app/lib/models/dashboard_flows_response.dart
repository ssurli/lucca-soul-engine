import '../util/periodo.dart';
import 'flow_cell.dart';

/// Rispecchia `DashboardFlowsResponse` in `docs/DATA_CONTRACTS.md` §7 /
/// `packages/contracts`. Uscita di `GET /dashboard/flows`. SEMPRE una riga
/// per luogo (mai una combinatoria luogo×giorno×ora in un solo payload):
/// `giorno`/`ora`, se presenti, sono il filtro applicato dal server alla
/// STESSA lista di celle, non una dimensione aggiuntiva del payload.
class DashboardFlowsResponse {
  final String periodo;
  final DateTime? giorno; // filtro applicato alla richiesta, se presente (solo data)
  final int? ora; // 0..23, fascia oraria applicata, se presente
  final List<FlowCell> celle;

  const DashboardFlowsResponse({
    required this.periodo,
    this.giorno,
    this.ora,
    required this.celle,
  });

  factory DashboardFlowsResponse.fromJson(Map<String, dynamic> json) {
    final giornoStr = json['giorno'] as String?;
    return DashboardFlowsResponse(
      periodo: json['periodo'] as String,
      giorno: giornoStr == null ? null : DateTime.parse(giornoStr),
      ora: json['ora'] as int?,
      celle: (json['celle'] as List<dynamic>)
          .map((e) => FlowCell.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
        'periodo': periodo,
        'giorno': giorno == null ? null : formatDateYmd(giorno!),
        'ora': ora,
        'celle': celle.map((c) => c.toJson()).toList(),
      };
}
