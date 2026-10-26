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

/// Fascia scura sotto l'AppBar: data, fascia oraria, numero di tappe, "a piedi".
class TestataGiornata extends StatelessWidget {
  final Itinerary itinerario;
  final DateTime data;
  final AppStrings strings;
  const TestataGiornata(
      {super.key,
      required this.itinerario,
      required this.data,
      required this.strings,});

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
          child: Text(riga, style: stileTesto(15, 600, Tk.testoSuTestata)),
        ),
      ),
    );
  }
}
