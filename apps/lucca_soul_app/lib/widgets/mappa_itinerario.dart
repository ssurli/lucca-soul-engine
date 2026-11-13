import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../models/itinerary.dart';
import '../theme/app_theme.dart';
import '../theme/tokens.dart';
import '../util/app_strings.dart' show kUserAgentPackage;
import '../util/mappa_tappe.dart';
import '../util/segnaposti_separati.dart';
import 'segnaposto_mura.dart';

/// Strato OpenStreetMap. Regola d'uso di tile.openstreetmap.org: attribuzione
/// sempre visibile, User-Agent identificativo, nessun prefetch/download in
/// blocco/uso offline, cache secondo gli header HTTP.
const String kUrlTileOsm = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const String kAttribuzioneOsm = '© OpenStreetMap contributors';

/// Altezza della mappa nella schermata dell'itinerario.
const double kAltezzaMappa = 168;

const double _kPaddingVerticaleAttribuzione = 2;

/// Stile della scritta di attribuzione (unico: lo usano il widget e la misura).
TextStyle _stileAttribuzione() => stileTesto(12, 600, Tk.testo);

/// Riquadro di tocco del segnaposto e punto del riquadro che cade sul luogo:
/// con la sagoma, riquadro e punta; senza (cerchio di riserva), il riquadro
/// minimo con il punto al centro. Unica fonte per i limiti del clamp e per i
/// padding dell'inquadratura.
({Size dim, Offset ancora}) ingombroSegnaposto(SagomaSegnaposto? sg) {
  if (sg == null) {
    const d = Size.square(Tk.areaMinima);
    return (dim: d, ancora: Offset(d.width / 2, d.height / 2));
  }
  return (
    dim: sg.dimensioneRiquadro(kLarghezzaSegnaposto),
    ancora: sg.puntaNelRiquadro(kLarghezzaSegnaposto),
  );
}

/// Altezza MISURATA dell'attribuzione in basso a destra (una riga con lo stesso
/// stile, piu' il padding verticale). La usano sia `_Attribuzione` sia il limite
/// in basso dei segnaposti, che non devono coprirla.
double altezzaAttribuzione() {
  final tp = TextPainter(
    text: TextSpan(text: kAttribuzioneOsm, style: _stileAttribuzione()),
    textDirection: TextDirection.ltr,
  )..layout();
  return tp.height + 2 * _kPaddingVerticaleAttribuzione;
}

/// Mappa in alto nella schermata dell'itinerario: un segnaposto numerato per
/// ogni tappa con punto (stessa numerazione delle card) e una linea DRITTA tra
/// i segnaposto consecutivi. La linea indica l'ORDINE delle tappe, non il
/// percorso a piedi. Se tra due tappe con punto ce n'è una senza punto, la
/// linea le collega comunque (2→4): indica la successione sulla mappa.
///
/// I segnaposti hanno la sagoma delle Mura (`assets/brand/segnaposto_sagoma.json`):
/// la PUNTA della sagoma cade sul luogo vero. Se la sagoma non si carica
/// (asset mancante o JSON malformato) restano i cerchi numerati, senza errori.
///
/// Senza nessun punto non c'è mappa (nessun riquadro vuoto da spiegare).
/// Se gli strati non si caricano (rete assente) restano segnaposto e linee su
/// sfondo neutro. Niente prefetch: `panBuffer: 0`; il trascinamento è spento
/// (la mappa sta dentro una lista che scorre), restano pizzico e doppio tocco.
class MappaItinerario extends StatefulWidget {
  final List<ItineraryStop> tappe;

  /// Iniettabile nei test (nessuna rete). Default: rete con cache HTTP.
  final TileProvider? tileProvider;

  /// Iniettabile nei test per leggere l'inquadratura.
  final MapController? controller;

  /// Etichetta accessibile dei segnaposto ("Tappa" nella lingua dell'app).
  final String etichettaTappa;

  /// Riga sotto la mappa: la linea indica l'ordine, non il percorso.
  final String dicitura;

  /// Tocco su un segnaposto: riceve il numero della tappa (1-based).
  final ValueChanged<int>? onSegnaposto;

  /// Iniettabile nei test: la sagoma dei segnaposti. Un future che completa con
  /// `null` (o con errore) simula l'asset mancante e lascia il cerchio; uno che
  /// completa con una [SagomaSegnaposto] simula l'asset presente. Default:
  /// [caricaSagomaSegnaposto] (asset del bundle, Future in cache). Finché il
  /// future non completa si disegna il cerchio di riserva.
  final Future<SagomaSegnaposto?>? sagoma;

  const MappaItinerario({
    super.key,
    required this.tappe,
    this.tileProvider,
    this.controller,
    this.etichettaTappa = 'Tappa',
    this.dicitura =
        "Tocca un numero per aprire la tappa. La linea indica l'ordine, non il percorso.",
    this.onSegnaposto,
    this.sagoma,
  });

  @override
  State<MappaItinerario> createState() => _MappaItinerarioState();
}

class _MappaItinerarioState extends State<MappaItinerario> {
  late final MapController _controller = widget.controller ?? MapController();
  bool _pronta = false;
  SagomaSegnaposto? _sg; // null: attesa, errore o asset mancante -> cerchio
  Object? _richiesta; // scarta le risposte di un future ormai sostituito
  bool _risolta = false; // la mappa si costruisce a sagoma nota (o assente)

  @override
  void initState() {
    super.initState();
    _risolvi();
  }

  void _risolvi() {
    final richiesta = _richiesta = Object();
    (widget.sagoma ?? caricaSagomaSegnaposto()).then<SagomaSegnaposto?>(
        (v) => v, onError: (Object _) => null,).then((v) {
      if (!mounted || richiesta != _richiesta) return;
      setState(() {
        _sg = v;
        _risolta = true;
      });
    });
  }

  /// Margine tra il riquadro della sagoma e il bordo della mappa (px).
  static const double _margineSagoma = 4;

  /// Padding per lato: mai meno di 40 px e mai meno di quanto serve al riquadro
  /// di tocco attorno alla punta ([ingombroSegnaposto], la stessa fonte dei
  /// limiti del clamp) piu' [_margineSagoma]; in basso si aggiunge l'altezza
  /// dell'attribuzione. Cosi' nella vista iniziale, senza separazione, il clamp
  /// non interviene mai e la punta cade sul luogo, con la sagoma e col cerchio.
  /// Il padding verticale resta ben dentro [kAltezzaMappa].
  CameraFit _inquadra(List<LatLng> punti) {
    const base = 40.0;
    final (:dim, :ancora) = ingombroSegnaposto(_sg);
    final sinistra = ancora.dx + _margineSagoma;
    final alto = ancora.dy + _margineSagoma;
    final destra = dim.width - ancora.dx + _margineSagoma;
    final basso =
        dim.height - ancora.dy + altezzaAttribuzione() + _margineSagoma;
    return CameraFit.bounds(
        bounds: LatLngBounds.fromPoints(punti),
        padding: EdgeInsets.fromLTRB(math.max(base, sinistra),
            math.max(base, alto), math.max(base, destra), math.max(base, basso),),
        maxZoom: 16, // un solo punto: zoom da quartiere, non da portone
      );
  }

  @override
  void didUpdateWidget(MappaItinerario old) {
    super.didUpdateWidget(old);
    if (widget.sagoma != old.sagoma) {
      _risolta = false;
      _risolvi();
    }
    // Dopo un adattamento tappe e numeri cambiano: si reinquadra.
    final nuovi = segnapostiMappa(widget.tappe);
    final vecchi = segnapostiMappa(old.tappe);
    if (_pronta && nuovi.isNotEmpty && !_uguali(nuovi, vecchi)) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _controller.fitCamera(_inquadra([for (final s in nuovi) s.punto]));
        }
      });
    }
  }

  static bool _uguali(List<SegnapostoMappa> a, List<SegnapostoMappa> b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i].numero != b[i].numero || a[i].punto != b[i].punto) return false;
    }
    return true;
  }

  @override
  void dispose() {
    if (widget.controller == null) _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final segnaposti = segnapostiMappa(widget.tappe);
    if (segnaposti.isEmpty) return const SizedBox.shrink();
    final punti = [for (final s in segnaposti) s.punto];
    if (!_risolta) {
      // Sagoma in arrivo: il riquadro c'è già, la mappa parte subito con
      // l'inquadratura giusta (niente reinquadratura, niente tile sprecati).
      return Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: kAltezzaMappa),
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(widget.dicitura,
                  style: stileTesto(12, 700, Tk.testoSecondario),),
            ),
          ],
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(Tk.raggio),
            child: DecoratedBox(
              decoration: BoxDecoration(
                  border: Border.all(color: Tk.cardBordo),
                  borderRadius: BorderRadius.circular(Tk.raggio),),
              child: SizedBox(
                height: kAltezzaMappa,
                child: FlutterMap(
                  mapController: _controller,
                  options: MapOptions(
                    backgroundColor: Tk.avviso,
                    initialCameraFit: _inquadra(punti),
                    onMapReady: () {
                      _pronta = true;
                    },
                    interactionOptions: const InteractionOptions(
                      flags: InteractiveFlag.pinchZoom |
                          InteractiveFlag.doubleTapZoom,
                    ),
                  ),
                  children: [
                    TileLayer(
                      urlTemplate: kUrlTileOsm,
                      userAgentPackageName: kUserAgentPackage,
                      tileProvider: widget.tileProvider,
                      panBuffer: 0,
                      // Rete assente o tile rifiutata: nessuna eccezione, la
                      // mappa resta su sfondo neutro.
                      errorTileCallback: (tile, error, stackTrace) {},
                    ),
                    if (punti.length > 1)
                      PolylineLayer(
                        polylines: [
                          Polyline(
                            points: punti,
                            strokeWidth: 3,
                            color: Tk.accento,
                            pattern: const StrokePattern.dotted(),
                          ),
                        ],
                      ),
                    _StratoSegnaposti(
                      segnaposti: segnaposti,
                      etichetta: widget.etichettaTappa,
                      onSegnaposto: widget.onSegnaposto,
                      sagoma: _sg, // attesa o errore: cerchio di riserva
                    ),
                    const _Attribuzione(),
                  ],
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(widget.dicitura,
                style: stileTesto(12, 700, Tk.testoSecondario),),
          ),
        ],
      ),
    );
  }
}

/// Strato dei segnaposti. Posizione sullo schermo dalla camera CORRENTE
/// (si ricalcola a ogni pizzico). I punti veri vengono scostati in pixel di
/// schermo ([separaSegnaposti]) perché numeri e tocchi restino distinti; la
/// linea della mappa usa sempre i punti veri.
///
/// Con [sagoma]: la punta ancorata al punto (eventualmente scostato), distanza
/// minima [kLarghezzaSegnaposto] tra le punte, e sotto i segnaposti una linea
/// di richiamo dalla punta scostata al luogo vero (solo se lo scostamento
/// supera 2 px). Senza sagoma (cerchio di riserva): centrato sul punto,
/// distanza [kDiametroSegnaposto], nessuna linea di richiamo.
class _StratoSegnaposti extends StatelessWidget {
  final List<SegnapostoMappa> segnaposti;
  final String etichetta;
  final ValueChanged<int>? onSegnaposto;
  final SagomaSegnaposto? sagoma;
  const _StratoSegnaposti({
    required this.segnaposti,
    required this.etichetta,
    required this.onSegnaposto,
    this.sagoma,
  });

  @override
  Widget build(BuildContext context) {
    final camera = MapCamera.of(context);
    final veri = [
      for (final s in segnaposti) camera.latLngToScreenOffset(s.punto),
    ];
    final sg = sagoma;
    // Dove sta, dentro il riquadro di tocco, il punto che deve cadere sul luogo.
    final (:dim, :ancora) = ingombroSegnaposto(sg);
    // Limiti della PUNTA perché l'intero riquadro di tocco (e quindi la sagoma)
    // resti dentro la mappa e sopra l'attribuzione. Il vincolo in basso vale
    // su tutta la larghezza (non solo dove sta il testo): non dipende dalla
    // larghezza del testo e resta un rettangolo, quindi il clamp e' semplice.
    final lato = camera.size;
    final limiti = Rect.fromLTRB(
      ancora.dx,
      ancora.dy,
      lato.width - (dim.width - ancora.dx),
      lato.height - altezzaAttribuzione() - (dim.height - ancora.dy),
    );
    final punte = sg == null
        ? separaSegnaposti(veri, limiti: limiti)
        : separaSegnaposti(veri,
            diametro: diametroCollisione(kLarghezzaSegnaposto),
            limiti: limiti,);
    return SizedBox.expand(
      child: Stack(
        children: [
          if (sg != null)
            Positioned.fill(
              child: IgnorePointer(
                child: CustomPaint(painter: GuidePainter(veri, punte)),
              ),
            ),
          for (var i = 0; i < segnaposti.length; i++)
            Positioned(
              key: ValueKey('segnaposto-${segnaposti[i].numero}'),
              left: punte[i].dx - ancora.dx,
              top: punte[i].dy - ancora.dy,
              width: dim.width,
              height: dim.height,
              child: Segnaposto(
                numero: segnaposti[i].numero,
                etichetta: etichetta,
                sagoma: sg,
                onTap: onSegnaposto == null
                    ? null
                    : () => onSegnaposto!(segnaposti[i].numero),
              ),
            ),
        ],
      ),
    );
  }
}

/// Segnaposto numerato. Con [sagoma]: la sagoma delle Mura piena (accento),
/// larga [kLarghezzaSegnaposto] e alta quanto la viewBox, centrata in un
/// riquadro di tocco di almeno 44x44. Senza sagoma (riserva): cerchio mattone di
/// 32 px dentro un'area di tocco 44x44. In entrambi i casi il numero è bianco
/// (contrasto 5,9) e DISEGNATO (non è un `Text`) così non si confonde con quello
/// della card nelle ricerche per testo; per l'accessibilità porta l'etichetta
/// "Tappa N".
class Segnaposto extends StatelessWidget {
  final int numero;
  final String etichetta;
  final VoidCallback? onTap;
  final SagomaSegnaposto? sagoma;
  const Segnaposto({
    super.key,
    required this.numero,
    this.etichetta = 'Tappa',
    this.onTap,
    this.sagoma,
  });

  @override
  Widget build(BuildContext context) {
    final sg = sagoma;
    final Size dim = sg == null
        ? const Size.square(Tk.areaMinima)
        : sg.dimensioneRiquadro(kLarghezzaSegnaposto);
    return Semantics(
      label: '$etichetta $numero',
      button: true,
      onTap: onTap,
      excludeSemantics: true,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onTap,
        child: SizedBox(
          width: dim.width,
          height: dim.height,
          child: sg == null
              ? CustomPaint(painter: _SegnapostoPainter(numero))
              : Center(
                  child: CustomPaint(
                    size: sg.dimensione(kLarghezzaSegnaposto),
                    painter: SagomaPainter(sg, numero),
                  ),
                ),
        ),
      ),
    );
  }
}

class _SegnapostoPainter extends CustomPainter {
  final int numero;
  _SegnapostoPainter(this.numero);

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    const r = 16.0; // cerchio di 32 px dentro l'area di tocco di 44
    canvas.drawCircle(c, r, Paint()..color = Tk.cardSfondo);
    canvas.drawCircle(c, r - 2, Paint()..color = Tk.accento);
    final tp = TextPainter(
      text: TextSpan(
          text: '$numero', style: stileTesto(14, 800, Tk.testoSuAccento),),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, c - Offset(tp.width / 2, tp.height / 2));
  }

  @override
  bool shouldRepaint(_SegnapostoPainter old) => old.numero != numero;
}

/// Attribuzione SEMPRE visibile (non un'icona da espandere).
class _Attribuzione extends StatelessWidget {
  const _Attribuzione();

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.bottomRight,
      child: Container(
        color: Tk.cardSfondo.withValues(alpha: 0.9),
        padding: const EdgeInsets.symmetric(
            horizontal: 6, vertical: _kPaddingVerticaleAttribuzione,),
        child: Text(kAttribuzioneOsm, style: _stileAttribuzione()),
      ),
    );
  }
}
