import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../theme/tokens.dart';
import 'segnaposto_mura.dart';

/// Opacita' del velo bianco dentro il baluardo. Una sola costante: il test di
/// contrasto compone `Tk.accento` su questo velo sopra il colore d'area OSM piu'
/// scuro (landfill #b6b592: 4,85:1 a 0,70).
const double kVeloBaluardo = 0.70;

/// Disegna il baluardo: bordo esterno chiaro (5 px, solo fuori dal contorno),
/// interno velato di bianco, contorno accento 2,2 px, traccia del terrapieno,
/// numero accento al centro del corpo. Nessuna ombra: sotto il velo ne
/// altererebbe il colore e il contrasto calcolato.
void disegnaBaluardo(
    Canvas canvas, Size size, SagomaSegnaposto sg, int numero,) {
  final s = sg.scala(size.width);
  Path percorso(List<Offset> punti) {
    final p = Path();
    for (var i = 0; i < punti.length; i++) {
      final q = (punti[i] - sg.viewBox.topLeft) * s;
      i == 0 ? p.moveTo(q.dx, q.dy) : p.lineTo(q.dx, q.dy);
    }
    return p..close();
  }

  final corpo = percorso(sg.contorno);
  // Bordo chiaro: solo la parte esterna, cosi' l'interno e' velo puro.
  canvas.save();
  canvas.clipPath(Path.combine(
    PathOperation.difference,
    Path()..addRect(Offset.zero & size),
    corpo,
  ),);
  canvas.drawPath(
    corpo,
    Paint()
      ..style = PaintingStyle.stroke
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = 5 * s
      ..color = Tk.cardSfondo,
  );
  canvas.restore();
  canvas.drawPath(
      corpo, Paint()..color = Colors.white.withValues(alpha: kVeloBaluardo),);
  canvas.drawPath(
    percorso(sg.traccia),
    Paint()
      ..style = PaintingStyle.stroke
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = 1.2 * s
      ..color = Tk.accento.withValues(alpha: 0.55),
  );
  canvas.drawPath(
    corpo,
    Paint()
      ..style = PaintingStyle.stroke
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = 2.2 * s
      ..color = Tk.accento,
  );
  final dim = sg.dimensioneNumero * s * (numero >= 10 ? 0.85 : 1);
  final tp = TextPainter(
    text: TextSpan(text: '$numero', style: stileTesto(dim, 800, Tk.accento)),
    textDirection: TextDirection.ltr,
  )..layout();
  final c = (sg.centroNumero - sg.viewBox.topLeft) * s;
  tp.paint(canvas, c - Offset(tp.width / 2, tp.height / 2));
}
