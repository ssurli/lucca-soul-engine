/// Indica se l'app registra gli eventi di percorso chiamando POST /events.
///
/// Oggi l'app NON chiama /events, quindi la dashboard resta vuota e mostra
/// l'avviso di versione di prova. Va messa a `true` solo quando l'app
/// chiamerà davvero POST /events. Un test di guardia sul sorgente fallisce
/// se lib/ chiama /events mentre questa costante è `false`.
const bool kAppRegistraEventi = false;
