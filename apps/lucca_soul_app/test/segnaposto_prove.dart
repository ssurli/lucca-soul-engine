// Supporto ai test dei segnaposti (non e' un test: il suffisso non e' _test).
// La sagoma si prova SEMPRE iniettandola dal file, mai dal bundle, cosi' si
// sa cosa gira.
import 'dart:io';

import 'package:lucca_soul_app/widgets/segnaposto_mura.dart';

SagomaSegnaposto sagomaMura() => parseSagomaSegnaposto(
      File('assets/brand/segnaposto_sagoma.json').readAsStringSync(),
    );
