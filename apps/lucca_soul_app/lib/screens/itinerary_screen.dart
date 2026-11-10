import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
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
import '../util/foto_tappa.dart';
import '../util/excluded_stop_line.dart';
import '../util/itinerary_diff.dart';
import '../util/interruttori_controller.dart';
import '../util/known_places.dart';
import '../util/minuti_a_piedi.dart';
import '../util/signal_presets.dart';
import '../widgets/adaptive_card.dart';
import '../widgets/colonna_centrata.dart';
import '../widgets/foto_tappa_widget.dart';
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

  /// Solo test: foto delle tappe iniettate. Default: dal bundle dell'app.
  final ArchivioFoto? archivioFoto;

  const ItineraryScreen({
    this.tileProvider,
    this.archivioFoto,
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

  /// Unico proprietario di interruttori e itinerario mostrato (l'originale di
  /// `POST /itinerary` o l'ultimo adattamento). Nuovo a ogni caricamento, cosi'
  /// il refresh azzera insieme interruttori e itinerario.
  InterruttoriController? _controller;
  ArchivioFoto _foto = const ArchivioFoto();
  bool _caricando = true;
  String? _errore;

  /// Indici (0-based) delle tappe aperte: unico stato aperto/chiuso, cosi'
  /// anche dall'esterno (es. tocco sulla mappa) si apre una tappa per indice.
  final Set<int> _aperte = {};

  /// Una GlobalKey per tappa (per indice), per scorrere la lista alla tappa.
  final List<GlobalKey> _chiavi = [];
  Itinerary? _ultimoMostrato;

  GlobalKey _chiave(int i) {
    while (_chiavi.length <= i) {
      _chiavi.add(GlobalKey());
    }
    return _chiavi[i];
  }

  final ScrollController _scroll = ScrollController();

  /// Tocco su un segnaposto: apre la tappa [numero] (1-based) e ci scorre.
  /// Se la tappa e' fuori dalla cache della lista la sua chiave non ha
  /// contesto: si scorre a gradini verso di essa finche' non viene costruita.
  void _apriDaMappa(int numero) {
    final i = numero - 1;
    if (i < 0) return;
    setState(() => _aperte.add(i));
    _scorriA(i);
  }

  Future<void> _scorriA(int i) async {
    for (var tentativo = 0; tentativo < 60; tentativo++) {
      await WidgetsBinding.instance.endOfFrame;
      if (!mounted) return;
      final ctx = _chiave(i).currentContext;
      if (ctx != null && ctx.mounted) {
        await Scrollable.ensureVisible(ctx,
            duration: const Duration(milliseconds: 250), curve: Curves.easeOut,);
        return;
      }
      if (!_scroll.hasClients) return;
      // Verso: se una tappa costruita ha indice minore di i si scende, altrimenti si sale.
      var giu = true;
      for (var j = _chiavi.length - 1; j >= 0; j--) {
        if (_chiavi[j].currentContext != null) {
          giu = j < i;
          break;
        }
      }
      final pos = _scroll.position;
      final passo = pos.viewportDimension * 0.8;
      final target = (pos.pixels + (giu ? passo : -passo))
          .clamp(pos.minScrollExtent, pos.maxScrollExtent);
      if (target == pos.pixels) return;
      _scroll.jumpTo(target);
    }
  }

  void _toggleTappa(int i) => setState(() {
        if (!_aperte.remove(i)) _aperte.add(i);
      });

  @override
  void initState() {
    super.initState();
    _strings = AppStrings.forLanguages(widget.profile.lingue);
    _caricaItinerario();
    _caricaFoto();
  }

  Future<void> _caricaFoto() async {
    final archivio = widget.archivioFoto ?? await ArchivioFoto.dalBundle(rootBundle);
    if (mounted) setState(() => _foto = archivio);
  }

  @override
  void dispose() {
    _controller?.dispose();
    _scroll.dispose();
    super.dispose();
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
      if (!mounted) return;
      final precedente = _controller;
      setState(() {
        _controller = InterruttoriController(
          bffClient: widget.bffClient,
          originale: itinerario,
          profilo: widget.profile,
        );
      });
      precedente?.dispose(); // le sue risposte in volo non contano piu'

    } on BffException catch (error) {
      setState(() => _errore = error.message);
    } finally {
      if (mounted) setState(() => _caricando = false);
    }
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

    final controller = _controller;
    if (controller == null || controller.originale.stops.isEmpty) {
      return Center(child: Text(_strings.emptyStops));
    }

    // L'itinerario mostrato deriva dallo stato del controller: si ricostruisce a ogni suo cambio.
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) => _buildItinerario(context, controller),
    );
  }

  Widget _buildItinerario(
      BuildContext context, InterruttoriController controller,) {
    final itinerario = controller.itinerarioMostrato;
    // Itinerario riscritto (o ricaricato): tutte le tappe tornano chiuse.
    if (!identical(itinerario, _ultimoMostrato)) {
      _ultimoMostrato = itinerario;
      _aperte.clear();
    }
    return Column(
      children: [
        TestataGiornata(
            itinerario: itinerario, data: _segnale.data ?? Orologio.adesso().toLocal(), strings: _strings, demo: demoAttivoDefine,),
        Expanded(
          child: ColonnaCentrata(
            child: RefreshIndicator(
              onRefresh: _caricaItinerario,
              child: ListView(
                controller: _scroll,
                padding: const EdgeInsets.only(bottom: 24),
                children: [
                  MappaItinerario(
                    tappe: itinerario.stops,
                    tileProvider: widget.tileProvider,
                    etichettaTappa: _strings.genericStop,
                    dicitura: _strings.mapCaption,
                    onSegnaposto: _apriDaMappa,
                  ),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                    child: Text(_strings.itineraryTitle,
                        style: Theme.of(context).textTheme.headlineSmall,),
                  ),
                  AdaptiveCard(controller: controller, strings: _strings),
                  const SizedBox(height: 8),
                  for (var i = 0; i < itinerario.stops.length; i++)
                    StopCard(
                      key: _chiave(i),
                      aperta: _aperte.contains(i),
                      onToggle: () => _toggleTappa(i),
                      conLinea: i < itinerario.stops.length - 1,
                      minutiAllaProssima: i < itinerario.stops.length - 1
                          ? minutiAPiedi(
                              itinerario.stops[i], itinerario.stops[i + 1],)
                          : null,
                      stop: itinerario.stops[i],
                      evidenziata: tappaSostituita(itinerario.stops[i]),
                      mantenutaSenzaAlternativa:
                          tappaMantenutaSenzaAlternativa(itinerario.stops[i]),
                      strings: _strings,
                      numero: i + 1,
                      foto: _foto.per(itinerario.stops[i].experienceId),
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

/// Una tappa come riga chiusa (numero, ora e durata, titolo, esito, freccia);
/// un tocco su tutta la riga la apre e mostra foto, motivo, curiosita', link e
/// ricordo. Aperta/chiusa e' controllabile dall'esterno ([aperta] + [onToggle],
/// per indice dallo schermo); senza [onToggle] tiene lo stato da se'.
class StopCard extends StatefulWidget {
  final ItineraryStop stop;
  final bool evidenziata;

  /// La tappa resta in programma perché il motore non ha trovato alternative.
  final bool mantenutaSenzaAlternativa;
  final AppStrings strings;
  final VoidCallback onLasciaRicordo;

  /// Numero della tappa (1-based), nello stesso ordine della mappa. Null = senza cerchio.
  final int? numero;

  /// Foto della tappa, se esiste (file + voce nel json). Null = nessuna foto.
  final FotoTappa? foto;

  /// Stato aperto controllato dall'esterno. Null = stato interno (chiusa).
  final bool? aperta;
  final VoidCallback? onToggle;

  /// Minuti a piedi verso la tappa successiva (da [minutiAPiedi]). Null = nessuna riga.
  final int? minutiAllaProssima;

  /// Linea verticale verso il numero della tappa successiva.
  final bool conLinea;

  const StopCard({
    super.key,
    required this.stop,
    required this.evidenziata,
    this.mantenutaSenzaAlternativa = false,
    required this.strings,
    required this.onLasciaRicordo,
    this.numero,
    this.foto,
    this.aperta,
    this.onToggle,
    this.minutiAllaProssima,
    this.conLinea = false,
  });

  @override
  State<StopCard> createState() => _StopCardState();
}

class _StopCardState extends State<StopCard> {
  bool _interna = false;

  bool get _aperta => widget.aperta ?? _interna;

  void _tocco() {
    if (widget.onToggle != null) {
      widget.onToggle!();
    } else {
      setState(() => _interna = !_interna);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final strings = widget.strings;
    final stop = widget.stop;
    final etichetta = widget.evidenziata
        ? EtichettaEsito(
            testo: strings.changedStop,
            sfondo: Tk.sostituitaSfondo,
            colore: Tk.sostituitaTesto,)
        : widget.mantenutaSenzaAlternativa
            ? EtichettaEsito(
                testo: strings.keptNoAlternative,
                sfondo: Tk.mantenutaSfondo,
                colore: Tk.mantenutaTesto,)
            : null;
    final titolo = titoloTappa(stop.titolo, strings);
    final aperta = _aperta;
    const sinistra = 32.0 + 12.0; // cerchio + spazio: la colonna di destra
    final minuti = widget.minutiAllaProssima;
    final rientro = widget.numero != null ? sinistra : 0.0;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Stack(
        children: [
          if (widget.numero != null && widget.conLinea)
            const Positioned(
              left: 15,
              top: 32,
              bottom: 0,
              width: 2,
              child: ColoredBox(color: Tk.cardBordo),
            ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Semantics(
                container: true,
                button: true,
                expanded: aperta,
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: _tocco,
                    borderRadius: BorderRadius.circular(Tk.raggio),
                    child: ConstrainedBox(
                      constraints:
                          const BoxConstraints(minHeight: Tk.areaMinima),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (widget.numero != null) ...[
                            Container(
                              width: 32,
                              height: 32,
                              alignment: Alignment.center,
                              decoration: const BoxDecoration(
                                  color: Tk.accento, shape: BoxShape.circle,),
                              child: Text('${widget.numero}',
                                  style: stileTesto(15, 800, Tk.testoSuAccento),),
                            ),
                            const SizedBox(width: 12),
                          ],
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '${stop.arrivo.label} · ${stop.durataMin} ${strings.durationLabel}',
                                  style: stileTesto(14, 700, Tk.testoSecondario),
                                ),
                                const SizedBox(height: 2),
                                Text(titolo, style: theme.textTheme.titleMedium),
                                if (etichetta != null)
                                  Padding(
                                      padding: const EdgeInsets.only(top: 6),
                                      child: etichetta,),
                              ],
                            ),
                          ),
                          SizedBox(
                            width: Tk.areaMinima,
                            height: Tk.areaMinima,
                            child: AnimatedRotation(
                              turns: aperta ? 0.5 : 0,
                              duration: const Duration(milliseconds: 150),
                              child: const Icon(Icons.expand_more,
                                  color: Tk.testoSecondario,),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              if (aperta)
                Padding(
                  padding: EdgeInsets.only(left: rientro, top: 4, right: 4),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (widget.foto != null)
                        SezioneFoto(
                            foto: widget.foto!, titolo: titolo, strings: strings,),
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
                            onPressed: () => apriInNuovaScheda(
                                urlComeArrivo(stop.puntoArrivo)!,),
                            icon: const Icon(Icons.directions_walk, size: 18),
                            label: Text(strings.howToArrive),
                          ),
                        ),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: TextButton.icon(
                          onPressed: widget.onLasciaRicordo,
                          icon: const Icon(Icons.auto_stories_outlined,
                              size: 18,),
                          label: Text(strings.leaveMemoryAction),
                        ),
                      ),
                    ],
                  ),
                ),
              if (minuti != null)
                Padding(
                  padding: EdgeInsets.only(left: rientro, top: 6, bottom: 6),
                  child: Text(strings.minutesOnFoot(minuti),
                      style: stileTesto(13, 600, Tk.testoSecondario),),
                )
              else
                const SizedBox(height: 12),
            ],
          ),
        ],
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
