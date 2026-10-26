import 'dart:math' show pow;

import 'package:flutter/material.dart';

/// Token grafici UNICI dell'app (direzione C). Nessun colore o misura della
/// grafica sta altrove: schermate e widget leggono da qui o dal tema.
class Tk {
  Tk._();

  // Superfici
  static const Color sfondo = Color(0xFFF6F2EA);
  static const Color cardSfondo = Color(0xFFFFFDF9);
  static const Color cardBordo = Color(0xFFE2DACB);
  static const Color avviso = Color(0xFFEFE1CF);
  static const Color testata = Color(0xFF1F2A2E);

  // Testo
  static const Color testo = Color(0xFF1F2A2E);
  static const Color testoSecondario = Color(0xFF4C585D);
  static const Color testoSuTestata = sfondo;
  static const Color testoSuAccento = Color(0xFFFFFFFF);

  // Accento mattone. MAI su testata scura (contrasto 2,48:1).
  static const Color accento = Color(0xFFA4482A);
  static const Color accentoPremuto = Color(0xFF7E351E);

  /// SOLO elementi non testuali (bordi, icone decorative, linee). Mai testo.
  static const Color grigioNonTestuale = Color(0xFF6B7A80);

  // Etichette dell'esito
  static const Color sostituitaSfondo = Color(0xFFF3DCCF);
  static const Color sostituitaTesto = Color(0xFF7E351E);
  static const Color mantenutaSfondo = Color(0xFFDCE7DF);
  static const Color mantenutaTesto = testo;

  // Misure
  static const double raggio = 12;
  static const double areaMinima = 44;
  static const double colonnaMax = 600;

  // Caratteri (famiglie incorporate in assets/fonts)
  static const String fontTitoli = 'Domine';
  static const String fontTesto = 'NunitoSans';
}

/// Coppia testo/sfondo realmente usata dal tema, con il rapporto minimo atteso.
class CoppiaColori {
  final String nome;
  final Color testo;
  final Color sfondo;
  const CoppiaColori(this.nome, this.testo, this.sfondo);
}

/// Tutte le coppie testo/sfondo del tema (verificate da test: >= 4,5).
const List<CoppiaColori> kCoppieTestoSfondo = [
  CoppiaColori('testo su sfondo', Tk.testo, Tk.sfondo),
  CoppiaColori('testo su card', Tk.testo, Tk.cardSfondo),
  CoppiaColori('secondario su sfondo', Tk.testoSecondario, Tk.sfondo),
  CoppiaColori('secondario su card', Tk.testoSecondario, Tk.cardSfondo),
  CoppiaColori('accento su sfondo', Tk.accento, Tk.sfondo),
  CoppiaColori('accento su card', Tk.accento, Tk.cardSfondo),
  CoppiaColori('bianco su accento', Tk.testoSuAccento, Tk.accento),
  CoppiaColori(
      'bianco su accento premuto', Tk.testoSuAccento, Tk.accentoPremuto,),
  CoppiaColori('accento su avviso', Tk.accento, Tk.avviso),
  CoppiaColori('testo su avviso', Tk.testo, Tk.avviso),
  CoppiaColori('sostituita', Tk.sostituitaTesto, Tk.sostituitaSfondo),
  CoppiaColori('resta in programma', Tk.mantenutaTesto, Tk.mantenutaSfondo),
  CoppiaColori('testata', Tk.testoSuTestata, Tk.testata),
];

/// Rapporto di contrasto WCAG 2.x tra due colori opachi.
double rapportoContrasto(Color a, Color b) {
  double lum(Color c) {
    double ch(double v) =>
        v <= 0.03928 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4).toDouble();
    return 0.2126 * ch(c.r) + 0.7152 * ch(c.g) + 0.0722 * ch(c.b);
  }

  final la = lum(a), lb = lum(b);
  final hi = la > lb ? la : lb, lo = la > lb ? lb : la;
  return (hi + 0.05) / (lo + 0.05);
}
