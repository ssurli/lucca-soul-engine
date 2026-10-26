import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../theme/tokens.dart';
import '../util/app_strings.dart';
import '../util/foto_tappa.dart';
import 'colonna_centrata.dart';

/// Miniatura 4:3 ritagliata nella card. La didascalia è il testo alternativo.
/// Toccandola si apre il dettaglio con la foto intera. Area >= 44 px.
class MiniaturaFoto extends StatelessWidget {
  final FotoTappa foto;
  final String titolo;
  final AppStrings strings;
  /// Chiamato (dopo il frame) se la foto non si decodifica.
  final VoidCallback? onErrore;
  const MiniaturaFoto({
    super.key,
    required this.foto,
    required this.titolo,
    required this.strings,
    this.onErrore,
  });

  static const double larghezza = 132;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      button: true,
      label: foto.didascalia,
      image: true,
      excludeSemantics: true,
      onTap: () => _apri(context),
      child: SizedBox(
        width: larghezza,
        child: AspectRatio(
          aspectRatio: 4 / 3,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(Tk.raggio),
            child: InkWell(
              onTap: () => _apri(context),
              child: Image(
                image: foto.immagine,
                fit: BoxFit.cover,
                // File illeggibile: si avvisa la sezione, che sparisce per intero.
                errorBuilder: (_, __, ___) {
                  WidgetsBinding.instance.addPostFrameCallback((_) => onErrore?.call());
                  return const SizedBox.shrink();
                },
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _apri(BuildContext context) => Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => DettaglioFoto(foto: foto, titolo: titolo, strings: strings),
        ),
      );
}

/// Spaziatura + miniatura. Se la foto non si decodifica sparisce TUTTO (anche
/// la spaziatura): la card resta esattamente com'è, senza riquadri vuoti né
/// tocchi.
class SezioneFoto extends StatefulWidget {
  final FotoTappa foto;
  final String titolo;
  final AppStrings strings;
  const SezioneFoto({super.key, required this.foto, required this.titolo, required this.strings});

  @override
  State<SezioneFoto> createState() => _SezioneFotoState();
}

class _SezioneFotoState extends State<SezioneFoto> {
  bool _rotta = false;

  @override
  Widget build(BuildContext context) {
    if (_rotta) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 10),
        MiniaturaFoto(
          foto: widget.foto,
          titolo: widget.titolo,
          strings: widget.strings,
          onErrore: () {
            if (mounted) setState(() => _rotta = true);
          },
        ),
      ],
    );
  }
}

/// Dettaglio minimo: la foto intera, la didascalia e «Foto: <autore>».
class DettaglioFoto extends StatelessWidget {
  final FotoTappa foto;
  final String titolo;
  final AppStrings strings;
  const DettaglioFoto({super.key, required this.foto, required this.titolo, required this.strings});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(titolo, overflow: TextOverflow.ellipsis)),
      body: SafeArea(
        child: ColonnaCentrata(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Semantics(
                label: foto.didascalia,
                image: true,
                excludeSemantics: true,
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(Tk.raggio),
                  child: Image(
                    image: foto.immagine,
                    fit: BoxFit.contain,
                    errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Text(foto.didascalia, style: Theme.of(context).textTheme.bodyLarge),
              const SizedBox(height: 4),
              Text(strings.photoBy(foto.autore), style: stileTesto(14, 600, Tk.testoSecondario)),
            ],
          ),
        ),
      ),
    );
  }
}
