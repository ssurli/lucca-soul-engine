import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

/// Cartella e indice delle foto delle tappe. Il file di una foto è
/// `assets/foto/<experience_id>.jpg`; didascalia e autore stanno in
/// `assets/foto/foto.json`, indicizzati per `experience_id`.
const String kCartellaFoto = 'assets/foto/';
const String kIndiceFoto = 'assets/foto/foto.json';

/// Le tappe fluttuanti e gli eventi promossi non hanno MAI una foto, anche se
/// esistesse un file con quel nome.
bool idSenzaFoto(String experienceId) =>
    experienceId.startsWith('fluttuante-') || experienceId.startsWith('evento-');

/// Voce di `foto.json`: didascalia e autore, entrambe obbligatorie.
class VoceFoto {
  final String didascalia;
  final String autore;
  const VoceFoto(this.didascalia, this.autore);
}

/// Una foto pronta da mostrare.
class FotoTappa {
  final String experienceId;
  final String didascalia;
  final String autore;
  final ImageProvider immagine;
  const FotoTappa({
    required this.experienceId,
    required this.didascalia,
    required this.autore,
    required this.immagine,
  });
}

/// Legge `foto.json`. Json assente o malformato: mappa vuota (nessuna foto,
/// nessun errore). Le voci incomplete (didascalia o autore mancanti, vuoti o
/// non stringa) sono scartate una per una.
Map<String, VoceFoto> parseVociFoto(String? json) {
  if (json == null) return const {};
  try {
    final dati = jsonDecode(json);
    if (dati is! Map<String, dynamic>) return const {};
    final voci = <String, VoceFoto>{};
    dati.forEach((id, v) {
      if (v is! Map<String, dynamic>) return;
      final d = v['didascalia'];
      final a = v['autore'];
      if (d is String && a is String && d.trim().isNotEmpty && a.trim().isNotEmpty) {
        voci[id] = VoceFoto(d.trim(), a.trim());
      }
    });
    return voci;
  } on FormatException {
    return const {};
  }
}

/// Id -> foto o null. Funzione pura: la foto c'è SOLO se esistono entrambi il
/// file jpg negli asset ([assetDisponibili]) e la voce nel json ([voci]), e
/// l'id non è fluttuante/evento.
FotoTappa? risolviFoto({
  required String experienceId,
  required Set<String> assetDisponibili,
  required Map<String, VoceFoto> voci,
  ImageProvider Function(String percorso) fabbricaImmagine = _daAsset,
}) {
  if (idSenzaFoto(experienceId)) return null;
  final percorso = '$kCartellaFoto$experienceId.jpg';
  final voce = voci[experienceId];
  if (voce == null || !assetDisponibili.contains(percorso)) return null;
  return FotoTappa(
    experienceId: experienceId,
    didascalia: voce.didascalia,
    autore: voce.autore,
    immagine: fabbricaImmagine(percorso),
  );
}

ImageProvider _daAsset(String percorso) => AssetImage(percorso);

/// Le foto disponibili: elenco asset + voci del json.
class ArchivioFoto {
  final Set<String> asset;
  final Map<String, VoceFoto> voci;
  final ImageProvider Function(String percorso) fabbricaImmagine;

  const ArchivioFoto({
    this.asset = const {},
    this.voci = const {},
    this.fabbricaImmagine = _daAsset,
  });

  FotoTappa? per(String experienceId) => risolviFoto(
        experienceId: experienceId,
        assetDisponibili: asset,
        voci: voci,
        fabbricaImmagine: fabbricaImmagine,
      );

  /// Dal bundle dell'app. L'elenco degli asset viene dal manifest (nessun
  /// caricamento che lancia per sapere se un file esiste). Qualunque errore:
  /// archivio vuoto, nessuna foto.
  static Future<ArchivioFoto> dalBundle(AssetBundle bundle) async {
    try {
      final manifest = await AssetManifest.loadFromAssetBundle(bundle);
      final asset = manifest.listAssets().where((a) => a.startsWith(kCartellaFoto) && a.endsWith('.jpg')).toSet();
      if (asset.isEmpty) return const ArchivioFoto();
      String? json;
      try {
        json = await bundle.loadString(kIndiceFoto);
      } on Object {
        json = null;
      }
      return ArchivioFoto(asset: asset, voci: parseVociFoto(json));
    } on Object {
      return const ArchivioFoto();
    }
  }
}
