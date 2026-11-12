import '../models/meteo.dart';
import '../models/signal.dart';

/// Segnale di partenza per la generazione dell'itinerario: giornata serena,
/// nessun affollamento noto, stanchezza a zero. È il punto zero da cui la
/// card adattiva della Wave 1 si scosta quando l'utente simula un evento.
Signal baselineSignal([DateTime? now]) {
  final t = Signal.orologio(now); // una sola lettura: ora e data coerenti
  return Signal(
    meteo: Meteo.sereno,
    affollamento: const {},
    stanchezza: 0.0,
    ora: t.ora,
    data: t.data,
    istante: t.istante,
  );
}

/// I tre segnali che la card adattiva della Wave 1 permette di simulare
/// (vedi `docs/BUILD_PLAN.md` Wave 1: "pioggia, affollamento, stanchezza").
/// In produzione questi segnali arriverebbero dalla Data Layer reale; qui
/// sono innescati da tre bottoni per dimostrare la riscrittura.
enum SimulatedSignalKind { pioggia, affollamento, stanchezza }

// Le etichette dei segnali vivono SOLO in `AppStrings` (signalRain,
// signalCrowd, signalTired): nessuna copia qui.

/// Elenco simulato, scritto a mano (in produzione arriverebbe dal Data Layer).
/// Luoghi noti del seed (`services/graph/cypher/01_seed_lucca.cypher`).
const List<String> kLuoghiAffollatiSimulati = ['via-fillungo', 'san-michele-in-foro'];

/// Valore di affollamento simulato per ogni luogo dell'elenco. Sta tra la
/// soglia di adattamento del motore (rules.SOGLIA_AFFOLLAMENTO_ADATTAMENTO =
/// 0.7: sopra, le tappe all'aperto vengono riscritte) e la soglia critica
/// (rules.SOGLIA_AFFOLLAMENTO_CRITICO = 0.8: da li' il filtro duro esclude
/// tutto il luogo, anche gli interni, che quindi non potrebbero fare da
/// sostituto). Verificato da tests/test_valore_folla_app.py.
const double kValoreAffollamentoSimulato = 0.75;

/// Costruisce il nuovo `Signal` a partire da quello corrente, alterando
/// solo la dimensione simulata dal bottone premuto. `now` solo nei test.
Signal buildSimulatedSignal(SimulatedSignalKind kind, Signal current, [DateTime? now]) {
  final t = Signal.orologio(now); // una sola lettura per ora e data
  switch (kind) {
    case SimulatedSignalKind.pioggia:
      return current.copyWith(meteo: Meteo.pioggia, ora: t.ora, data: t.data, istante: t.istante);
    case SimulatedSignalKind.affollamento:
      return current.copyWith(
        affollamento: {for (final luogo in kLuoghiAffollatiSimulati) luogo: kValoreAffollamentoSimulato},
        ora: t.ora, data: t.data, istante: t.istante,
      );
    case SimulatedSignalKind.stanchezza:
      return current.copyWith(stanchezza: 0.85, ora: t.ora, data: t.data, istante: t.istante);
  }
}

/// Segnale COMBINATO di tutti gli interruttori accesi, sempre a partire da
/// [baselineSignal]: ogni interruttore acceso applica la propria dimensione.
/// Ora, data e istante vengono da UNA sola lettura dell'orologio.
Signal segnaleCombinato(Set<SimulatedSignalKind> accesi, [DateTime? now]) {
  final t = Signal.orologio(now);
  var segnale = baselineSignal(t.istante);
  for (final kind in SimulatedSignalKind.values) {
    if (accesi.contains(kind)) segnale = buildSimulatedSignal(kind, segnale, t.istante);
  }
  return segnale;
}
