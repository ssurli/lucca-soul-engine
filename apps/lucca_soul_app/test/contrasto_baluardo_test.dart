// Contrasto del numero/contorno del baluardo (Tk.accento) sul velo bianco
// (kVeloBaluardo) composto sopra i colori d'area OPACHI dello stile standard
// di OpenStreetMap (openstreetmap-carto, ramo master: landcover.mss,
// style.mss, water.mss). Il piu' scuro e' landfill #b6b592. WCAG >= 4,5.
// Limite: sono i colori di AREA; non copre etichette, strade o edifici disegnati
// sopra le aree, ne' le tile satellitari.
import 'dart:ui';

import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/theme/tokens.dart';
import 'package:lucca_soul_app/widgets/segnaposto_baluardo.dart';

const _coloriAreaOsm = <String, Color>{
  'landfill': Color(0xFFB6B592),
  'cemetery': Color(0xFFAACBAF),
  'quarry': Color(0xFFC5C3C3),
  'forest': Color(0xFFADD19E),
  'construction': Color(0xFFC7C7B4),
  'pitch': Color(0xFF88E0BE),
  'water': Color(0xFFAAD3DF),
  'scrub': Color(0xFFC8D7AB),
  'orchard': Color(0xFFAEDFA3),
  'built-up-lowzoom': Color(0xFFD0D0D0),
};

void main() {
  const velo = Color(0xFFFFFFFF);
  for (final e in _coloriAreaOsm.entries) {
    test(
        'accento su velo $kVeloBaluardo sopra ${e.key} (${e.value.toARGB32().toRadixString(16)}): >= 4,5',
        () {
      final sfondo =
          Color.alphaBlend(velo.withValues(alpha: kVeloBaluardo), e.value);
      expect(sfondo.a, 1.0);
      final r = rapportoContrasto(Tk.accento, sfondo);
      expect(r, greaterThanOrEqualTo(4.5), reason: '${e.key}: $r');
    });
  }

  test('il caso peggiore e landfill e il velo e quello dichiarato', () {
    final rr = {
      for (final e in _coloriAreaOsm.entries)
        e.key: rapportoContrasto(
          Tk.accento,
          Color.alphaBlend(velo.withValues(alpha: kVeloBaluardo), e.value),
        ),
    };
    final peggiore = rr.entries.reduce((a, b) => a.value <= b.value ? a : b);
    expect(peggiore.key, 'landfill');
    expect(peggiore.value, closeTo(4.853, 0.01));
    expect(kVeloBaluardo, 0.70);
  });
}
