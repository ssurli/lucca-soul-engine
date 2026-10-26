import 'package:flutter/material.dart';

import '../theme/tokens.dart';

/// Su schermi larghi il contenuto sta in una colonna centrata di al massimo
/// [Tk.colonnaMax] px; sugli schermi stretti occupa tutta la larghezza.
class ColonnaCentrata extends StatelessWidget {
  final Widget child;
  const ColonnaCentrata({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: Tk.colonnaMax),
          child: child,),
    );
  }
}
