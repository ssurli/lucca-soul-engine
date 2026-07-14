import 'package:flutter/material.dart';

import '../api/bff_client.dart';
import '../api/bff_exception.dart';
import '../models/emotional_profile.dart';
import '../models/itinerary.dart';
import '../models/person_kind.dart';
import '../models/signal.dart';
import '../models/visitor_context.dart';
import '../util/app_strings.dart';
import '../util/itinerary_diff.dart';
import '../util/known_places.dart';
import '../util/signal_presets.dart';
import '../widgets/adaptive_card.dart';
import '../widgets/memory_contribution_sheet.dart';

/// Schermata dell'itinerario: la giornata generata da `POST /itinerary`,
/// ogni tappa con orario e `reason` in evidenza (la spiegabilità è il
/// prodotto), più la card adattiva che riscrive le tappe a fronte di un
/// segnale (`POST /itinerary/adapt`).
class ItineraryScreen extends StatefulWidget {
  final BffClient bffClient;
  final String personId;
  final EmotionalProfile profile;

  const ItineraryScreen({
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
  Signal _segnale = baselineSignal();
  Itinerary? _itinerario;
  Set<int> _tappeEvidenziate = const {};
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
        _itinerario = itinerario;
        _tappeEvidenziate = const {};
      });
    } on BffException catch (error) {
      setState(() => _errore = error.message);
    } finally {
      if (mounted) setState(() => _caricando = false);
    }
  }

  void _onAdattato(Itinerary nuovoItinerario, Signal nuovoSegnale) {
    final precedente = _itinerario?.stops ?? const <ItineraryStop>[];
    setState(() {
      _tappeEvidenziate = tappeCambiate(prima: precedente, dopo: nuovoItinerario.stops);
      _itinerario = nuovoItinerario;
      _segnale = nuovoSegnale;
    });
  }

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
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(_strings.memorySuccess)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_strings.itineraryTitle)),
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
              Icon(Icons.wifi_off, size: 40, color: Theme.of(context).colorScheme.error),
              const SizedBox(height: 12),
              Text(_strings.itineraryError, textAlign: TextAlign.center),
              const SizedBox(height: 4),
              Text(_errore!, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 16),
              FilledButton(onPressed: _caricaItinerario, child: Text(_strings.retry)),
            ],
          ),
        ),
      );
    }

    final itinerario = _itinerario;
    if (itinerario == null || itinerario.stops.isEmpty) {
      return Center(child: Text(_strings.emptyStops));
    }

    return RefreshIndicator(
      onRefresh: _caricaItinerario,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          AdaptiveCard(
            bffClient: widget.bffClient,
            itinerary: itinerario,
            signal: _segnale,
            strings: _strings,
            onAdapted: _onAdattato,
          ),
          if (itinerario.adattatoDaSegnale) _AdattatoBadge(strings: _strings),
          for (var i = 0; i < itinerario.stops.length; i++)
            _StopCard(
              stop: itinerario.stops[i],
              evidenziata: _tappeEvidenziate.contains(i),
              strings: _strings,
              onLasciaRicordo: () => _lasciaRicordo(itinerario.stops[i]),
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

class _StopCard extends StatelessWidget {
  final ItineraryStop stop;
  final bool evidenziata;
  final AppStrings strings;
  final VoidCallback onLasciaRicordo;

  const _StopCard({
    required this.stop,
    required this.evidenziata,
    required this.strings,
    required this.onLasciaRicordo,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: evidenziata ? scheme.tertiaryContainer : null,
      shape: evidenziata
          ? RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: scheme.tertiary, width: 2),
            )
          : null,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  stop.arrivo.label,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
                ),
                const SizedBox(width: 8),
                Text('· ${stop.durataMin} ${strings.durationLabel}'),
                const Spacer(),
                if (evidenziata)
                  Chip(
                    label: Text(strings.changedStop),
                    visualDensity: VisualDensity.compact,
                    backgroundColor: scheme.tertiary,
                    labelStyle: TextStyle(color: scheme.onTertiary),
                  ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              stop.experienceId,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: scheme.outline),
            ),
            const SizedBox(height: 12),
            // Il `reason` è il prodotto: sempre in evidenza, mai una nota a
            // piè di pagina.
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: scheme.primaryContainer.withOpacity(evidenziata ? 0.6 : 1.0),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.auto_awesome, size: 18, color: scheme.onPrimaryContainer),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      stop.reason,
                      style: Theme.of(context)
                          .textTheme
                          .bodyMedium
                          ?.copyWith(color: scheme.onPrimaryContainer),
                    ),
                  ),
                ],
              ),
            ),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: onLasciaRicordo,
                icon: const Icon(Icons.auto_stories_outlined, size: 18),
                label: Text(strings.leaveMemoryAction),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
