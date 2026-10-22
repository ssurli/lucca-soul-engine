import 'package:flutter/material.dart';

import '../api/bff_client.dart';
import '../api/bff_exception.dart';
import '../models/emotional_profile.dart';
import '../models/itinerary.dart';
import '../util/app_strings.dart';
import '../util/signal_presets.dart';
import '../util/signal_toggles.dart';

/// Card adattiva: tre interruttori di simulazione segnale (pioggia,
/// affollamento, stanchezza). A ogni cambio parte dall'itinerario ORIGINALE
/// e manda UNA sola richiesta `POST /itinerary/adapt` con il segnale
/// combinato di tutti gli interruttori accesi. Se arrivano risposte fuori
/// ordine conta solo quella dell'ultimo stato richiesto.
///
/// Non decide nulla: mostra il risultato di ciò che l'Experience Engine ha
/// deciso lato BFF, con il suo `reason` aggiornato.
class AdaptiveCard extends StatefulWidget {
  final BffClient bffClient;

  /// Itinerario di `POST /itinerary`, mai modificato: base di ogni adattamento.
  final Itinerary original;
  final EmotionalProfile profile;
  final AppStrings strings;

  /// Chiamato con l'itinerario da mostrare (l'originale o l'ultimo
  /// adattamento valido).
  final void Function(Itinerary mostrato) onShown;

  const AdaptiveCard({
    super.key,
    required this.bffClient,
    required this.original,
    required this.profile,
    required this.strings,
    required this.onShown,
  });

  @override
  State<AdaptiveCard> createState() => _AdaptiveCardState();
}

class _AdaptiveCardState extends State<AdaptiveCard> {
  SignalToggleState _stato = const SignalToggleState();

  /// Stato di cui l'itinerario mostrato e' il risultato (per il ripristino
  /// se l'ultima richiesta fallisce).
  SignalToggleState _statoMostrato = const SignalToggleState();
  int _sequenza = 0;
  bool _inCorso = false;
  bool _senzaEffetto = false;
  String? _errore;

  void _applica(SignalToggleState nuovo) {
    setState(() {
      _stato = nuovo;
      _errore = null;
    });
    _richiedi(nuovo);
  }

  Future<void> _richiedi(SignalToggleState stato) async {
    final mia = ++_sequenza;
    final richiesta = richiestaDiAdattamento(
      accesi: stato.accesi,
      originale: widget.original,
      profilo: widget.profile,
    );
    if (richiesta == null) {
      setState(() {
        _inCorso = false;
        _senzaEffetto = false;
        _statoMostrato = stato;
      });
      widget.onShown(widget.original);
      return;
    }
    setState(() => _inCorso = true);
    try {
      final adattato = await widget.bffClient.adaptItinerary(richiesta);
      if (!mounted || mia != _sequenza) return; // risposta superata
      setState(() {
        _inCorso = false;
        _statoMostrato = stato;
        _senzaEffetto = adattamentoSenzaEffetto(originale: widget.original, adattato: adattato);
      });
      widget.onShown(adattato);
    } on BffException catch (error) {
      if (!mounted || mia != _sequenza) return;
      setState(() {
        _inCorso = false;
        _errore = error.message;
        _stato = _statoMostrato; // l'interruttore torna a rispecchiare ciò che si vede
      });
    }
  }

  IconData _iconaPer(SimulatedSignalKind kind) {
    switch (kind) {
      case SimulatedSignalKind.pioggia:
        return Icons.umbrella_outlined;
      case SimulatedSignalKind.affollamento:
        return Icons.groups_outlined;
      case SimulatedSignalKind.stanchezza:
        return Icons.battery_alert_outlined;
    }
  }

  String _etichettaPer(SimulatedSignalKind kind) {
    switch (kind) {
      case SimulatedSignalKind.pioggia:
        return widget.strings.signalRain;
      case SimulatedSignalKind.affollamento:
        return widget.strings.signalCrowd;
      case SimulatedSignalKind.stanchezza:
        return widget.strings.signalTired;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.strings.adaptiveCardTitle, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: SimulatedSignalKind.values.map((kind) {
                return FilterChip(
                  selected: _stato.accesi.contains(kind),
                  avatar: Icon(_iconaPer(kind)),
                  label: Text(_etichettaPer(kind)),
                  onSelected: (_) => _applica(_stato.premi(kind)),
                );
              }).toList(),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                TextButton(
                  onPressed: _stato.puoAnnullare ? () => _applica(_stato.annulla()) : null,
                  child: Text(widget.strings.undoAction),
                ),
                TextButton(
                  onPressed: _stato.nessunoAcceso ? null : () => _applica(_stato.tornaAlPercorsoIniziale()),
                  child: Text(widget.strings.resetAction),
                ),
                if (_inCorso) const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2)),
              ],
            ),
            if (_senzaEffetto && !_inCorso)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(widget.strings.noEffectNote),
              ),
            if (_errore != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(_errore!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ),
          ],
        ),
      ),
    );
  }
}
