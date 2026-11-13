/// Indicatori noti dell'Urban Intelligence Index (chiavi tecniche del BFF).
const List<String> kIndicatoriNoti = [
  'tempo_medio_esperienza_min',
  'coinvolgimento',
  'tasso_ritorno',
  'attivazione_locale',
  'distribuzione_flussi',
  'nuovi_percorsi',
  'contributi_memoria',
];

/// Estrae dal `motivo_indisponibilita` del BFF la chiave tecnica
/// dell'indicatore, che compare tra apici singoli (`'chiave'`). Ritorna null
/// se il motivo è null/vuoto o se nessuna chiave nota compare in quella forma.
String? indicatoreDaMotivo(String? motivo) {
  if (motivo == null || motivo.isEmpty) return null;
  for (final chiave in kIndicatoriNoti) {
    if (motivo.contains("'$chiave'")) return chiave;
  }
  return null;
}
