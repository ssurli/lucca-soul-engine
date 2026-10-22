import '../models/adapt_request.dart';
import '../models/emotional_profile.dart';
import '../models/itinerary.dart';
import 'signal_presets.dart';

/// Stato degli interruttori dei segnali simulati, con la storia per
/// "Annulla". Immutabile e puro (nessun Flutter): ogni operazione restituisce
/// un nuovo stato.
class SignalToggleState {
  /// Interruttori accesi adesso.
  final Set<SimulatedSignalKind> accesi;

  /// Pila degli stati precedenti (l'ultimo elemento e' il piu' recente).
  final List<Set<SimulatedSignalKind>> storia;

  const SignalToggleState({this.accesi = const {}, this.storia = const []});

  bool get puoAnnullare => storia.isNotEmpty;
  bool get nessunoAcceso => accesi.isEmpty;

  /// Interruttore: la seconda pressione spegne. Il cambio entra nella storia.
  SignalToggleState premi(SimulatedSignalKind kind) {
    final nuovi = {...accesi};
    if (!nuovi.remove(kind)) nuovi.add(kind);
    return SignalToggleState(accesi: nuovi, storia: [...storia, accesi]);
  }

  /// Torna allo stato precedente all'ultimo cambio (senza storia: invariato).
  SignalToggleState annulla() {
    if (storia.isEmpty) return this;
    return SignalToggleState(
      accesi: storia.last,
      storia: storia.sublist(0, storia.length - 1),
    );
  }

  /// Spegne tutto. Se c'e' qualcosa di acceso, entra nella storia (Annulla
  /// lo puo' disfare); se e' gia' tutto spento non cambia nulla.
  SignalToggleState tornaAlPercorsoIniziale() {
    if (accesi.isEmpty) return this;
    return SignalToggleState(accesi: const {}, storia: [...storia, accesi]);
  }
}

/// La richiesta da mandare al BFF per lo stato degli interruttori, partendo
/// SEMPRE dall'itinerario originale. Nessun interruttore acceso: `null`
/// (si mostra l'originale, nessuna richiesta di rete).
AdaptRequest? richiestaDiAdattamento({
  required Set<SimulatedSignalKind> accesi,
  required Itinerary originale,
  required EmotionalProfile? profilo,
  DateTime? now,
}) {
  if (accesi.isEmpty) return null;
  return AdaptRequest(
    itinerary: originale,
    signal: segnaleCombinato(accesi, now),
    profile: profilo,
  );
}

/// Vero se l'adattamento non tocca il percorso: tutte le tappe
/// `non_toccata`, stessi id nello stesso ordine dell'originale.
bool adattamentoSenzaEffetto({required Itinerary originale, required Itinerary adattato}) {
  final a = originale.stops;
  final b = adattato.stops;
  if (a.length != b.length) return false;
  for (var i = 0; i < b.length; i++) {
    if (b[i].esitoAdattamento != 'non_toccata') return false;
    if (a[i].experienceId != b[i].experienceId) return false;
  }
  return true;
}
