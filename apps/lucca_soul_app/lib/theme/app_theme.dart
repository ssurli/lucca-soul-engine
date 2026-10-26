import 'package:flutter/material.dart';

import 'tokens.dart';

/// Stile con asse `wght` esplicito: i font incorporati sono variabili, e il
/// peso va chiesto anche come variazione (non ci si affida al solo `fontWeight`).
TextStyle _stile(String famiglia, double dimensione, int peso, Color colore,
    {double? altezza,}) {
  return TextStyle(
    fontFamily: famiglia,
    fontSize: dimensione,
    fontWeight: FontWeight.values[(peso ~/ 100) - 1],
    fontVariations: [FontVariation('wght', peso.toDouble())],
    color: colore,
    height: altezza,
  );
}

/// Titoli: Domine 700.
TextStyle stileTitolo(double dimensione, Color colore) =>
    _stile(Tk.fontTitoli, dimensione, 700, colore, altezza: 1.25);

/// Testo: Nunito Sans 400/600/700/800.
TextStyle stileTesto(double dimensione, int peso, Color colore) =>
    _stile(Tk.fontTesto, dimensione, peso, colore, altezza: 1.4);

TextTheme _textTheme() {
  const t = Tk.testo;
  return TextTheme(
    displayLarge: stileTitolo(32, t),
    displayMedium: stileTitolo(28, t),
    displaySmall: stileTitolo(24, t),
    headlineLarge: stileTitolo(24, t),
    headlineMedium: stileTitolo(22, t),
    headlineSmall: stileTitolo(20, t),
    titleLarge: stileTitolo(19, t),
    titleMedium: stileTitolo(17, t),
    titleSmall: stileTesto(15, 700, t),
    bodyLarge: stileTesto(16, 400, t),
    bodyMedium: stileTesto(15, 400, t),
    bodySmall: stileTesto(13, 400, Tk.testoSecondario),
    labelLarge: stileTesto(15, 700, t),
    labelMedium: stileTesto(13, 600, Tk.testoSecondario),
    labelSmall: stileTesto(12, 600, Tk.testoSecondario),
  );
}

/// Tema unico dell'app (direzione C).
ThemeData buildAppTheme() {
  const scheme = ColorScheme(
    brightness: Brightness.light,
    primary: Tk.accento,
    onPrimary: Tk.testoSuAccento,
    primaryContainer: Tk.sostituitaSfondo,
    onPrimaryContainer: Tk.sostituitaTesto,
    secondary: Tk.accento,
    onSecondary: Tk.testoSuAccento,
    secondaryContainer: Tk.avviso,
    onSecondaryContainer: Tk.testo,
    tertiary: Tk.accentoPremuto,
    onTertiary: Tk.testoSuAccento,
    tertiaryContainer: Tk.sostituitaSfondo,
    onTertiaryContainer: Tk.sostituitaTesto,
    error: Color(0xFF8C2B1B),
    onError: Tk.testoSuAccento,
    errorContainer: Tk.sostituitaSfondo,
    onErrorContainer: Tk.sostituitaTesto,
    surface: Tk.sfondo,
    onSurface: Tk.testo,
    onSurfaceVariant: Tk.testoSecondario,
    surfaceContainerLowest: Tk.cardSfondo,
    surfaceContainerLow: Tk.cardSfondo,
    surfaceContainer: Tk.cardSfondo,
    surfaceContainerHigh: Tk.avviso,
    surfaceContainerHighest: Tk.avviso,
    outline: Tk.grigioNonTestuale,
    outlineVariant: Tk.cardBordo,
    shadow: Colors.black,
    scrim: Colors.black,
    inverseSurface: Tk.testata,
    onInverseSurface: Tk.testoSuTestata,
    inversePrimary: Tk.testoSuTestata,
  );
  final tt = _textTheme();
  final raggio = BorderRadius.circular(Tk.raggio);
  const bordoControllo = BorderSide(color: Tk.grigioNonTestuale);
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: Tk.sfondo,
    fontFamily: Tk.fontTesto,
    textTheme: tt,
    primaryTextTheme: tt,
    appBarTheme: AppBarTheme(
      backgroundColor: Tk.testata,
      foregroundColor: Tk.testoSuTestata,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      titleTextStyle: stileTitolo(19, Tk.testoSuTestata),
      iconTheme: const IconThemeData(color: Tk.testoSuTestata),
    ),
    cardTheme: CardThemeData(
      color: Tk.cardSfondo,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      shape: RoundedRectangleBorder(
          borderRadius: raggio, side: const BorderSide(color: Tk.cardBordo),),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(Tk.areaMinima, Tk.areaMinima),
        textStyle: tt.labelLarge,
      ).copyWith(
        backgroundColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.disabled)
              ? Tk.cardBordo
              : (s.contains(WidgetState.pressed) ||
                      s.contains(WidgetState.hovered))
                  ? Tk.accentoPremuto
                  : Tk.accento,
        ),
        foregroundColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.disabled)
              ? Tk.testoSecondario
              : Tk.testoSuAccento,
        ),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(Tk.areaMinima, Tk.areaMinima),
        foregroundColor: Tk.accento,
        textStyle: tt.labelLarge,
        side: bordoControllo,
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        minimumSize: const Size(Tk.areaMinima, Tk.areaMinima),
        textStyle: tt.labelLarge,
      ).copyWith(
        foregroundColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.disabled)
              ? Tk.testoSecondario
              : (s.contains(WidgetState.pressed) ||
                      s.contains(WidgetState.hovered))
                  ? Tk.accentoPremuto
                  : Tk.accento,
        ),
      ),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: Tk.cardSfondo,
      selectedColor: Tk.accento,
      checkmarkColor: Tk.testoSuAccento,
      labelStyle: tt.bodyMedium,
      secondaryLabelStyle: tt.bodyMedium?.copyWith(color: Tk.testoSuAccento),
      side: bordoControllo,
      shape: RoundedRectangleBorder(borderRadius: raggio),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Tk.cardSfondo,
      border:
          OutlineInputBorder(borderRadius: raggio, borderSide: bordoControllo),
      enabledBorder:
          OutlineInputBorder(borderRadius: raggio, borderSide: bordoControllo),
      focusedBorder: OutlineInputBorder(
          borderRadius: raggio,
          borderSide: const BorderSide(color: Tk.accento, width: 2),),
      labelStyle: tt.bodyMedium?.copyWith(color: Tk.testoSecondario),
      hintStyle: tt.bodyMedium?.copyWith(color: Tk.testoSecondario),
    ),
    dividerTheme: const DividerThemeData(color: Tk.cardBordo),
    progressIndicatorTheme: const ProgressIndicatorThemeData(color: Tk.accento),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: Tk.testata,
      contentTextStyle: stileTesto(15, 400, Tk.testoSuTestata),
      actionTextColor: Tk.testoSuTestata,
    ),
  );
}
