/// Rispecchia `Signal.meteo` in `docs/DATA_CONTRACTS.md` §1
/// (`Literal["sereno","pioggia","caldo","freddo"]`). Nessun valore in più.
enum Meteo { sereno, pioggia, caldo, freddo }

extension MeteoJsonCodec on Meteo {
  String toJson() => name;
}

Meteo meteoFromJson(String value) {
  return Meteo.values.firstWhere(
    (m) => m.name == value,
    orElse: () => throw FormatException('meteo sconosciuto dal BFF: "$value"'),
  );
}
