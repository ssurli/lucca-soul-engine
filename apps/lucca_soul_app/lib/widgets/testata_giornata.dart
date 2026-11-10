import 'package:flutter/material.dart';

import '../models/itinerary.dart';
import '../theme/app_theme.dart';
import '../theme/tokens.dart';
import '../util/app_strings.dart';
import '../util/riepilogo_cambio.dart';
import 'colonna_centrata.dart';
import 'mura_logo.dart';

/// Titolo dell'AppBar: logo delle Mura + nome prodotto. Tutto in #F6F2EA
/// sulla testata scura (mai il mattone: contrasto 2,48:1).
class TitoloMarchio extends StatelessWidget {
  const TitoloMarchio({super.key});

  @override
  Widget build(BuildContext context) {
    return const Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        MuraLogo(size: 32),
        SizedBox(width: 10),
        Flexible(child: Text('Lucca Soul', overflow: TextOverflow.ellipsis)),
      ],
    );
  }
}

/// Etichetta "Demo" (build con `--dart-define=DEMO=true`): bordo e testo
/// #F6F2EA sulla testata scura. Sta a destra del nome, sulla riga dell'AppBar.
class EtichettaDemo extends StatelessWidget {
  final AppStrings strings;
  const EtichettaDemo({super.key, required this.strings});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 1, horizontal: 6),
      decoration: BoxDecoration(
        border: Border.all(color: Tk.testoSuTestata, width: Tk.bordoEtichetta),
        borderRadius: BorderRadius.circular(Tk.raggioEtichetta),
      ),
      child: Text(
        strings.demoLabel.toUpperCase(),
        semanticsLabel: strings.demoLabel,
        style: stileTesto(12, 800, Tk.testoSuTestata).copyWith(letterSpacing: 0.6),
      ),
    );
  }
}

/// Fascia scura sotto l'AppBar: data, fascia oraria, numero di tappe, "a piedi".
class TestataGiornata extends StatelessWidget {
  final Itinerary itinerario;
  final DateTime data;
  final AppStrings strings;
  /// Mostra l'etichetta "Demo" (build con `--dart-define=DEMO=true`).
  final bool demo;
  const TestataGiornata(
      {super.key,
      required this.itinerario,
      required this.data,
      required this.strings,
      this.demo = false,});

  @override
  Widget build(BuildContext context) {
    final fascia = fasciaOrariaGiornata(itinerario.stops);
    final riga = [
      strings.shortDate(data),
      if (fascia != null) fascia,
      strings.stopsCount(itinerario.stops.length),
      strings.onFoot,
    ].join(' · ');
    return Container(
      width: double.infinity,
      color: Tk.testata,
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
      child: ColonnaCentrata(
        child: Align(
          alignment: Alignment.centerLeft,
          child: Wrap(
            spacing: 10,
            runSpacing: 6,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(riga, style: stileTesto(15, 600, Tk.testoSuTestata)),
              if (demo) EtichettaDemo(strings: strings),
            ],
          ),
        ),
      ),
    );
  }
}
