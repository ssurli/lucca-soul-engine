/// Eccezione sollevata quando il BFF risponde con un errore, non è
/// raggiungibile o restituisce un corpo che non rispetta il contratto
/// atteso. Il messaggio non contiene mai dati personali: al più il testo di
/// errore in italiano restituito dal BFF stesso (`detail`).
class BffException implements Exception {
  final String message;
  final int? statusCode;

  const BffException(this.message, {this.statusCode});

  @override
  String toString() =>
      statusCode == null ? 'BffException: $message' : 'BffException($statusCode): $message';
}
