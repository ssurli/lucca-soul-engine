// Stanchezza di partenza = 0.0 (approvata dal committente): il segnale di
// partenza non porta stanchezza; accesa e poi spenta, si torna a 0.0.
import 'package:flutter_test/flutter_test.dart';
import 'package:lucca_soul_app/util/signal_presets.dart';

void main() {
  final t = DateTime.utc(2026, 12, 12, 9);

  test('baselineSignal() ha stanchezza 0.0', () {
    expect(baselineSignal(t).stanchezza, 0.0);
  });

  test('segnaleCombinato({stanchezza}) poi segnaleCombinato({}): torna a 0.0', () {
    final acceso = segnaleCombinato({SimulatedSignalKind.stanchezza}, t);
    expect(acceso.stanchezza, 0.85);
    final spento = segnaleCombinato(<SimulatedSignalKind>{}, t);
    expect(spento.stanchezza, 0.0);
  });

  test('segnaleCombinato({}) coincide col segnale di partenza (stanchezza)', () {
    expect(
      segnaleCombinato(<SimulatedSignalKind>{}, t).stanchezza,
      baselineSignal(t).stanchezza,
    );
  });
}
