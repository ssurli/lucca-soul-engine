// TEMPORANEO: la scelta tra le due varianti del segnaposto si fa sul telefono.
// Dopo la scelta si tolgono la variante scartata, questo file, il define
// SEGNAPOSTO, il parametro -Segnaposto di scripts/avvia_demo.ps1 e (se resta
// il baluardo) il ramo `mura` del caricamento.

/// Le due varianti. `baluardo` e' il default.
enum VarianteSegnaposto {
  mura('assets/brand/segnaposto_sagoma.json'),
  baluardo('assets/brand/segnaposto_baluardo.json');

  final String asset;
  const VarianteSegnaposto(this.asset);
}

/// Unico punto in cui si legge il define: `--dart-define=SEGNAPOSTO=mura|baluardo`.
const String _kSegnapostoDefine = String.fromEnvironment('SEGNAPOSTO');

/// Valore sconosciuto o vuoto: default `baluardo`.
VarianteSegnaposto varianteDaTesto(String valore) =>
    valore == 'mura' ? VarianteSegnaposto.mura : VarianteSegnaposto.baluardo;

/// Variante scelta all'avvio dalla build.
final VarianteSegnaposto kVarianteSegnaposto =
    varianteDaTesto(_kSegnapostoDefine);
