// Supporto ai test dei segnaposti (non e' un test: il suffisso non e' _test).
// Le varianti si provano SEMPRE iniettando la sagoma letta dal file, mai dal
// bundle, cosi' si sa quale variante gira.
import 'dart:io';

import 'package:lucca_soul_app/widgets/segnaposto_mura.dart';
import 'package:lucca_soul_app/widgets/segnaposto_variante.dart';

SagomaSegnaposto sagomaDi(VarianteSegnaposto v) =>
    parseSagomaSegnaposto(File(v.asset).readAsStringSync());

/// Le due varianti con sagoma.
const kVarianti = VarianteSegnaposto.values;
