/// Helper puri di formattazione data per la dashboard (Wave 4):
/// `periodo` ("YYYY-MM") e `giorno` ("YYYY-MM-DD") sono le stesse forme
/// attese da `GET /dashboard/index`/`GET /dashboard/flows`
/// (`docs/DATA_CONTRACTS.md` §7/§8). Logica pura, senza Flutter: testabile
/// a riga di comando anche senza SDK (stesso principio di
/// `lib/util/itinerary_diff.dart`).
String twoDigits(int n) => n.toString().padLeft(2, '0');

/// Formatta un `DateTime` come periodo mensile "YYYY-MM", il formato
/// atteso dalla query `periodo` di entrambi gli endpoint `/dashboard/*`.
String formatPeriodo(DateTime data) => '${data.year.toString().padLeft(4, '0')}-${twoDigits(data.month)}';

/// Formatta un `DateTime` come data "YYYY-MM-DD" (solo la parte data,
/// ignora l'orario), il formato atteso dalla query `giorno` di
/// `GET /dashboard/flows`.
String formatDateYmd(DateTime data) =>
    '${data.year.toString().padLeft(4, '0')}-${twoDigits(data.month)}-${twoDigits(data.day)}';

/// Il primo giorno del mese `delta` mesi dopo (o prima, se negativo) quello
/// di `data`. Usato dal selettore di periodo della dashboard per navigare
/// mese per mese senza dipendere da `intl`.
DateTime meseSpostatoDi(DateTime data, int delta) {
  final totale = data.year * 12 + (data.month - 1) + delta;
  final anno = totale ~/ 12;
  final mese = totale % 12 + 1;
  return DateTime(anno, mese);
}
