import '../models/itinerary.dart';

/// Gli esiti di taglio del contratto (`EsitoAdattamento`), in un solo punto.
/// L'ordine della lista e' l'ordine dei gruppi a schermo.
class EsitoTaglio {
  static const stanchezza = 'tagliata_stanchezza';
  static const tettoGiornata = 'tagliata_tetto_giornata';
  static const orario = 'tagliata_orario';
  static const sospesa = 'tagliata_sospesa';

  static const ordinati = [stanchezza, tettoGiornata, orario, sospesa];
}

/// Le tappe escluse che condividono lo stesso `esito`.
class GruppoEscluse {
  final String esito;
  final List<TappaEsclusa> tappe;

  const GruppoEscluse(this.esito, this.tappe);

  /// True se tutte le tappe del gruppo hanno lo stesso `reason`: la frase si
  /// scrive una volta sola, nel titolo del gruppo.
  bool get reasonUniforme => tappe.every((t) => t.reason == tappe.first.reason);
}

class EscluseRaggruppate {
  /// Solo i gruppi non vuoti, nell'ordine di [EsitoTaglio.ordinati].
  final List<GruppoEscluse> gruppi;

  /// Esito fuori dai quattro noti: nessun raggruppamento, ordine d'arrivo.
  /// Si mostrano DOPO i gruppi (non si perdono, non si mescolano a quelli noti).
  final List<TappaEsclusa> sconosciute;

  const EscluseRaggruppate(this.gruppi, this.sconosciute);
}

/// Raggruppa per `esito` (mai per il testo del `reason`). Logica pura.
EscluseRaggruppate raggruppaEscluse(List<TappaEsclusa> escluse) {
  final gruppi = <GruppoEscluse>[];
  for (final esito in EsitoTaglio.ordinati) {
    final tappe = escluse.where((t) => t.esito == esito).toList();
    if (tappe.isNotEmpty) gruppi.add(GruppoEscluse(esito, tappe));
  }
  final sconosciute =
      escluse.where((t) => !EsitoTaglio.ordinati.contains(t.esito)).toList();
  return EscluseRaggruppate(gruppi, sconosciute);
}
