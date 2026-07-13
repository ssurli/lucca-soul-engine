import 'dart:math';

/// Genera uno pseudonimo locale e casuale per `VisitorContext.personId`.
///
/// Non è derivato da alcun dato personale (nome, email, dispositivo...) e
/// vive solo in memoria per la durata della sessione: non viene mai scritto
/// su storage persistente del device, in linea con "niente PII on device".
String generatePersonId() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return 'visitor_$hex';
}
