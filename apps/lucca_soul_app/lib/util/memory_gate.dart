/// Regola pura di abilitazione dell'invio di un conferimento a Urban
/// Memory: nessuna eccezione a `consenso == true`
/// (`docs/DATA_CONTRACTS.md` §4/§7 — "MemoryContribution.consenso deve
/// essere True per essere persistito. Nessuna eccezione.").
///
/// Estratta dal widget per essere testabile senza device/SDK grafico
/// (stesso principio di `itinerary_diff.dart`).
bool puoConferire({
  required bool consenso,
  required String licenza,
  required bool haContenuto,
}) {
  return consenso && licenza.trim().isNotEmpty && haContenuto;
}
