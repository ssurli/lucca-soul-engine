import 'package:flutter/material.dart';

import '../api/bff_client.dart';
import '../api/bff_exception.dart';
import '../models/memory_contribution.dart';
import '../models/memory_kind.dart';
import '../models/person_kind.dart';
import '../util/app_strings.dart';
import '../util/local_id.dart';
import '../util/memory_gate.dart';

/// Le licenze proponibili per un conferimento. Sempre tracciata
/// (`MemoryContribution.licenza`, mai vuota — `docs/DATA_CONTRACTS.md` §4):
/// l'utente ne sceglie una esplicitamente, l'app non ne inventa una
/// silenziosa.
const List<String> kMemoryLicenseOptions = ['CC-BY-SA-4.0', 'CC-BY-4.0', 'CC0-1.0'];

/// Apre il conferimento a Urban Memory come bottom sheet, contestuale a una
/// tappa appena vissuta (dall'itinerario) o a un luogo (dalla vista
/// Cittadino). Ritorna `true` se il conferimento è stato inviato con
/// successo, altrimenti `null`.
Future<bool?> showMemoryContributionSheet(
  BuildContext context, {
  required BffClient bffClient,
  required String contributorId,
  required PersonKind contributorKind,
  required List<String> riguarda,
  required AppStrings strings,
  String? esperienzaId,
}) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (_) => MemoryContributionSheet(
      bffClient: bffClient,
      contributorId: contributorId,
      contributorKind: contributorKind,
      riguarda: riguarda,
      strings: strings,
      esperienzaId: esperienzaId,
    ),
  );
}

/// Conferimento LEGGERO e CONTESTUALE alla Urban Memory: non un modulo
/// burocratico, ma tre gesti — che tipo di ricordo, un breve racconto (o un
/// link a un media), e un consenso esplicito con licenza tracciata.
///
/// Punto NON negoziabile: la checkbox di consenso non è mai pre-spuntata e
/// il bottone "Conferisci" resta disabilitato finché non lo è, insieme a
/// licenza e contenuto (`lib/util/memory_gate.dart`,
/// `docs/DATA_CONTRACTS.md` §4/§7 — "nessuna eccezione").
class MemoryContributionSheet extends StatefulWidget {
  final BffClient bffClient;
  final String contributorId;
  final PersonKind contributorKind;
  final List<String> riguarda;
  final AppStrings strings;
  final String? esperienzaId;

  const MemoryContributionSheet({
    super.key,
    required this.bffClient,
    required this.contributorId,
    required this.contributorKind,
    required this.riguarda,
    required this.strings,
    this.esperienzaId,
  });

  @override
  State<MemoryContributionSheet> createState() => _MemoryContributionSheetState();
}

class _MemoryContributionSheetState extends State<MemoryContributionSheet> {
  final TextEditingController _testoController = TextEditingController();
  final TextEditingController _mediaController = TextEditingController();
  MemoryKind _kind = MemoryKind.racconto;
  String _licenza = kMemoryLicenseOptions.first;

  // MAI pre-spuntato: il consenso esplicito è la condizione non negoziabile
  // per persistere il contributo.
  bool _consenso = false;
  bool _inviando = false;
  String? _errore;

  bool get _haContenuto =>
      _testoController.text.trim().isNotEmpty || _mediaController.text.trim().isNotEmpty;

  bool get _puoInviare =>
      puoConferire(consenso: _consenso, licenza: _licenza, haContenuto: _haContenuto) &&
      !_inviando;

  Future<void> _invia() async {
    setState(() {
      _inviando = true;
      _errore = null;
    });
    try {
      final contribution = MemoryContribution(
        id: generateLocalId('memoria'),
        kind: _kind,
        testo: _testoController.text.trim().isEmpty ? null : _testoController.text.trim(),
        mediaUri: _mediaController.text.trim().isEmpty ? null : _mediaController.text.trim(),
        riguarda: widget.riguarda,
        contributorId: widget.contributorId,
        contributorKind: widget.contributorKind,
        esperienzaId: widget.esperienzaId,
        consenso: _consenso,
        licenza: _licenza,
        creatoIl: DateTime.now().toUtc(),
      );
      await widget.bffClient.submitMemory(contribution);
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on BffException catch (error) {
      setState(() => _errore = error.message);
    } finally {
      if (mounted) setState(() => _inviando = false);
    }
  }

  @override
  void dispose() {
    _testoController.dispose();
    _mediaController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final strings = widget.strings;
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.auto_stories_outlined, color: scheme.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(strings.memorySheetTitle, style: Theme.of(context).textTheme.titleLarge),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              strings.memoryIntro,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: scheme.outline),
            ),
            const SizedBox(height: 20),
            Text(strings.memoryKindLabel, style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: MemoryKind.values.map((kind) {
                return ChoiceChip(
                  label: Text(strings.memoryKindName(kind)),
                  selected: _kind == kind,
                  onSelected: (_) => setState(() => _kind = kind),
                );
              }).toList(),
            ),
            const SizedBox(height: 20),
            TextField(
              controller: _testoController,
              maxLines: 4,
              maxLength: 600,
              decoration: InputDecoration(
                labelText: strings.memoryTextLabel,
                hintText: strings.memoryTextHint,
                border: const OutlineInputBorder(),
              ),
              onChanged: (_) => setState(() {}),
            ),
            TextField(
              controller: _mediaController,
              decoration: InputDecoration(
                labelText: strings.memoryMediaLabel,
                hintText: strings.memoryMediaHint,
                border: const OutlineInputBorder(),
              ),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: _licenza,
              decoration: InputDecoration(
                labelText: strings.memoryLicenseLabel,
                border: const OutlineInputBorder(),
              ),
              items: kMemoryLicenseOptions
                  .map((l) => DropdownMenuItem(value: l, child: Text(l)))
                  .toList(),
              onChanged: (value) {
                if (value != null) setState(() => _licenza = value);
              },
            ),
            const SizedBox(height: 8),
            // Consenso esplicito: checkbox mai pre-spuntata. È la condizione
            // non negoziabile per abilitare l'invio (vedi `_puoInviare`).
            CheckboxListTile(
              value: _consenso,
              onChanged: (value) => setState(() => _consenso = value ?? false),
              controlAffinity: ListTileControlAffinity.leading,
              contentPadding: EdgeInsets.zero,
              title: Text(strings.memoryConsentLabel),
              subtitle: Text(strings.memoryConsentDetail),
            ),
            if (_errore != null) ...[
              const SizedBox(height: 4),
              Text(strings.memorySubmitError, style: TextStyle(color: scheme.error)),
              Text(
                _errore!,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: scheme.error),
              ),
            ],
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _puoInviare ? _invia : null,
                child: _inviando
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(strings.memorySubmit),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
