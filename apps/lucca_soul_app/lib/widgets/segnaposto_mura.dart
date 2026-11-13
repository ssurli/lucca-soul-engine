import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;

import '../theme/app_theme.dart';
import '../theme/tokens.dart';

/// Larghezza DISEGNATA del segnaposto (px di schermo). L'altezza segue la
/// viewBox. L'area del tocco è un riquadro di almeno [Tk.areaMinima] per lato,
/// centrato sulla sagoma ([SagomaSegnaposto.dimensioneRiquadro]).
const double kLarghezzaSegnaposto = 40;

/// Larghezza (px) della sagoma senza punta usata come numero nelle card della
/// lista delle tappe. L'altezza segue la sua viewBox.
const double kLarghezzaNumeroCard = 32;

/// Altezza delle cifre in proporzione al corpo del carattere (Nunito Sans): serve
/// a misurare il rettangolo del numero ([SagomaSegnaposto.rettangoloNumero]).
const double kAltezzaCifre = 0.72;

/// Fattore di riduzione del carattere con due cifre.
const double kRiduzioneDueCifre = 0.85;

/// Geometria della sagoma, in unità della sua viewBox (y verso il basso).
class SagomaSegnaposto {
  final Rect viewBox;
  final List<Offset> contorno; // chiuso, comprende la punta
  final List<Offset> traccia; // linea interna (il tracciato delle mura)
  final Offset punta; // il luogo esatto: ancoraggio del segnaposto
  final Offset centroNumero;
  final double dimensioneNumero; // in unità della viewBox

  /// Versione senza punta per la lista delle tappe; null se l'asset non la
  /// contiene (la card ripiega sul cerchio). Vedi [senzaPuntaDaJson].
  final SagomaSegnaposto? senzaPunta;

  const SagomaSegnaposto({
    required this.viewBox,
    required this.contorno,
    required this.traccia,
    required this.punta,
    required this.centroNumero,
    required this.dimensioneNumero,
    this.senzaPunta,
  });

  factory SagomaSegnaposto.fromJson(Map<String, dynamic> j) {
    Offset o(List<dynamic> p) =>
        Offset((p[0] as num).toDouble(), (p[1] as num).toDouble());
    List<Offset> lista(String k) =>
        [for (final p in j[k] as List<dynamic>) o(p as List<dynamic>)];
    final vb = j['viewBox'] as Map<String, dynamic>;
    return SagomaSegnaposto(
      viewBox: Rect.fromLTWH(
        (vb['x'] as num).toDouble(),
        (vb['y'] as num).toDouble(),
        (vb['larghezza'] as num).toDouble(),
        (vb['altezza'] as num).toDouble(),
      ),
      contorno: lista('contorno'),
      traccia: lista('traccia'),
      punta: o(j['punta'] as List<dynamic>),
      centroNumero: o(j['centroNumero'] as List<dynamic>),
      dimensioneNumero: (j['dimensioneNumero'] as num).toDouble(),
      senzaPunta: senzaPuntaDaJson(j),
    );
  }

  /// Versione senza punta (il baluardo sud allungato sostituito da uno tozzo),
  /// per il numero nella lista delle tappe. Legge `contornoSenzaPunta`,
  /// `viewBoxSenzaPunta`, `centroNumeroSenzaPunta`, `dimensioneNumeroSenzaPunta`;
  /// se manca anche uno solo (o sono malformati) restituisce null e la card
  /// ripiega sul cerchio. Senza traccia; la punta e' il centro in basso (non usata).
  static SagomaSegnaposto? senzaPuntaDaJson(Map<String, dynamic> j) {
    try {
      Offset o(List<dynamic> p) =>
          Offset((p[0] as num).toDouble(), (p[1] as num).toDouble());
      final vb = j['viewBoxSenzaPunta'] as Map<String, dynamic>;
      final r = Rect.fromLTWH(
        (vb['x'] as num).toDouble(),
        (vb['y'] as num).toDouble(),
        (vb['larghezza'] as num).toDouble(),
        (vb['altezza'] as num).toDouble(),
      );
      final contorno = [
        for (final p in j['contornoSenzaPunta'] as List<dynamic>)
          o(p as List<dynamic>),
      ];
      if (contorno.length < 3) return null;
      return SagomaSegnaposto(
        viewBox: r,
        contorno: contorno,
        traccia: const [],
        punta: Offset(r.center.dx, r.bottom),
        centroNumero: o(j['centroNumeroSenzaPunta'] as List<dynamic>),
        dimensioneNumero: (j['dimensioneNumeroSenzaPunta'] as num).toDouble(),
      );
    } catch (_) {
      return null;
    }
  }

  double scala(double larghezza) => larghezza / viewBox.width;

  /// Dimensione del carattere (px) per [numero] a una data larghezza.
  double dimensioneCarattere(double larghezza, int numero) =>
      dimensioneNumero * scala(larghezza) * (numero >= 10 ? kRiduzioneDueCifre : 1);

  /// Rettangolo occupato dalle cifre di [numero] (px, nel riquadro della
  /// sagoma disegnata): larghezza misurata dal testo, altezza = altezza delle
  /// cifre ([kAltezzaCifre]), centrato su `centroNumero`. I test lo confrontano
  /// con il contorno.
  Rect rettangoloNumero(double larghezza, int numero) {
    final dim = dimensioneCarattere(larghezza, numero);
    final tp = TextPainter(
      text: TextSpan(text: '$numero', style: stileTesto(dim, 800, Tk.testoSuAccento)),
      textDirection: TextDirection.ltr,
    )..layout();
    final c = (centroNumero - viewBox.topLeft) * scala(larghezza);
    return Rect.fromCenter(
        center: c, width: tp.width, height: dim * kAltezzaCifre,);
  }

  /// Dimensione del widget a una data larghezza.
  Size dimensione(double larghezza) =>
      Size(larghezza, viewBox.height * scala(larghezza));

  /// Riquadro di tocco: almeno [Tk.areaMinima] per lato, sagoma al centro.
  Size dimensioneRiquadro(double larghezza) {
    final d = dimensione(larghezza);
    return Size(math.max(Tk.areaMinima, d.width),
        math.max(Tk.areaMinima, d.height),);
  }

  /// Padding simmetrico tra il riquadro di tocco e la sagoma disegnata.
  Offset paddingTocco(double larghezza) {
    final d = dimensione(larghezza);
    final r = dimensioneRiquadro(larghezza);
    return Offset((r.width - d.width) / 2, (r.height - d.height) / 2);
  }

  /// Posizione della punta dentro il RIQUADRO di tocco (padding + punta del
  /// disegno): è il punto del widget che deve cadere sul luogo.
  Offset puntaNelRiquadro(double larghezza) =>
      paddingTocco(larghezza) + puntaLocale(larghezza);

  /// Spazio che l'inquadratura deve lasciare attorno al punto perché l'intero
  /// riquadro di tocco (con la punta sul punto) resti dentro la mappa,
  /// più [margine] px per lato.
  EdgeInsets margini(double larghezza, double margine) {
    final d = dimensioneRiquadro(larghezza);
    final t = puntaNelRiquadro(larghezza);
    return EdgeInsets.fromLTRB(t.dx + margine, t.dy + margine,
        d.width - t.dx + margine, d.height - t.dy + margine,);
  }

  /// Posizione della punta dentro la sagoma DISEGNATA (px).
  Offset puntaLocale(double larghezza) =>
      (punta - viewBox.topLeft) * scala(larghezza);
}

/// Disegna la sagoma piena (accento), bordo chiaro, traccia interna e numero.
class SagomaPainter extends CustomPainter {
  final SagomaSegnaposto sagoma;
  final int numero;

  /// Ombra sotto la sagoma: sulla mappa si', nella lista delle tappe no.
  final bool conOmbra;
  SagomaPainter(this.sagoma, this.numero, {this.conOmbra = true});

  Path _percorso(List<Offset> punti, double s, {bool chiuso = true}) {
    final p = Path();
    for (var i = 0; i < punti.length; i++) {
      final q = (punti[i] - sagoma.viewBox.topLeft) * s;
      i == 0 ? p.moveTo(q.dx, q.dy) : p.lineTo(q.dx, q.dy);
    }
    if (chiuso) p.close();
    return p;
  }

  @override
  void paint(Canvas canvas, Size size) {
    final s = sagoma.scala(size.width);
    final corpo = _percorso(sagoma.contorno, s);
    if (conOmbra) canvas.drawShadow(corpo, Colors.black, 2, false);
    canvas.drawPath(corpo, Paint()..color = Tk.accento);
    canvas.drawPath(
      corpo,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeJoin = StrokeJoin.round
        ..strokeWidth = 1.4 * s
        ..color = Tk.cardSfondo,
    );
    if (sagoma.traccia.isNotEmpty) {
      canvas.drawPath(
        _percorso(sagoma.traccia, s),
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeJoin = StrokeJoin.round
          ..strokeWidth = 0.9 * s
          ..color = Tk.cardSfondo.withValues(alpha: 0.75),
      );
    }
    // Due cifre: carattere un po' più piccolo per restare dentro la traccia.
    final dim = sagoma.dimensioneCarattere(size.width, numero);
    final tp = TextPainter(
      text: TextSpan(
          text: '$numero', style: stileTesto(dim, 800, Tk.testoSuAccento),),
      textDirection: TextDirection.ltr,
    )..layout();
    final c = (sagoma.centroNumero - sagoma.viewBox.topLeft) * s;
    tp.paint(canvas, c - Offset(tp.width / 2, tp.height / 2));
  }

  @override
  bool shouldRepaint(SagomaPainter old) =>
      old.numero != numero || old.sagoma != sagoma || old.conOmbra != conOmbra;
}

/// Spessore della linea di richiamo (px): sottile, diverso dai 3 px della
/// linea dell'ordine.
const double kSpessoreRichiamo = 1;

/// Raggio del pallino sul luogo vero (px).
const double kRaggioPallinoRichiamo = 2.5;

/// Colore della linea e del pallino di richiamo: grigio non testuale, mai il
/// nero né l'accento (che e' della linea dell'ordine).
const Color kColoreRichiamo = Tk.grigioNonTestuale;

/// Linee di richiamo: quando un segnaposto è stato scostato
/// ([separaSegnaposti]), una linea continua e sottile va dalla sua punta al
/// luogo vero, segnato da un pallino. Si distingue dalla linea dell'ordine
/// (tratteggiata, accento, 3 px) per colore, spessore e tratto. Nessun alone:
/// il grigio da solo e' leggibile sullo sfondo della mappa. Va disegnato SOTTO
/// i segnaposti.
class GuidePainter extends CustomPainter {
  final List<Offset> veri; // punti veri sullo schermo
  final List<Offset> punte; // punte dopo la separazione
  GuidePainter(this.veri, this.punte);

  @override
  void paint(Canvas canvas, Size size) {
    final linea = Paint()
      ..color = kColoreRichiamo
      ..strokeWidth = kSpessoreRichiamo;
    for (var i = 0; i < veri.length; i++) {
      if ((punte[i] - veri[i]).distance < 2) continue;
      canvas.drawLine(punte[i], veri[i], linea);
      canvas.drawCircle(
          veri[i], kRaggioPallinoRichiamo, Paint()..color = kColoreRichiamo,);
    }
  }

  @override
  bool shouldRepaint(GuidePainter old) => true;
}

/// Diametro di collisione per [separaSegnaposti] con la sagoma: la larghezza
/// DISEGNATA (non il riquadro di tocco: i riquadri di due segnaposti separati
/// possono sovrapporsi di qualche px nel padding trasparente).
double diametroCollisione(double larghezza) => larghezza;

/// Legge la sagoma da `assets/brand/segnaposto_sagoma.json`. Nessuna
/// coordinata nel codice: la geometria è dato.
SagomaSegnaposto parseSagomaSegnaposto(String json) =>
    SagomaSegnaposto.fromJson(jsonDecode(json) as Map<String, dynamic>);

SagomaSegnaposto? _sagomaCaricata;

/// Carica la sagoma dall'asset. Si memorizza solo il SUCCESSO (il valore, non
/// il Future): un fallimento, o un caricamento rimasto in sospeso in un test
/// con tempo finto, non resta in cache e il tentativo successivo riparte.
/// Non lancia mai: asset mancante o JSON malformato danno `null` e la mappa
/// resta con il cerchio di riserva.
Future<SagomaSegnaposto?> caricaSagomaSegnaposto() async {
  final nota = _sagomaCaricata;
  if (nota != null) return nota;
  try {
    final j = await rootBundle.loadString('assets/brand/segnaposto_sagoma.json');
    return _sagomaCaricata = parseSagomaSegnaposto(j);
  } catch (_) {
    return null;
  }
}

/// Solo test: azzera la cache del successo, per riprovare il caricamento da
/// capo. Costa una riga e rende ripetibili i test che verificano il default.
@visibleForTesting
void azzeraCacheSagoma() => _sagomaCaricata = null;
