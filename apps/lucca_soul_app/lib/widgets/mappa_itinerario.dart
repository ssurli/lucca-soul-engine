import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../models/itinerary.dart';
import '../theme/app_theme.dart';
import '../theme/tokens.dart';
import '../util/app_strings.dart' show kUserAgentPackage;
import '../util/mappa_tappe.dart';

/// Strato OpenStreetMap. Regola d'uso di tile.openstreetmap.org: attribuzione
/// sempre visibile, User-Agent identificativo, nessun prefetch/download in
/// blocco/uso offline, cache secondo gli header HTTP.
const String kUrlTileOsm = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const String kAttribuzioneOsm = '© OpenStreetMap contributors';

/// Altezza della mappa nella schermata dell'itinerario.
const double kAltezzaMappa = 220;

/// Mappa in alto nella schermata dell'itinerario: un segnaposto numerato per
/// ogni tappa con punto (stessa numerazione delle card) e una linea DRITTA tra
/// i segnaposto consecutivi. La linea indica l'ORDINE delle tappe, non il
/// percorso a piedi. Se tra due tappe con punto ce n'è una senza punto, la
/// linea le collega comunque (2→4): indica la successione sulla mappa.
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

  const MappaItinerario({
    super.key,
    required this.tappe,
    this.tileProvider,
    this.controller,
    this.etichettaTappa = 'Tappa',
  });

  @override
  State<MappaItinerario> createState() => _MappaItinerarioState();
}

class _MappaItinerarioState extends State<MappaItinerario> {
  late final MapController _controller = widget.controller ?? MapController();
  bool _pronta = false;

  static CameraFit _inquadra(List<LatLng> punti) => CameraFit.bounds(
        bounds: LatLngBounds.fromPoints(punti),
        padding: const EdgeInsets.all(40),
        maxZoom: 16, // un solo punto: zoom da quartiere, non da portone
      );

  @override
  void didUpdateWidget(MappaItinerario old) {
    super.didUpdateWidget(old);
    // Dopo un adattamento tappe e numeri cambiano: si reinquadra.
    final nuovi = segnapostiMappa(widget.tappe);
    final vecchi = segnapostiMappa(old.tappe);
    if (_pronta && nuovi.isNotEmpty && !_uguali(nuovi, vecchi)) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _controller.fitCamera(_inquadra([for (final s in nuovi) s.punto]));
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
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(Tk.raggio),
        child: DecoratedBox(
          decoration: BoxDecoration(border: Border.all(color: Tk.cardBordo), borderRadius: BorderRadius.circular(Tk.raggio)),
          child: SizedBox(
            height: kAltezzaMappa,
            child: FlutterMap(
              mapController: _controller,
              options: MapOptions(
                backgroundColor: Tk.avviso,
                initialCameraFit: _inquadra(punti),
                onMapReady: () => _pronta = true,
                interactionOptions: const InteractionOptions(
                  flags: InteractiveFlag.pinchZoom | InteractiveFlag.doubleTapZoom,
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
                    polylines: [Polyline(points: punti, strokeWidth: 3, color: Tk.accento)],
                  ),
                MarkerLayer(
                  markers: [
                    for (final s in segnaposti)
                      Marker(
                        point: s.punto,
                        width: 32,
                        height: 32,
                        child: Segnaposto(numero: s.numero, etichetta: widget.etichettaTappa),
                      ),
                  ],
                ),
                const _Attribuzione(),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Segnaposto numerato: cerchio mattone, numero bianco (contrasto 5,9). Il
/// numero è disegnato (non è un `Text`) così non si confonde con quello della
/// card nelle ricerche per testo; per l'accessibilità porta l'etichetta
/// "Tappa N".
class Segnaposto extends StatelessWidget {
  final int numero;
  final String etichetta;
  const Segnaposto({super.key, required this.numero, this.etichetta = 'Tappa'});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: '$etichetta $numero',
      excludeSemantics: true,
      child: CustomPaint(painter: _SegnapostoPainter(numero)),
    );
  }
}

class _SegnapostoPainter extends CustomPainter {
  final int numero;
  _SegnapostoPainter(this.numero);

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final r = size.shortestSide / 2;
    canvas.drawCircle(c, r, Paint()..color = Tk.cardSfondo);
    canvas.drawCircle(c, r - 2, Paint()..color = Tk.accento);
    final tp = TextPainter(
      text: TextSpan(text: '$numero', style: stileTesto(14, 800, Tk.testoSuAccento)),
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
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        child: Text(kAttribuzioneOsm, style: stileTesto(12, 600, Tk.testo)),
      ),
    );
  }
}
