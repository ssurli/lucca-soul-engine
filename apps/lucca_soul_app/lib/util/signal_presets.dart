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

extension SimulatedSignalKindLabel on SimulatedSignalKind {
  String get label {
    switch (this) {
      case SimulatedSignalKind.pioggia:
        return 'Sta piovendo';
      case SimulatedSignalKind.affollamento:
        return 'Mura affollate';
      case SimulatedSignalKind.stanchezza:
        return 'Sono stanco/a';
    }
  }
}

/// Luoghi noti del seed di Lucca (`services/graph/cypher/01_seed_lucca.cypher`)
/// usati per rendere plausibile il segnale di affollamento simulato.
const List<String> _luoghiTipicamenteAffollati = ['mura-urbane', 'piazza-anfiteatro'];

/// Costruisce il nuovo `Signal` a partire da quello corrente, alterando
/// solo la dimensione simulata dal bottone premuto. `now` solo nei test.
Signal buildSimulatedSignal(SimulatedSignalKind kind, Signal current, [DateTime? now]) {
  final t = Signal.orologio(now); // una sola lettura per ora e data
  switch (kind) {
    case SimulatedSignalKind.pioggia:
      return current.copyWith(meteo: Meteo.pioggia, ora: t.ora, data: t.data, istante: t.istante);
    case SimulatedSignalKind.affollamento:
      return current.copyWith(
        affollamento: {for (final luogo in _luoghiTipicamenteAffollati) luogo: 0.95},
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
