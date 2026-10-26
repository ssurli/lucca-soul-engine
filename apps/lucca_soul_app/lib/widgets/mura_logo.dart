import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;

import '../theme/tokens.dart';
import '../util/app_strings.dart';

/// Un punto del logo: coordinate normalizzate 0..1 (nord in alto).
class PuntoMura {
  final String nome;
  final bool piattaforma;
  final double x;
  final double y;
  const PuntoMura(this.nome, this.piattaforma, this.x, this.y);
}

/// Legge la geometria del logo dal dato `assets/brand/mura_punti.json`
/// (stesso file per favicon e icone). Nessuna coordinata nel codice.
List<PuntoMura> parsePuntiMura(String json) {
  final m = jsonDecode(json) as Map<String, dynamic>;
  return [
    for (final p in m['punti'] as List<dynamic>)
      PuntoMura(
        (p as Map<String, dynamic>)['nome'] as String,
        p['tipo'] == 'piattaforma',
        (p['x'] as num).toDouble(),
        (p['y'] as num).toDouble(),
      ),
  ];
}

Future<List<PuntoMura>>? _cache;
Future<List<PuntoMura>> caricaPuntiMura() => _cache ??=
    rootBundle.loadString('assets/brand/mura_punti.json').then(parsePuntiMura);

/// Logo delle Mura: costellazione di 11 punti (10 baluardi, 1 piattaforma).
/// Colori: solo [colore] (di norma il testo su testata); le linee di
/// collegamento usano il grigio NON testuale.
class MuraLogo extends StatelessWidget {
  final double size;
  final Color colore;
  const MuraLogo({super.key, this.size = 32, this.colore = Tk.testoSuTestata});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: kMuraLogoLabel,
      container: true,
      image: true,
      excludeSemantics: true,
      child: SizedBox(
        width: size,
        height: size,
        child: FutureBuilder<List<PuntoMura>>(
          future: caricaPuntiMura(),
          builder: (context, snap) =>
              CustomPaint(painter: _MuraPainter(snap.data ?? const [], colore)),
        ),
      ),
    );
  }
}

class _MuraPainter extends CustomPainter {
  final List<PuntoMura> punti;
  final Color colore;
  _MuraPainter(this.punti, this.colore);

  @override
  void paint(Canvas canvas, Size size) {
    if (punti.isEmpty) return;
    final lato = math.min(size.width, size.height);
    final pad = lato * 0.1;
    final area = lato - 2 * pad;
    Offset pos(PuntoMura p) => Offset(pad + p.x * area, pad + p.y * area);

    // Anello: i punti ordinati per angolo attorno al baricentro.
    final c = Offset(
      punti.map((p) => p.x).reduce((a, b) => a + b) / punti.length,
      punti.map((p) => p.y).reduce((a, b) => a + b) / punti.length,
    );
    final ordine = [...punti]..sort((a, b) => math
        .atan2(a.y - c.dy, a.x - c.dx)
        .compareTo(math.atan2(b.y - c.dy, b.x - c.dx)),);
    final linea = Paint()
      ..color = Tk.grigioNonTestuale
      ..strokeWidth = math.max(1, lato / 40)
      ..style = PaintingStyle.stroke;
    final path = Path()..moveTo(pos(ordine.first).dx, pos(ordine.first).dy);
    for (final p in ordine.skip(1)) {
      path.lineTo(pos(p).dx, pos(p).dy);
    }
    path.close();
    canvas.drawPath(path, linea);

    final pieno = Paint()..color = colore;
    final raggio = lato / 15;
    for (final p in punti) {
      if (p.piattaforma) {
        // La piattaforma: anello più grande, per distinguerla dai baluardi.
        canvas.drawCircle(pos(p), raggio * 1.5, Paint()..color = Tk.testata);
        canvas.drawCircle(
          pos(p),
          raggio * 1.5,
          Paint()
            ..color = colore
            ..style = PaintingStyle.stroke
            ..strokeWidth = math.max(1.2, lato / 30),
        );
      } else {
        canvas.drawCircle(pos(p), raggio, pieno);
      }
    }
  }

  @override
  bool shouldRepaint(_MuraPainter old) =>
      old.punti != punti || old.colore != colore;
}
