import '../models/meteo.dart';
import '../models/signal.dart';
import '../models/time_hms.dart';

/// Segnale di partenza per la generazione dell'itinerario: giornata serena,
/// nessun affollamento noto, stanchezza minima. È il punto zero da cui la
/// card adattiva della Wave 1 si scosta quando l'utente simula un evento.
Signal baselineSignal() => Signal(
      meteo: Meteo.sereno,
      affollamento: const {},
      stanchezza: 0.1,
      ora: TimeHms.now(),
    );

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
/// solo la dimensione simulata dal bottone premuto.
Signal buildSimulatedSignal(SimulatedSignalKind kind, Signal current) {
  switch (kind) {
    case SimulatedSignalKind.pioggia:
      return current.copyWith(meteo: Meteo.pioggia, ora: TimeHms.now());
    case SimulatedSignalKind.affollamento:
      return current.copyWith(
        affollamento: {for (final luogo in _luoghiTipicamenteAffollati) luogo: 0.95},
        ora: TimeHms.now(),
      );
    case SimulatedSignalKind.stanchezza:
      return current.copyWith(stanchezza: 0.85, ora: TimeHms.now());
  }
}
