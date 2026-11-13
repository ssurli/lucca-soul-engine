// Supporto ai test dei segnaposti (non e' un test: il suffisso non e' _test).
// La sagoma si prova SEMPRE iniettandola dal file, mai dal bundle, cosi' si
// sa cosa gira.
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:lucca_soul_app/widgets/segnaposto_mura.dart';

SagomaSegnaposto sagomaMura() => parseSagomaSegnaposto(
      File('assets/brand/segnaposto_sagoma.json').readAsStringSync(),
    );

// ---- Numero disegnato nelle card della lista (sagoma senza punta) ----
// Il numero non e' un Text: sta nel SagomaPainter dentro `Key('numero-sagoma')`.
// Si legge dal painter (numero) e dalla Semantics (label), non da find.text.

/// Dentro [dentro] (o tutta la pagina): il riquadro del numero disegnato.
Finder numeroSagoma([Finder? dentro]) => dentro == null
    ? find.byKey(const Key('numero-sagoma'))
    : find.descendant(
        of: dentro, matching: find.byKey(const Key('numero-sagoma')),);

/// Il CustomPaint che disegna il numero dentro [riquadro].
Finder disegnoNumero(Finder riquadro) => find.descendant(
      of: riquadro,
      matching: find.byWidgetPredicate(
        (w) => w is CustomPaint && w.painter is SagomaPainter,
      ),
    );

/// Numeri disegnati, nell'ordine dell'albero (= ordine delle card).
List<int> numeriDisegnati(WidgetTester t, [Finder? dentro]) => [
      for (final e in disegnoNumero(numeroSagoma(dentro)).evaluate())
        ((e.widget as CustomPaint).painter! as SagomaPainter).numero,
    ];
