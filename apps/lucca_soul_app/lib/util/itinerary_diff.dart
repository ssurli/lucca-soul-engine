import '../models/itinerary.dart';

/// Esiti di `ItineraryStop.esitoAdattamento` che la UI distingue.
const String kEsitoSostituita = 'sostituita';
const String kEsitoMantenutaSenzaAlternativa = 'mantenuta_senza_alternativa';

/// Una tappa e' evidenziata col badge "Cambiata" SOLO se il motore l'ha
/// sostituita. Uno slittamento dell'arrivo o un `reason` diverso non contano:
/// la decisione e' del motore (`esito_adattamento`), non un confronto locale.
bool tappaSostituita(ItineraryStop stop) => stop.esitoAdattamento == kEsitoSostituita;

/// La tappa resta in programma perche' il motore non ha trovato alternative.
bool tappaMantenutaSenzaAlternativa(ItineraryStop stop) =>
    stop.esitoAdattamento == kEsitoMantenutaSenzaAlternativa;

/// Indici delle tappe da evidenziare con il badge "Cambiata".
/// Logica pura, senza Flutter.
Set<int> tappeSostituite(List<ItineraryStop> tappe) => {
      for (var i = 0; i < tappe.length; i++)
        if (tappaSostituita(tappe[i])) i,
    };
