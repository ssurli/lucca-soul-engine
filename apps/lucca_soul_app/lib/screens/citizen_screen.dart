import 'package:flutter/material.dart';

import '../api/bff_client.dart';
import '../api/bff_exception.dart';
import '../models/memory_contribution.dart';
import '../models/person_kind.dart';
import '../util/app_strings.dart';
import '../util/known_places.dart';
import '../widgets/memory_contribution_sheet.dart';

/// Le lingue in cui può presentarsi la vista Cittadino. Stesso meccanismo
/// del selettore di `onboarding_screen.dart`: qui non esiste un
/// `EmotionalProfile` da cui derivare `lingue`, quindi la scelta resta
/// esplicita.
const Map<String, String> kCitizenLanguages = {'it': 'Italiano', 'en': 'English'};

/// La vista CITTADINO (`docs/BUILD_PLAN.md` Wave 2).
///
/// "Il Cittadino non paga: alimenta la Urban Memory ed è la condizione di
/// sostenibilità sociale del sistema" (CLAUDE.md) — un cliente di prima
/// classe, non un turista di seconda scelta. Mostra i contributi già
/// curati (`GET /memory/{place_id}`) di un luogo e apre il conferimento
/// (`POST /memory`) con `contributor_kind = cittadino`.
class CitizenScreen extends StatefulWidget {
  final BffClient bffClient;
  final String personId;

  const CitizenScreen({super.key, required this.bffClient, required this.personId});

  @override
  State<CitizenScreen> createState() => _CitizenScreenState();
}

class _CitizenScreenState extends State<CitizenScreen> {
  String _lingua = 'it';
  String _placeId = kKnownPlaceIds.first;
  List<MemoryContribution> _memorie = const [];
  bool _caricando = true;
  String? _errore;

  AppStrings get _strings => AppStrings.forLanguages([_lingua]);

  @override
  void initState() {
    super.initState();
    _carica();
  }

  Future<void> _carica() async {
    setState(() {
      _caricando = true;
      _errore = null;
    });
    try {
      final memorie = await widget.bffClient.memoriesForPlace(_placeId);
      setState(() => _memorie = memorie);
    } on BffException catch (error) {
      setState(() => _errore = error.message);
    } finally {
      if (mounted) setState(() => _caricando = false);
    }
  }

  Future<void> _lasciaRicordo() async {
    final strings = _strings;
    final esito = await showMemoryContributionSheet(
      context,
      bffClient: widget.bffClient,
      contributorId: widget.personId,
      contributorKind: PersonKind.cittadino,
      riguarda: [_placeId],
      strings: strings,
    );
    if (esito == true) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(strings.memorySuccess)));
      }
      await _carica();
    }
  }

  @override
  Widget build(BuildContext context) {
    final strings = _strings;
    return Scaffold(
      appBar: AppBar(
        title: Text(strings.citizenTitle),
        actions: [
          DropdownButton<String>(
            value: _lingua,
            underline: const SizedBox.shrink(),
            items: kCitizenLanguages.entries
                .map((e) => DropdownMenuItem(value: e.key, child: Text(e.value)))
                .toList(),
            onChanged: (value) {
              if (value != null) setState(() => _lingua = value);
            },
          ),
          const SizedBox(width: 12),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Text(strings.citizenIntro, style: Theme.of(context).textTheme.bodyMedium),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: DropdownButtonFormField<String>(
                value: _placeId,
                decoration: InputDecoration(
                  labelText: strings.citizenPlaceLabel,
                  border: const OutlineInputBorder(),
                ),
                items: kKnownPlaceIds.map((p) => DropdownMenuItem(value: p, child: Text(p))).toList(),
                onChanged: (value) {
                  if (value != null && value != _placeId) {
                    setState(() => _placeId = value);
                    _carica();
                  }
                },
              ),
            ),
            const SizedBox(height: 8),
            Expanded(child: _buildBody(context, strings)),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _lasciaRicordo,
        icon: const Icon(Icons.auto_stories_outlined),
        label: Text(strings.leaveMemoryAction),
      ),
    );
  }

  Widget _buildBody(BuildContext context, AppStrings strings) {
    if (_caricando) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 12),
            Text(strings.citizenLoading),
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
              Text(strings.citizenError, textAlign: TextAlign.center),
              const SizedBox(height: 4),
              Text(_errore!, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 16),
              FilledButton(onPressed: _carica, child: Text(strings.retry)),
            ],
          ),
        ),
      );
    }

    if (_memorie.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(strings.citizenEmpty, textAlign: TextAlign.center),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _carica,
      child: ListView.builder(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 96),
        itemCount: _memorie.length,
        itemBuilder: (context, index) => _MemoryCard(memoria: _memorie[index], strings: strings),
      ),
    );
  }
}

class _MemoryCard extends StatelessWidget {
  final MemoryContribution memoria;
  final AppStrings strings;

  const _MemoryCard({required this.memoria, required this.strings});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Chip(
                  label: Text(strings.memoryKindName(memoria.kind)),
                  visualDensity: VisualDensity.compact,
                ),
                const Spacer(),
                Text(
                  strings.contributorKindLabel(memoria.contributorKind),
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(color: scheme.outline),
                ),
              ],
            ),
            if (memoria.testo != null) ...[
              const SizedBox(height: 8),
              Text(memoria.testo!),
            ],
            if (memoria.mediaUri != null) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  Icon(Icons.attachment, size: 16, color: scheme.outline),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      memoria.mediaUri!,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(color: scheme.outline),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 8),
            Text(
              memoria.licenza,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(color: scheme.outline),
            ),
          ],
        ),
      ),
    );
  }
}
