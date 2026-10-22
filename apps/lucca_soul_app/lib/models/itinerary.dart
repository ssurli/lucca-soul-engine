import 'time_hms.dart';

// ATTENZIONE: ogni campo nuovo del contratto (`packages/contracts`) va
// aggiunto a fromJson E a toJson. L'app rimanda l'itinerario a
// `/itinerary/adapt` con `toJson()`: un campo letto ma non riemesso si perde
// nell'andata e ritorno. Le chiavi con valore null non vengono emesse.

/// `Curiosita.tipo` del contratto. Un valore sconosciuto (futuro) e' letto come
/// `fatto`: mai come `leggenda`, che ha un'etichetta obbligatoria in UI.
enum CuriosityKind { leggenda, fatto }

/// Rispecchia `Curiosita` in `docs/DATA_CONTRACTS.md` §3. Una leggenda ha
/// sempre un testo che inizia con "Si racconta".
class Curiosita {
  final String testo;
  final CuriosityKind tipo;
  final String fonte;

  /// True solo per fonti pubbliche; la UI mostra la riga della fonte SOLO se
  /// true. Default false (assente = nascosta), come nel contratto.
  final bool fontePubblica;

  const Curiosita({
    required this.testo,
    required this.tipo,
    required this.fonte,
    this.fontePubblica = false,
  });

  factory Curiosita.fromJson(Map<String, dynamic> json) => Curiosita(
        testo: json['testo'] as String,
        tipo: json['tipo'] == 'leggenda' ? CuriosityKind.leggenda : CuriosityKind.fatto,
        fonte: json['fonte'] as String,
        fontePubblica: json['fonte_pubblica'] == true,
      );

  // Sempre emesso (anche false): il round-trip verso /itinerary/adapt non
  // perde il dato.
  Map<String, dynamic> toJson() => {
        'testo': testo,
        'tipo': tipo.name,
        'fonte': fonte,
        'fonte_pubblica': fontePubblica,
      };
}

/// Rispecchia `Punto` del contratto: coordinata WGS84. I double sono tenuti
/// com'e' (nessun arrotondamento): l'andata e ritorno JSON e' senza perdite.
class Punto {
  final double lat;
  final double lon;

  const Punto({required this.lat, required this.lon});

  factory Punto.fromJson(Map<String, dynamic> json) => Punto(
        lat: (json['lat'] as num).toDouble(),
        lon: (json['lon'] as num).toDouble(),
      );

  Map<String, dynamic> toJson() => {'lat': lat, 'lon': lon};
}

/// Rispecchia `ItineraryStop` in `docs/DATA_CONTRACTS.md` §3.
/// `reason` è la spiegabilità obbligatoria: il prodotto, non una nota.
class ItineraryStop {
  final String experienceId;
  final TimeHms arrivo;
  final int durataMin;
  final String reason;

  /// Nome leggibile dal catalogo (opzionale nel contratto).
  final String? titolo;

  /// Stringa grezza (non enum): un valore futuro del contratto sopravvive
  /// all'andata e ritorno. Sulla tappa: non_toccata, sostituita,
  /// mantenuta_senza_alternativa.
  final String? esitoAdattamento;

  /// Curiosita della tappa (contratto: default []).
  final List<Curiosita> curiosita;

  /// Punto di arrivo scelto dall'Experience Engine. Null = nessun link
  /// "Come arrivo qui" (es. botteghe dimostrative).
  final Punto? puntoArrivo;

  const ItineraryStop({
    required this.experienceId,
    required this.arrivo,
    required this.durataMin,
    required this.reason,
    this.titolo,
    this.esitoAdattamento,
    this.curiosita = const [],
    this.puntoArrivo,
  });

  factory ItineraryStop.fromJson(Map<String, dynamic> json) {
    return ItineraryStop(
      experienceId: json['experience_id'] as String,
      arrivo: TimeHms.parse(json['arrivo'] as String),
      durataMin: json['durata_min'] as int,
      reason: json['reason'] as String,
      titolo: json['titolo'] as String?,
      esitoAdattamento: json['esito_adattamento'] as String?,
      curiosita: (json['curiosita'] as List<dynamic>? ?? const [])
          .map((e) => Curiosita.fromJson(e as Map<String, dynamic>))
          .toList(),
      puntoArrivo: json['punto_arrivo'] == null
          ? null
          : Punto.fromJson(json['punto_arrivo'] as Map<String, dynamic>),
    );
  }

  Map<String, dynamic> toJson() => {
        'experience_id': experienceId,
        'arrivo': arrivo.toJson(),
        'durata_min': durataMin,
        'reason': reason,
        if (titolo != null) 'titolo': titolo,
        if (esitoAdattamento != null) 'esito_adattamento': esitoAdattamento,
        // Omessa se vuota (come tappe_escluse): il BFF ha default [].
        if (curiosita.isNotEmpty) 'curiosita': curiosita.map((c) => c.toJson()).toList(),
        if (puntoArrivo != null) 'punto_arrivo': puntoArrivo!.toJson(),
      };
}

/// Rispecchia `TappaEsclusa` in `docs/DATA_CONTRACTS.md` §3: una tappa
/// tagliata dal motore, con il motivo leggibile. `esito` resta stringa grezza.
class TappaEsclusa {
  final String experienceId;
  final String esito;
  final String reason;
  final String? titolo;

  const TappaEsclusa({
    required this.experienceId,
    required this.esito,
    required this.reason,
    this.titolo,
  });

  factory TappaEsclusa.fromJson(Map<String, dynamic> json) {
    return TappaEsclusa(
      experienceId: json['experience_id'] as String,
      esito: json['esito'] as String,
      reason: json['reason'] as String,
      titolo: json['titolo'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'experience_id': experienceId,
        'esito': esito,
        'reason': reason,
        if (titolo != null) 'titolo': titolo,
      };
}

/// Rispecchia `Itinerary` in `docs/DATA_CONTRACTS.md` §3.
/// Uscita di `POST /itinerary` e `POST /itinerary/adapt`.
class Itinerary {
  final String personId;
  final List<ItineraryStop> stops;
  final DateTime generatedAt;
  final bool adattatoDaSegnale;
  final int? tempoDisponibileMin;
  final int? tempoEffettivoMin;
  final List<TappaEsclusa> tappeEscluse;

  const Itinerary({
    required this.personId,
    required this.stops,
    required this.generatedAt,
    this.adattatoDaSegnale = false,
    this.tempoDisponibileMin,
    this.tempoEffettivoMin,
    this.tappeEscluse = const [],
  });

  factory Itinerary.fromJson(Map<String, dynamic> json) {
    return Itinerary(
      personId: json['person_id'] as String,
      stops: (json['stops'] as List<dynamic>)
          .map((e) => ItineraryStop.fromJson(e as Map<String, dynamic>))
          .toList(),
      generatedAt: DateTime.parse(json['generated_at'] as String),
      adattatoDaSegnale: json['adattato_da_segnale'] as bool? ?? false,
      tempoDisponibileMin: json['tempo_disponibile_min'] as int?,
      tempoEffettivoMin: json['tempo_effettivo_min'] as int?,
      tappeEscluse: (json['tappe_escluse'] as List<dynamic>? ?? const [])
          .map((e) => TappaEsclusa.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
        'person_id': personId,
        'stops': stops.map((s) => s.toJson()).toList(),
        'generated_at': generatedAt.toIso8601String(),
        'adattato_da_segnale': adattatoDaSegnale,
        if (tempoDisponibileMin != null) 'tempo_disponibile_min': tempoDisponibileMin,
        if (tempoEffettivoMin != null) 'tempo_effettivo_min': tempoEffettivoMin,
        // Omessa se vuota: il BFF ha default [] e l'itinerario nella forma
        // attuale resta identico all'andata e ritorno.
        if (tappeEscluse.isNotEmpty) 'tappe_escluse': tappeEscluse.map((t) => t.toJson()).toList(),
      };
}
