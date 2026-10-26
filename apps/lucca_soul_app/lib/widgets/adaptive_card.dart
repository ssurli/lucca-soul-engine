import 'package:flutter/material.dart';

import '../api/bff_client.dart';
import '../api/bff_exception.dart';
import '../models/emotional_profile.dart';
import '../models/itinerary.dart';
import '../util/app_strings.dart';
import '../util/signal_presets.dart';
import '../theme/app_theme.dart';
import '../theme/tokens.dart';
import '../util/riepilogo_cambio.dart';
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

  /// Risultato attualmente mostrato (null = l'originale): base del confronto
  /// per la nota "nessun effetto".
  Itinerary? _mostrato;
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
        _mostrato = null;
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
        _senzaEffetto = risultatoSenzaEffetto(
          precedente: _mostrato ?? widget.original,
          nuovo: adattato,
        );
        _mostrato = adattato;
      });
      widget.onShown(adattato);
    } on BffException catch (error) {
      if (!mounted || mia != _sequenza) return;
      setState(() {
        _inCorso = false;
        _errore = error.message;
        _stato =
            _statoMostrato; // l'interruttore torna a rispecchiare ciò che si vede
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

  /// Riepilogo del cambio mostrato, dagli esiti dell'itinerario adattato.
  String _riepilogo() {
    final mostrato = _mostrato;
    if (mostrato == null) return widget.strings.backToOriginalSummary;
    return riepilogoCambio(
      segnali: [
        for (final k in SimulatedSignalKind.values)
          if (_statoMostrato.accesi.contains(k)) _etichettaPer(k),
      ],
      adattato: mostrato,
      originale: widget.original,
      strings: widget.strings,
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.strings.adaptiveCardTitle,
                style: theme.textTheme.titleMedium,),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: SimulatedSignalKind.values.map((kind) {
                return InterruttoreSegnale(
                  acceso: _stato.accesi.contains(kind),
                  icona: _iconaPer(kind),
                  etichetta: _etichettaPer(kind),
                  onPressed: () => _applica(_stato.premi(kind)),
                );
              }).toList(),
            ),
            if (_stato.puoAnnullare)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: FasciaRiepilogo(
                  testo: _riepilogo(),
                  azione: widget.strings.undoAction,
                  onAzione: () => _applica(_stato.annulla()),
                ),
              ),
            const SizedBox(height: 4),
            Wrap(
              spacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                TextButton(
                  onPressed: _stato.nessunoAcceso
                      ? null
                      : () => _applica(_stato.tornaAlPercorsoIniziale()),
                  child: Text(widget.strings.resetAction),
                ),
                if (_inCorso)
                  const SizedBox(
                      height: 16,
                      width: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),),
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
                child: Text(_errore!,
                    style: TextStyle(color: theme.colorScheme.error),),
              ),
          ],
        ),
      ),
    );
  }
}

/// Interruttore di un segnale: spento = card con bordo; acceso = mattone,
/// testo bianco e segno di spunta. Area minima 44 px.
class InterruttoreSegnale extends StatelessWidget {
  final bool acceso;
  final IconData icona;
  final String etichetta;
  final VoidCallback onPressed;

  const InterruttoreSegnale({
    super.key,
    required this.acceso,
    required this.icona,
    required this.etichetta,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final fg = acceso ? Tk.testoSuAccento : Tk.testo;
    return Semantics(
      button: true,
      toggled: acceso,
      label: etichetta,
      excludeSemantics: true,
      onTap: onPressed,
      child: Material(
        color: acceso ? Tk.accento : Tk.cardSfondo,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Tk.raggio),
          side: BorderSide(color: acceso ? Tk.accento : Tk.grigioNonTestuale),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onPressed,
          overlayColor: WidgetStateProperty.resolveWith((s) {
            if (s.contains(WidgetState.pressed) ||
                s.contains(WidgetState.hovered)) {
              return acceso ? Tk.accentoPremuto : Tk.avviso;
            }
            return null;
          }),
          child: ConstrainedBox(
            constraints: const BoxConstraints(
                minHeight: Tk.areaMinima, minWidth: Tk.areaMinima,),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(acceso ? Icons.check : icona, size: 18, color: fg),
                  const SizedBox(width: 8),
                  Flexible(
                      child: Text(etichetta, style: stileTesto(15, 700, fg)),),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Fascia di riepilogo (sfondo avviso) con l'azione a destra: "Annulla" in
/// mattone su #EFE1CF.
class FasciaRiepilogo extends StatelessWidget {
  final String testo;
  final String azione;
  final VoidCallback onAzione;

  const FasciaRiepilogo(
      {super.key,
      required this.testo,
      required this.azione,
      required this.onAzione,});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.only(left: 14, right: 4),
      decoration: BoxDecoration(
          color: Tk.avviso, borderRadius: BorderRadius.circular(Tk.raggio),),
      child: Row(
        children: [
          Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(testo, style: stileTesto(15, 600, Tk.testo)),
            ),
          ),
          TextButton(onPressed: onAzione, child: Text(azione)),
        ],
      ),
    );
  }
}
