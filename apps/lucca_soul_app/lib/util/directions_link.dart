import 'package:url_launcher/url_launcher.dart';

import '../models/itinerary.dart';

/// Double in notazione decimale a precisione piena (shortest round-trip di
/// Dart), con punto decimale: indipendente dalla locale. Dart passa
/// all'esponenziale sotto 1e-6: in quel caso si espande a mano.
String _decimale(double v) {
  final s = v.toString();
  if (!s.contains('e') && !s.contains('E')) return s;
  var fisso = v.toStringAsFixed(20);
  if (fisso.contains('.')) {
    fisso = fisso.replaceFirst(RegExp(r'0+$'), '').replaceFirst(RegExp(r'\.$'), '');
  }
  return fisso;
}

/// Link "Come arrivo qui": null se la tappa non ha un punto di arrivo.
/// Nessuna chiave, nessun arrotondamento.
String? urlComeArrivo(Punto? punto) {
  if (punto == null) return null;
  return 'https://www.google.com/maps/dir/?api=1'
      '&destination=${_decimale(punto.lat)},${_decimale(punto.lon)}'
      '&travelmode=walking';
}

/// Apre il link in una NUOVA scheda (web: `_blank`; altrove: app esterna).
Future<void> apriInNuovaScheda(String url) async {
  await launchUrl(
    Uri.parse(url),
    mode: LaunchMode.externalApplication,
    webOnlyWindowName: '_blank',
  );
}
