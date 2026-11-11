import 'package:flutter/material.dart';

import '../util/app_strings.dart';
import '../util/interruttori_controller.dart';
import '../util/signal_presets.dart';
import '../theme/app_theme.dart';
import '../theme/tokens.dart';
import '../util/riepilogo_cambio.dart';

/// Card adattiva: tre interruttori di simulazione segnale (pioggia,
/// affollamento, stanchezza). E' una VISTA: lo stato (interruttori, itinerario
/// mostrato, richieste in volo) vive nell'[InterruttoriController] di
/// `ItineraryScreen`, cosi' smontarla dal `ListView` non lo perde. Inoltra le
/// pressioni al controller, che a ogni cambio parte dall'itinerario ORIGINALE.
///
/// Non decide nulla: mostra il risultato di ciò che l'Experience Engine ha
/// deciso lato BFF, con il suo `reason` aggiornato.
class AdaptiveCard extends StatelessWidget {
  final InterruttoriController controller;
  final AppStrings strings;

  const AdaptiveCard({
    super.key,
    required this.controller,
    required this.strings,
  });

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
        return strings.signalRain;
      case SimulatedSignalKind.affollamento:
        return strings.signalCrowd;
      case SimulatedSignalKind.stanchezza:
        return strings.signalTired;
    }
  }

  /// Riepilogo del cambio mostrato, dagli esiti dell'itinerario adattato.
  String _riepilogo() {
    final mostrato = controller.adattamentoMostrato;
    if (mostrato == null) return strings.backToOriginalSummary;
    return riepilogoCambio(
      segnali: [
        for (final k in SimulatedSignalKind.values)
          if (controller.statoMostrato.accesi.contains(k)) _etichettaPer(k),
      ],
      adattato: mostrato,
      originale: controller.originale,
      strings: strings,
    );
  }

  String? _secondaRiga() {
    final k = controller.segnaleSenzaAltroCambiamento;
    return k == null ? null : strings.noFurtherChange(_etichettaPer(k));
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: controller,
        builder: _costruisci,
      );

  Widget _costruisci(BuildContext context, Widget? _) {
    final theme = Theme.of(context);
    final stato = controller.stato;
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(strings.adaptiveCardTitle,
                      style: stileTesto(13, 700, Tk.testoSecondario),),
                ),
                // Nulla da ripristinare (nessun interruttore acceso): nessun comando.
                if (!stato.nessunoAcceso)
                  TextButton(
                    onPressed: controller.tornaAlPercorsoIniziale,
                    style: TextButton.styleFrom(
                      minimumSize: const Size(Tk.areaMinima, Tk.areaMinima),
                      foregroundColor: Tk.accento,
                      textStyle: stileTesto(14, 800, Tk.accento),
                    ),
                    child: Text(strings.resetShortAction),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 8,
              children: SimulatedSignalKind.values.map((kind) {
                return InterruttoreSegnale(
                  acceso: stato.accesi.contains(kind),
                  icona: _iconaPer(kind),
                  etichetta: _etichettaPer(kind),
                  onPressed: () => controller.premi(kind),
                );
              }).toList(),
            ),
            if (stato.puoAnnullare || !stato.nessunoAcceso)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: FasciaRiepilogo(
                  testo: _riepilogo(),
                  secondaRiga: _secondaRiga(),
                ),
              ),
            if (controller.inCorso)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: SizedBox(
                    height: 16,
                    width: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),),
              ),
            if (controller.errore != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(controller.errore!,
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
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(acceso ? Icons.check : icona, size: 16, color: fg),
                  const SizedBox(width: 4),
                  Flexible(
                      child: Text(etichetta, style: stileTesto(14, 700, fg)),),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Fascia di riepilogo (sfondo avviso): il testo usa tutta la larghezza. Il
/// comando "Percorso iniziale" sta sulla riga del titolo della card.
class FasciaRiepilogo extends StatelessWidget {
  final String testo;
  final String? secondaRiga;

  const FasciaRiepilogo({super.key, required this.testo, this.secondaRiga});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      decoration: BoxDecoration(
          color: Tk.avviso, borderRadius: BorderRadius.circular(Tk.raggio),),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(testo, style: stileTesto(14, 600, Tk.testo)),
          if (secondaRiga != null)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(secondaRiga!, style: stileTesto(14, 600, Tk.testo)),
            ),
        ],
      ),
    );
  }
}
