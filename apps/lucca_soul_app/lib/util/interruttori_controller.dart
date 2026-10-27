import 'package:flutter/foundation.dart';

import '../api/bff_client.dart';
import '../api/bff_exception.dart';
import '../models/emotional_profile.dart';
import '../models/itinerary.dart';
import 'signal_presets.dart';
import 'signal_toggles.dart';

/// Unico proprietario dello stato degli interruttori dei segnali e
/// dell'itinerario mostrato. Lo crea e lo conserva `ItineraryScreen`; la card
/// adattiva e la lista delle tappe sono viste che lo leggono, quindi uscire
/// dalla cache del `ListView` non puo' separare interruttori e tappe.
///
/// A ogni pressione parte dall'itinerario ORIGINALE (mai modificato) e manda
/// UNA sola richiesta `POST /itinerary/adapt` con il segnale combinato degli
/// interruttori accesi. Se arrivano risposte fuori ordine conta solo quella
/// dell'ultimo stato richiesto. Non decide nulla: l'adattamento e' dell'Experience
/// Engine, lato BFF.
class InterruttoriController extends ChangeNotifier {
  final BffClient bffClient;

  /// Itinerario di `POST /itinerary`, base di ogni adattamento.
  final Itinerary originale;
  final EmotionalProfile profilo;

  InterruttoriController({
    required this.bffClient,
    required this.originale,
    required this.profilo,
  });

  SignalToggleState _stato = const SignalToggleState();

  /// Stato di cui l'itinerario mostrato e' il risultato (per il ripristino
  /// se l'ultima richiesta fallisce).
  SignalToggleState _statoMostrato = const SignalToggleState();

  /// Risultato attualmente mostrato (null = l'originale): base del confronto
  /// per la nota "nessun effetto".
  Itinerary? _mostrato;
  int _sequenza = 0;
  bool _inCorso = false;
  bool _senzaEffetto = false;
  String? _errore;
  bool _disposto = false;

  SignalToggleState get stato => _stato;
  SignalToggleState get statoMostrato => _statoMostrato;

  /// L'itinerario da mostrare: l'originale o l'ultimo adattamento valido.
  Itinerary get itinerarioMostrato => _mostrato ?? originale;

  /// Null = si sta mostrando l'originale.
  Itinerary? get adattamentoMostrato => _mostrato;
  bool get inCorso => _inCorso;
  bool get senzaEffetto => _senzaEffetto;
  String? get errore => _errore;

  void premi(SimulatedSignalKind kind) => _applica(_stato.premi(kind));
  void annulla() => _applica(_stato.annulla());
  void tornaAlPercorsoIniziale() => _applica(_stato.tornaAlPercorsoIniziale());

  void _applica(SignalToggleState nuovo) {
    _stato = nuovo;
    _errore = null;
    notifyListeners();
    _richiedi(nuovo);
  }

  Future<void> _richiedi(SignalToggleState stato) async {
    final mia = ++_sequenza;
    final richiesta = richiestaDiAdattamento(
      accesi: stato.accesi,
      originale: originale,
      profilo: profilo,
    );
    if (richiesta == null) {
      _inCorso = false;
      _senzaEffetto = false;
      _statoMostrato = stato;
      _mostrato = null;
      notifyListeners();
      return;
    }
    _inCorso = true;
    notifyListeners();
    try {
      final adattato = await bffClient.adaptItinerary(richiesta);
      if (_disposto || mia != _sequenza) return; // risposta superata
      _inCorso = false;
      _statoMostrato = stato;
      _senzaEffetto = risultatoSenzaEffetto(
        precedente: _mostrato ?? originale,
        nuovo: adattato,
      );
      _mostrato = adattato;
      notifyListeners();
    } on BffException catch (error) {
      if (_disposto || mia != _sequenza) return;
      _inCorso = false;
      _errore = error.message;
      _stato = _statoMostrato; // l'interruttore torna a rispecchiare ciò che si vede
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _disposto = true; // le risposte in volo non toccano piu' lo stato
    super.dispose();
  }
}
