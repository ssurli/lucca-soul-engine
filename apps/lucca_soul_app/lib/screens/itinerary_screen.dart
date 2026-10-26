import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart' show TileProvider;

import '../api/bff_client.dart';
import '../api/bff_exception.dart';
import '../models/emotional_profile.dart';
import '../models/itinerary.dart';
import '../models/person_kind.dart';
import '../models/signal.dart';
import '../models/visitor_context.dart';
import '../theme/app_theme.dart';
import '../theme/tokens.dart';
import '../util/app_strings.dart';
import '../util/clock.dart';
import '../util/directions_link.dart';
import '../util/excluded_stop_line.dart';
import '../util/itinerary_diff.dart';
import '../util/known_places.dart';
import '../util/signal_presets.dart';
import '../widgets/adaptive_card.dart';
import '../widgets/colonna_centrata.dart';
import '../widgets/mappa_itinerario.dart';
import '../widgets/testata_giornata.dart';
import '../widgets/memory_contribution_sheet.dart';

/// Schermata dell'itinerario: la giornata generata da `POST /itinerary`,
/// ogni tappa con orario e `reason` in evidenza (la spiegabilità è il
/// prodotto), più la card adattiva che riscrive le tappe a fronte di un
/// segnale (`POST /itinerary/adapt`).
class ItineraryScreen extends StatefulWidget {
  final BffClient bffClient;
  final String personId;
  final EmotionalProfile profile;

  /// Solo test: strato di tile finto (nessuna rete). Default: rete.
  final TileProvider? tileProvider;

  const ItineraryScreen({
    this.tileProvider,
    super.key,
    required this.bffClient,
    required this.personId,
    required this.profile,
  });

  @override
  State<ItineraryScreen> createState() => _ItineraryScreenState();
}

class _ItineraryScreenState extends State<ItineraryScreen> {
  late AppStrings _strings;
  final Signal _segnale = baselineSignal();

  /// L'itinerario di `POST /itinerary`, conservato per ogni adattamento.
  Itinerary? _originale;

  /// Quello mostrato: l'originale o l'ultimo adattamento.
  Itinerary? _itinerario;
  bool _caricando = true;
  String? _errore;

  @override
  void initState() {
    super.initState();
    _strings = AppStrings.forLanguages(widget.profile.lingue);
    _caricaItinerario();
  }

  Future<void> _caricaItinerario() async {
    setState(() {
      _caricando = true;
      _errore = null;
    });
    try {
      final contesto = VisitorContext(
        personId: widget.personId,
        kind: PersonKind.turista,
        profile: widget.profile,
        signal: _segnale,
      );
      final itinerario = await widget.bffClient.itinerary(contesto);
      setState(() {
        _originale = itinerario;
        _itinerario = itinerario;
      });
    } on BffException catch (error) {
      setState(() => _errore = error.message);
    } finally {
      if (mounted) setState(() => _caricando = false);
    }
  }

  void _onMostrato(Itinerary mostrato) =>
      setState(() => _itinerario = mostrato);

  /// Apre il conferimento a Urban Memory, contestuale alla tappa appena
  /// vissuta: `esperienza_id` e i luoghi che "riguarda" sono passati dal
  /// contesto, non chiesti di nuovo all'utente (Wave 2).
  Future<void> _lasciaRicordo(ItineraryStop stop) async {
    final esito = await showMemoryContributionSheet(
      context,
      bffClient: widget.bffClient,
      contributorId: widget.personId,
      contributorKind: PersonKind.turista,
      riguarda: riguardaPerEsperienza(stop.experienceId),
      esperienzaId: stop.experienceId,
      strings: _strings,
    );
    if (esito == true && mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(_strings.memorySuccess)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const TitoloMarchio()),
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_caricando) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 12),
            Text(_strings.itineraryLoading),
          ],
        ),
      );
    }

    if (_errore != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.wifi_off,
                  size: 40, color: Theme.of(context).colorScheme.error,),
              const SizedBox(height: 12),
              Text(_strings.itineraryError, textAlign: TextAlign.center),
              const SizedBox(height: 4),
              Text(_errore!,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodySmall,),
              const SizedBox(height: 16),
              FilledButton(
                  onPressed: _caricaItinerario, child: Text(_strings.retry),),
            ],
          ),
        ),
      );
    }

    final itinerario = _itinerario;
    if (itinerario == null || itinerario.stops.isEmpty) {
      return Center(child: Text(_strings.emptyStops));
    }

    return Column(
      children: [
        TestataGiornata(
            itinerario: itinerario, data: _segnale.data ?? Orologio.adesso().toLocal(), strings: _strings,),
        Expanded(
          child: ColonnaCentrata(
            child: RefreshIndicator(
              onRefresh: _caricaItinerario,
              child: ListView(
                padding: const EdgeInsets.only(bottom: 24),
                children: [
                  MappaItinerario(
                    tappe: itinerario.stops,
                    tileProvider: widget.tileProvider,
                    etichettaTappa: _strings.genericStop,
                  ),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                    child: Text(_strings.itineraryTitle,
                        style: Theme.of(context).textTheme.headlineSmall,),
                  ),
                  AdaptiveCard(
                    key: ObjectKey(_originale),
                    bffClient: widget.bffClient,
                    original: _originale!,
                    profile: widget.profile,
                    strings: _strings,
                    onShown: _onMostrato,
                  ),
                  if (itinerario.adattatoDaSegnale)
                    _AdattatoBadge(strings: _strings),
                  for (var i = 0; i < itinerario.stops.length; i++)
                    StopCard(
                      stop: itinerario.stops[i],
                      evidenziata: tappaSostituita(itinerario.stops[i]),
                      mantenutaSenzaAlternativa:
                          tappaMantenutaSenzaAlternativa(itinerario.stops[i]),
                      strings: _strings,
                      numero: i + 1,
                      onLasciaRicordo: () =>
                          _lasciaRicordo(itinerario.stops[i]),
                    ),
                  if (itinerario.tappeEscluse.isNotEmpty)
                    TappeEscluseNote(
                        escluse: itinerario.tappeEscluse, strings: _strings,),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// Note in fondo alla lista: le tappe tagliate dal motore, con il loro reason.
class TappeEscluseNote extends StatelessWidget {
  final List<TappaEsclusa> escluse;
  final AppStrings strings;

  const TappeEscluseNote(
      {super.key, required this.escluse, required this.strings,});

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(strings.excludedStopsTitle, style: textTheme.titleSmall),
          const SizedBox(height: 4),
          for (final t in escluse)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(rigaTappaEsclusa(t, strings),
                  style: textTheme.bodySmall,),
            ),
        ],
      ),
    );
  }
}

class _AdattatoBadge extends StatelessWidget {
  final AppStrings strings;

  const _AdattatoBadge({required this.strings});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Chip(
        avatar: const Icon(Icons.autorenew, size: 18),
        label: Text(strings.adaptedBadge),
        backgroundColor: Theme.of(context).colorScheme.secondaryContainer,
      ),
    );
  }
}

/// Una curiosita sotto il motivo. La leggenda porta sempre l'etichetta
/// "Leggenda"; il fatto la etichetta "Curiosita'", mai "Leggenda".
class CuriosityTile extends StatelessWidget {
  final Curiosita curiosita;
  final AppStrings strings;

  const CuriosityTile(
      {super.key, required this.curiosita, required this.strings,});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final leggenda = curiosita.tipo == CuriosityKind.leggenda;
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            leggenda ? strings.legendLabel : strings.curiosityLabel,
            style: theme.textTheme.labelMedium
                ?.copyWith(fontWeight: FontWeight.bold),
          ),
          Text(curiosita.testo, style: theme.textTheme.bodyMedium),
          if (curiosita.fontePubblica)
            Text(strings.sourceLabel(curiosita.fonte),
                style: theme.textTheme.bodySmall,),
        ],
      ),
    );
  }
}

class StopCard extends StatelessWidget {
  final ItineraryStop stop;
  final bool evidenziata;

  /// La tappa resta in programma perché il motore non ha trovato alternative.
  final bool mantenutaSenzaAlternativa;
  final AppStrings strings;
  final VoidCallback onLasciaRicordo;

  /// Numero della tappa (1-based), nello stesso ordine della mappa. Null = senza cerchio.
  final int? numero;

  const StopCard({
    super.key,
    required this.stop,
    required this.evidenziata,
    this.mantenutaSenzaAlternativa = false,
    required this.strings,
    required this.onLasciaRicordo,
    this.numero,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final etichetta = evidenziata
        ? EtichettaEsito(
            testo: strings.changedStop,
            sfondo: Tk.sostituitaSfondo,
            colore: Tk.sostituitaTesto,)
        : mantenutaSenzaAlternativa
            ? EtichettaEsito(
                testo: strings.keptNoAlternative,
                sfondo: Tk.mantenutaSfondo,
                colore: Tk.mantenutaTesto,)
            : null;
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (numero != null) ...[
              Container(
                width: 32,
                height: 32,
                alignment: Alignment.center,
                decoration: const BoxDecoration(
                    color: Tk.accento, shape: BoxShape.circle,),
                child: Text('$numero',
                    style: stileTesto(15, 800, Tk.testoSuAccento),),
              ),
              const SizedBox(width: 12),
            ],
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (etichetta != null)
                    Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: etichetta,),
                  Text(titoloTappa(stop.titolo, strings),
                      style: theme.textTheme.titleMedium,),
                  const SizedBox(height: 4),
                  Text(
                    '${stop.arrivo.label} · ${stop.durataMin} ${strings.durationLabel}',
                    style: stileTesto(14, 700, Tk.testoSecondario),
                  ),
                  const SizedBox(height: 10),
                  // Il `reason` è il prodotto: sempre in evidenza, mai una nota a
                  // piè di pagina.
                  Text(stop.reason, style: theme.textTheme.bodyLarge),
                  for (final c in stop.curiosita)
                    CuriosityTile(curiosita: c, strings: strings),
                  if (stop.puntoArrivo != null)
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton.icon(
                        onPressed: () =>
                            apriInNuovaScheda(urlComeArrivo(stop.puntoArrivo)!),
                        icon: const Icon(Icons.directions_walk, size: 18),
                        label: Text(strings.howToArrive),
                      ),
                    ),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                      onPressed: onLasciaRicordo,
                      icon: const Icon(Icons.auto_stories_outlined, size: 18),
                      label: Text(strings.leaveMemoryAction),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Etichetta dell'esito (solo se c'è un esito): "sostituita" o "resta in programma".
class EtichettaEsito extends StatelessWidget {
  final String testo;
  final Color sfondo;
  final Color colore;
  const EtichettaEsito(
      {super.key,
      required this.testo,
      required this.sfondo,
      required this.colore,});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
          color: sfondo, borderRadius: BorderRadius.circular(Tk.raggio),),
      child: Text(testo, style: stileTesto(13, 700, colore)),
    );
  }
}
