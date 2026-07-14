import 'memory_kind.dart';
import 'person_kind.dart';

/// Rispecchia `MemoryContribution` in `docs/DATA_CONTRACTS.md` §4 /
/// `packages/contracts`. Nessun campo in più.
///
/// "Ogni esperienza vissuta può alimentare la memoria della città. Non è un
/// archivio da riempire una volta: cresce con l'uso." `consenso` deve
/// essere `true` per essere persistito — nessuna eccezione — e `licenza` è
/// sempre tracciata (mai vuota). Il client non forza questi vincoli da
/// solo: li applica il BFF; qui il modello si limita a rappresentarli
/// fedelmente (vedi `lib/util/memory_gate.dart` per la regola di invio
/// lato UI).
class MemoryContribution {
  final String id;
  final MemoryKind kind;
  final String? testo;
  final String? mediaUri;
  final List<String> riguarda; // id di Luogo / Bottega / Artista nel grafo
  final String contributorId; // PSEUDONIMO, mai PII
  final PersonKind contributorKind;
  final String? esperienzaId; // da quale esperienza nasce
  final bool consenso; // OBBLIGATORIO: nessun conferimento senza consenso esplicito
  final String licenza; // es. "CC-BY-SA-4.0" — sempre tracciata
  final DateTime creatoIl;
  final bool curato; // revisione prima della pubblicazione

  const MemoryContribution({
    required this.id,
    required this.kind,
    this.testo,
    this.mediaUri,
    required this.riguarda,
    required this.contributorId,
    required this.contributorKind,
    this.esperienzaId,
    required this.consenso,
    required this.licenza,
    required this.creatoIl,
    this.curato = false,
  });

  factory MemoryContribution.fromJson(Map<String, dynamic> json) {
    return MemoryContribution(
      id: json['id'] as String,
      kind: memoryKindFromJson(json['kind'] as String),
      testo: json['testo'] as String?,
      mediaUri: json['media_uri'] as String?,
      riguarda: (json['riguarda'] as List<dynamic>).map((e) => e as String).toList(),
      contributorId: json['contributor_id'] as String,
      contributorKind: personKindFromJson(json['contributor_kind'] as String),
      esperienzaId: json['esperienza_id'] as String?,
      consenso: json['consenso'] as bool,
      licenza: json['licenza'] as String,
      creatoIl: DateTime.parse(json['creato_il'] as String),
      curato: json['curato'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'kind': kind.toJson(),
        'testo': testo,
        'media_uri': mediaUri,
        'riguarda': riguarda,
        'contributor_id': contributorId,
        'contributor_kind': contributorKind.toJson(),
        'esperienza_id': esperienzaId,
        'consenso': consenso,
        'licenza': licenza,
        'creato_il': creatoIl.toIso8601String(),
        'curato': curato,
      };
}
