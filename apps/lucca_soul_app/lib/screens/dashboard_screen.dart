import 'package:flutter/material.dart';

import '../api/bff_client.dart';
import '../api/bff_exception.dart';
import '../models/dashboard_flows_response.dart';
import '../models/dashboard_index_response.dart';
import '../models/flow_cell.dart';
import '../models/urban_intelligence_index.dart';
import '../util/app_strings.dart';
import '../util/periodo.dart';

/// Le lingue in cui può presentarsi la dashboard. Stesso meccanismo del
/// selettore di `citizen_screen.dart`: qui non esiste un `EmotionalProfile`
/// da cui derivare `lingue`.
const Map<String, String> kDashboardLanguages = {'it': 'Italiano', 'en': 'English'};

/// Le tre viste che condividono `GET /dashboard/index` e
/// `GET /dashboard/flows` (`docs/BUILD_PLAN.md` Wave 4, "i cinque clienti"
/// del white paper): Comune, Hotel, Museo. Hotel e Museo leggono lo STESSO
/// substrato dati del Comune con un taglio più mirato (solo gli indicatori
/// rilevanti per un operatore che vuole capire come contribuire a
/// distribuire i flussi) — non esiste un terzo endpoint, solo un filtro
/// lato client su quali indicatori mettere in evidenza.
enum DashboardAudience { comune, hotel, museo }

extension on DashboardAudience {
  bool get isOperatore => this != DashboardAudience.comune;

  String label(AppStrings strings) {
    switch (this) {
      case DashboardAudience.comune:
        return strings.dashboardAudienceComune;
      case DashboardAudience.hotel:
        return strings.dashboardAudienceHotel;
      case DashboardAudience.museo:
        return strings.dashboardAudienceMuseo;
    }
  }

  IconData get icon {
    switch (this) {
      case DashboardAudience.comune:
        return Icons.account_balance_outlined;
      case DashboardAudience.hotel:
        return Icons.hotel_outlined;
      case DashboardAudience.museo:
        return Icons.museum_outlined;
    }
  }
}

/// Dashboard Comune/Operatori (`docs/BUILD_PLAN.md` Wave 4): heatmap dei
/// flussi (`GET /dashboard/flows`) + gli 8 indicatori dell'Urban
/// Intelligence Index (`GET /dashboard/index`), con un taglio diverso per
/// Comune (cruscotto completo) e Hotel/Museo (solo `distribuzione_flussi` +
/// `attivazione_locale`).
///
/// "Le Smart City raccolgono dati. Le città intelligenti generano
/// significato." (CLAUDE.md) — questa schermata non aggiunge alcun campo
/// commerciale: nessun `partner_id`/`prezzo_eur` esiste nel contratto della
/// dashboard, e non ne viene inventato uno qui.
class DashboardScreen extends StatefulWidget {
  final BffClient bffClient;

  const DashboardScreen({super.key, required this.bffClient});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  String _lingua = 'it';
  DashboardAudience _audience = DashboardAudience.comune;
  DateTime _mese = DateTime(DateTime.now().year, DateTime.now().month);
  DateTime? _filtroGiorno;
  int? _filtroOra;

  DashboardIndexResponse? _indexResponse;
  bool _caricandoIndex = true;
  String? _erroreIndex;

  DashboardFlowsResponse? _flowsResponse;
  bool _caricandoFlows = true;
  String? _erroreFlows;

  AppStrings get _strings => AppStrings.forLanguages([_lingua]);
  String get _periodo => formatPeriodo(_mese);

  @override
  void initState() {
    super.initState();
    _caricaTutto();
  }

  Future<void> _caricaTutto() async {
    await Future.wait([_caricaIndex(), _caricaFlows()]);
  }

  Future<void> _caricaIndex() async {
    setState(() {
      _caricandoIndex = true;
      _erroreIndex = null;
    });
    try {
      final risposta = await widget.bffClient.dashboardIndex(_periodo);
      if (!mounted) return;
      setState(() => _indexResponse = risposta);
    } on BffException catch (error) {
      if (!mounted) return;
      setState(() => _erroreIndex = error.message);
    } finally {
      if (mounted) setState(() => _caricandoIndex = false);
    }
  }

  Future<void> _caricaFlows() async {
    setState(() {
      _caricandoFlows = true;
      _erroreFlows = null;
    });
    try {
      final risposta = await widget.bffClient.dashboardFlows(
        periodo: _periodo,
        giorno: _filtroGiorno,
        ora: _filtroOra,
      );
      if (!mounted) return;
      setState(() => _flowsResponse = risposta);
    } on BffException catch (error) {
      if (!mounted) return;
      setState(() => _erroreFlows = error.message);
    } finally {
      if (mounted) setState(() => _caricandoFlows = false);
    }
  }

  void _cambiaMese(int delta) {
    setState(() => _mese = meseSpostatoDi(_mese, delta));
    _caricaTutto();
  }

  Future<void> _scegliGiorno() async {
    final primoGiorno = DateTime(_mese.year, _mese.month);
    final ultimoGiorno = DateTime(_mese.year, _mese.month + 1, 0);
    final scelto = await showDatePicker(
      context: context,
      initialDate: _filtroGiorno ?? primoGiorno,
      firstDate: primoGiorno,
      lastDate: ultimoGiorno,
    );
    if (scelto != null) {
      setState(() => _filtroGiorno = scelto);
      _caricaFlows();
    }
  }

  void _rimuoviFiltri() {
    setState(() {
      _filtroGiorno = null;
      _filtroOra = null;
    });
    _caricaFlows();
  }

  @override
  Widget build(BuildContext context) {
    final strings = _strings;
    return Scaffold(
      appBar: AppBar(
        title: Text(strings.dashboardTitle),
        actions: [
          DropdownButton<String>(
            value: _lingua,
            underline: const SizedBox.shrink(),
            items: kDashboardLanguages.entries
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
        child: RefreshIndicator(
          onRefresh: _caricaTutto,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
            children: [
              _AudienceSelector(
                audience: _audience,
                strings: strings,
                onChanged: (value) => setState(() => _audience = value),
              ),
              const SizedBox(height: 8),
              Text(
                _audience.isOperatore
                    ? strings.dashboardAudienceOperatorHint
                    : strings.dashboardAudienceComuneHint,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.outline,
                    ),
              ),
              const SizedBox(height: 16),
              _PeriodSelector(
                periodo: _periodo,
                strings: strings,
                onPrevious: () => _cambiaMese(-1),
                onNext: () => _cambiaMese(1),
              ),
              const SizedBox(height: 24),
              _IndexSection(
                strings: strings,
                audience: _audience,
                caricando: _caricandoIndex,
                errore: _erroreIndex,
                risposta: _indexResponse,
                onRetry: _caricaIndex,
              ),
              const SizedBox(height: 32),
              _FlowsSection(
                strings: strings,
                filtroGiorno: _filtroGiorno,
                filtroOra: _filtroOra,
                caricando: _caricandoFlows,
                errore: _erroreFlows,
                risposta: _flowsResponse,
                onRetry: _caricaFlows,
                onScegliGiorno: _scegliGiorno,
                onCambiaOra: (ora) {
                  setState(() => _filtroOra = ora);
                  _caricaFlows();
                },
                onRimuoviFiltri: _rimuoviFiltri,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AudienceSelector extends StatelessWidget {
  final DashboardAudience audience;
  final AppStrings strings;
  final ValueChanged<DashboardAudience> onChanged;

  const _AudienceSelector({required this.audience, required this.strings, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<DashboardAudience>(
      segments: DashboardAudience.values
          .map((a) => ButtonSegment(value: a, label: Text(a.label(strings)), icon: Icon(a.icon)))
          .toList(),
      selected: {audience},
      onSelectionChanged: (selection) => onChanged(selection.first),
    );
  }
}

class _PeriodSelector extends StatelessWidget {
  final String periodo;
  final AppStrings strings;
  final VoidCallback onPrevious;
  final VoidCallback onNext;

  const _PeriodSelector({
    required this.periodo,
    required this.strings,
    required this.onPrevious,
    required this.onNext,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(strings.dashboardPeriodLabel, style: Theme.of(context).textTheme.labelLarge),
        const SizedBox(width: 12),
        IconButton(
          tooltip: strings.dashboardPreviousPeriod,
          icon: const Icon(Icons.chevron_left),
          onPressed: onPrevious,
        ),
        Text(periodo, style: Theme.of(context).textTheme.titleMedium),
        IconButton(
          tooltip: strings.dashboardNextPeriod,
          icon: const Icon(Icons.chevron_right),
          onPressed: onNext,
        ),
      ],
    );
  }
}

/// I tre stati espliciti di un dato aggregato: caricamento, errore di
/// rete/BFF, o risultato (che a sua volta può essere `disponibile=true` con
/// valore, o `disponibile=false` — "dato insufficiente", MAI uno zero
/// fabbricato). Questo widget rende i primi due stati; l'ultimo è delegato
/// al chiamante perché la sua forma dipende dal tipo di dato (index vs
/// cella di flusso).
class _LoadingOrError extends StatelessWidget {
  final bool caricando;
  final String? errore;
  final String loadingLabel;
  final String errorLabel;
  final VoidCallback onRetry;
  final AppStrings strings;

  const _LoadingOrError({
    required this.caricando,
    required this.errore,
    required this.loadingLabel,
    required this.errorLabel,
    required this.onRetry,
    required this.strings,
  });

  @override
  Widget build(BuildContext context) {
    if (caricando) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 24),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(),
              const SizedBox(height: 12),
              Text(loadingLabel),
            ],
          ),
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Card(
        color: Theme.of(context).colorScheme.errorContainer,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.wifi_off, color: Theme.of(context).colorScheme.onErrorContainer),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      errorLabel,
                      style: TextStyle(color: Theme.of(context).colorScheme.onErrorContainer),
                    ),
                  ),
                ],
              ),
              if (errore != null) ...[
                const SizedBox(height: 4),
                Text(
                  errore!,
                  style: Theme.of(context)
                      .textTheme
                      .bodySmall
                      ?.copyWith(color: Theme.of(context).colorScheme.onErrorContainer),
                ),
              ],
              const SizedBox(height: 12),
              FilledButton(onPressed: onRetry, child: Text(strings.retry)),
            ],
          ),
        ),
      ),
    );
  }
}

/// Badge esplicito per un dato soppresso dalla soglia k=10 (privacy by
/// design): MAI uno zero, MAI un errore, MAI omesso in silenzio.
class _UnavailableBadge extends StatelessWidget {
  final String label;

  const _UnavailableBadge({required this.label});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Chip(
      avatar: Icon(Icons.shield_outlined, size: 18, color: scheme.onSecondaryContainer),
      label: Text(label),
      backgroundColor: scheme.secondaryContainer,
      labelStyle: TextStyle(color: scheme.onSecondaryContainer),
    );
  }
}

class _IndexSection extends StatelessWidget {
  final AppStrings strings;
  final DashboardAudience audience;
  final bool caricando;
  final String? errore;
  final DashboardIndexResponse? risposta;
  final VoidCallback onRetry;

  const _IndexSection({
    required this.strings,
    required this.audience,
    required this.caricando,
    required this.errore,
    required this.risposta,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    if (caricando || errore != null) {
      return _LoadingOrError(
        caricando: caricando,
        errore: errore,
        loadingLabel: strings.dashboardLoadingIndex,
        errorLabel: strings.dashboardErrorIndex,
        onRetry: onRetry,
        strings: strings,
      );
    }

    final dati = risposta;
    if (dati == null) return const SizedBox.shrink();

    // `disponibile=false`: stato esplicito "dato insufficiente" per l'INTERO
    // periodo, mai un cruscotto con valori a zero/finti (CLAUDE.md).
    if (!dati.disponibile) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.shield_outlined, color: Theme.of(context).colorScheme.secondary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      strings.dashboardIndexUnavailableTitle,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(dati.motivoIndisponibilita ?? strings.dashboardIndexUnavailableFallback),
            ],
          ),
        ),
      );
    }

    final index = dati.index!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(strings.dashboardIndexSectionTitle, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        // "L'indicatore che ci giudica" (CLAUDE.md): sempre ben visibile,
        // MAI relegato in un angolo, in ENTRAMBE le viste.
        _HeroIndicatorCard(strings: strings, index: index),
        const SizedBox(height: 16),
        if (audience.isOperatore)
          _IndicatorCard(
            icon: Icons.storefront_outlined,
            label: strings.indicatorAttivazioneLocaleLabel,
            value: _pct(index.attivazioneLocale),
          )
        else
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            childAspectRatio: 2.4,
            crossAxisSpacing: 8,
            mainAxisSpacing: 8,
            children: [
              _IndicatorCard(
                icon: Icons.timer_outlined,
                label: strings.indicatorTempoMedioLabel,
                value: '${index.tempoMedioEsperienzaMin.round()} min',
              ),
              _IndicatorCard(
                icon: Icons.favorite_border,
                label: strings.indicatorCoinvolgimentoLabel,
                value: _pct(index.coinvolgimento),
              ),
              _IndicatorCard(
                icon: Icons.star_outline,
                label: strings.indicatorSoddisfazioneLabel,
                value: index.soddisfazione == null
                    ? null
                    : index.soddisfazione!.toStringAsFixed(1),
                unavailableLabel: strings.indicatorSoddisfazioneUnavailable,
              ),
              _IndicatorCard(
                icon: Icons.replay_outlined,
                label: strings.indicatorTassoRitornoLabel,
                value: _pct(index.tassoRitorno),
              ),
              _IndicatorCard(
                icon: Icons.explore_outlined,
                label: strings.indicatorNuoviPercorsiLabel,
                value: _pct(index.nuoviPercorsi),
              ),
              _IndicatorCard(
                icon: Icons.storefront_outlined,
                label: strings.indicatorAttivazioneLocaleLabel,
                value: _pct(index.attivazioneLocale),
              ),
              _IndicatorCard(
                icon: Icons.auto_stories_outlined,
                label: strings.indicatorContributiMemoriaLabel,
                value: '${index.contributiMemoria}',
              ),
            ],
          ),
      ],
    );
  }

  String _pct(double v) => '${(v * 100).round()}%';
}

class _HeroIndicatorCard extends StatelessWidget {
  final AppStrings strings;
  final UrbanIntelligenceIndex index;

  const _HeroIndicatorCard({required this.strings, required this.index});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final valore = (index.distribuzioneFlussi * 100).round();
    return Card(
      color: scheme.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          children: [
            Icon(Icons.pie_chart_outline, size: 40, color: scheme.onPrimaryContainer),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    strings.dashboardHeroLabel,
                    style: Theme.of(context)
                        .textTheme
                        .titleMedium
                        ?.copyWith(color: scheme.onPrimaryContainer, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    strings.dashboardHeroDescription,
                    style: Theme.of(context)
                        .textTheme
                        .bodySmall
                        ?.copyWith(color: scheme.onPrimaryContainer),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            Text(
              '$valore%',
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    color: scheme.onPrimaryContainer,
                    fontWeight: FontWeight.bold,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class _IndicatorCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? value; // null quando il valore non esiste (es. soddisfazione)
  final String? unavailableLabel;

  const _IndicatorCard({
    required this.icon,
    required this.label,
    required this.value,
    this.unavailableLabel,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Icon(icon, color: scheme.primary),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    label,
                    style: Theme.of(context).textTheme.labelMedium,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  // `value == null` è un buco dati legittimo e dichiarato
                  // (`soddisfazione`: "nessuna fonte dati reale oggi"), da
                  // NON confondere con la soppressione k=10: testo diverso,
                  // mai uno "0" fabbricato.
                  if (value != null)
                    Text(
                      value!,
                      style: Theme.of(context)
                          .textTheme
                          .titleLarge
                          ?.copyWith(fontWeight: FontWeight.bold),
                    )
                  else
                    Text(
                      unavailableLabel ?? '—',
                      style: Theme.of(context)
                          .textTheme
                          .bodySmall
                          ?.copyWith(color: scheme.outline),
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

class _FlowsSection extends StatelessWidget {
  final AppStrings strings;
  final DateTime? filtroGiorno;
  final int? filtroOra;
  final bool caricando;
  final String? errore;
  final DashboardFlowsResponse? risposta;
  final VoidCallback onRetry;
  final VoidCallback onScegliGiorno;
  final ValueChanged<int?> onCambiaOra;
  final VoidCallback onRimuoviFiltri;

  const _FlowsSection({
    required this.strings,
    required this.filtroGiorno,
    required this.filtroOra,
    required this.caricando,
    required this.errore,
    required this.risposta,
    required this.onRetry,
    required this.onScegliGiorno,
    required this.onCambiaOra,
    required this.onRimuoviFiltri,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(strings.dashboardFlowsTitle, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            OutlinedButton.icon(
              onPressed: onScegliGiorno,
              icon: const Icon(Icons.calendar_today_outlined, size: 18),
              label: Text(
                filtroGiorno == null
                    ? strings.dashboardFlowsAnyDay
                    : formatDateYmd(filtroGiorno!),
              ),
            ),
            DropdownButton<int?>(
              value: filtroOra,
              hint: Text(strings.dashboardFlowsAnyHour),
              items: [
                DropdownMenuItem<int?>(value: null, child: Text(strings.dashboardFlowsAnyHour)),
                for (var h = 0; h < 24; h++)
                  DropdownMenuItem<int?>(value: h, child: Text('${h.toString().padLeft(2, '0')}:00')),
              ],
              onChanged: onCambiaOra,
            ),
            if (filtroGiorno != null || filtroOra != null)
              TextButton.icon(
                onPressed: onRimuoviFiltri,
                icon: const Icon(Icons.clear, size: 18),
                label: Text(strings.dashboardFlowsClearFilters),
              ),
          ],
        ),
        const SizedBox(height: 12),
        if (caricando || errore != null)
          _LoadingOrError(
            caricando: caricando,
            errore: errore,
            loadingLabel: strings.dashboardLoadingFlows,
            errorLabel: strings.dashboardErrorFlows,
            onRetry: onRetry,
            strings: strings,
          )
        else
          _FlowsList(strings: strings, risposta: risposta),
      ],
    );
  }
}

class _FlowsList extends StatelessWidget {
  final AppStrings strings;
  final DashboardFlowsResponse? risposta;

  const _FlowsList({required this.strings, required this.risposta});

  @override
  Widget build(BuildContext context) {
    final celle = risposta?.celle ?? const <FlowCell>[];
    if (celle.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 16),
        child: Text(strings.dashboardFlowsEmpty),
      );
    }
    return Column(
      children: celle.map((cella) => _FlowCellTile(strings: strings, cella: cella)).toList(),
    );
  }
}

class _FlowCellTile extends StatelessWidget {
  final AppStrings strings;
  final FlowCell cella;

  const _FlowCellTile({required this.strings, required this.cella});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      child: ListTile(
        leading: const Icon(Icons.place_outlined),
        title: Text(cella.placeId),
        // Cella soppressa (< k=10 person_id distinti): badge esplicito, MAI
        // uno "0" indistinguibile da un luogo davvero vuoto.
        trailing: cella.disponibile
            ? Text(
                '${cella.conteggioTappe}',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
              )
            : _UnavailableBadge(label: strings.dashboardCellUnavailableBadge),
      ),
    );
  }
}
