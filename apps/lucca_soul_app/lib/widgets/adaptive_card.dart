import 'package:flutter/material.dart';

import '../api/bff_client.dart';
import '../api/bff_exception.dart';
import '../models/adapt_request.dart';
import '../models/itinerary.dart';
import '../models/signal.dart';
import '../util/app_strings.dart';
import '../util/signal_presets.dart';

/// Card adattiva: tre bottoni di simulazione segnale (Wave 1) che chiamano
/// `POST /itinerary/adapt` e restituiscono al chiamante il nuovo
/// itinerario, già riscritto ("Piove → laboratorio al chiuso"; "Mura
/// affollate → Villa Bottini").
///
/// Non decide nulla: mostra il risultato di ciò che l'Experience Engine ha
/// deciso lato BFF, con il suo `reason` aggiornato.
class AdaptiveCard extends StatefulWidget {
  final BffClient bffClient;
  final Itinerary itinerary;
  final Signal signal;
  final AppStrings strings;

  /// Chiamato con il nuovo itinerario e il nuovo segnale dopo un adattamento
  /// riuscito, così lo schermo genitore può evidenziare le tappe cambiate.
  final void Function(Itinerary nuovoItinerario, Signal nuovoSegnale) onAdapted;

  const AdaptiveCard({
    super.key,
    required this.bffClient,
    required this.itinerary,
    required this.signal,
    required this.strings,
    required this.onAdapted,
  });

  @override
  State<AdaptiveCard> createState() => _AdaptiveCardState();
}

class _AdaptiveCardState extends State<AdaptiveCard> {
  SimulatedSignalKind? _inCorso;
  String? _errore;

  Future<void> _simula(SimulatedSignalKind kind) async {
    setState(() {
      _inCorso = kind;
      _errore = null;
    });
    try {
      final nuovoSegnale = buildSimulatedSignal(kind, widget.signal);
      final richiesta = AdaptRequest(itinerary: widget.itinerary, signal: nuovoSegnale);
      final nuovoItinerario = await widget.bffClient.adaptItinerary(richiesta);
      widget.onAdapted(nuovoItinerario, nuovoSegnale);
    } on BffException catch (error) {
      setState(() => _errore = error.message);
    } finally {
      if (mounted) setState(() => _inCorso = null);
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
                final inCorso = _inCorso == kind;
                return OutlinedButton.icon(
                  onPressed: _inCorso == null ? () => _simula(kind) : null,
                  icon: inCorso
                      ? const SizedBox(
                          height: 16,
                          width: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Icon(_iconaPer(kind)),
                  label: Text(_etichettaPer(kind)),
                );
              }).toList(),
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
