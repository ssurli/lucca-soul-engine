/// Eccezione sollevata quando il BFF risponde con un errore, non è
/// raggiungibile o restituisce un corpo che non rispetta il contratto
/// atteso. Il messaggio non contiene mai dati personali: al più il testo di
/// errore in italiano restituito dal BFF stesso (`detail`).
class BffException implements Exception {
  final String message;
  final int? statusCode;

  /// Vero se il BFF non e' stato raggiunto (rete assente, timeout). Il
  /// messaggio tecnico resta nei log di debug: la UI mostra un testo proprio.
  final bool connessioneAssente;

  const BffException(this.message, {this.statusCode}) : connessioneAssente = false;

  const BffException.rete(this.message)
      : statusCode = null,
        connessioneAssente = true;

  @override
  String toString() =>
      statusCode == null ? 'BffException: $message' : 'BffException($statusCode): $message';
}
