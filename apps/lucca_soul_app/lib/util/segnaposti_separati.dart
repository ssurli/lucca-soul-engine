import 'dart:math' as math;
import 'dart:ui' show Offset;

/// Diametro del cerchio di riserva del segnaposto (px di schermo). Con la
/// sagoma delle Mura si usa invece la sua larghezza (`diametroCollisione`).
const double kDiametroSegnaposto = 32;

/// Scarto minimo tra i bordi di due cerchi dopo la separazione (px).
const double kLuceSegnaposti = 1;

/// Scosta quanto basta i punti [centri] (px di schermo: centri dei cerchi di
/// riserva, oppure punte delle sagome) perché nessuna coppia disti meno di
/// [diametro] + [kLuceSegnaposti]: i segnaposti non si sovrappongono e il punto
/// di ciascuno è fuori dall'area di tocco degli altri.
///
/// Logica pura e deterministica: stesso ingresso, stesso risultato. Coppie
/// già distanti non si muovono. Punti identici si separano lungo una direzione
/// fissata dall'indice. Restituisce una lista parallela a [centri].
List<Offset> separaSegnaposti(
  List<Offset> centri, {
  double diametro = kDiametroSegnaposto,
}) {
  final n = centri.length;
  final p = List<Offset>.of(centri);
  final minima = diametro + kLuceSegnaposti;
  for (var giro = 0; giro < 200; giro++) {
    var mosso = false;
    for (var i = 0; i < n; i++) {
      for (var j = i + 1; j < n; j++) {
        final delta = p[j] - p[i];
        final d = delta.distance;
        if (d >= minima) continue;
        final Offset dir = d > 1e-6
            ? delta / d
            : Offset.fromDirection(2 * math.pi * j / n);
        final spinta = dir * ((minima - d) / 2 + 1e-3);
        p[i] -= spinta;
        p[j] += spinta;
        mosso = true;
      }
    }
    if (!mosso) break;
  }
  return p;
}
