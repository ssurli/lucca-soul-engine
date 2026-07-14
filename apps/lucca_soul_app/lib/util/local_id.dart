import 'dart:math';

/// Genera uno pseudonimo locale e casuale con un prefisso dato (es.
/// `generateLocalId('memoria')` -> `memoria_<32 hex>`).
///
/// Usato per gli `id` generati lato client (conferimenti a Urban Memory)
/// quando non esiste ancora un identificativo assegnato dal BFF. Non deriva
/// da alcun dato personale e non viene mai scritto su storage persistente
/// del device — stesso principio di `person_id.dart`.
String generateLocalId(String prefix) {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return '${prefix}_$hex';
}
