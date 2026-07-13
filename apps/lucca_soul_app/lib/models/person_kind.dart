/// Rispecchia `PersonKind` in `docs/DATA_CONTRACTS.md` §1.
/// Il Cittadino non paga: alimenta la Urban Memory (Wave 2).
enum PersonKind { turista, cittadino }

extension PersonKindJsonCodec on PersonKind {
  String toJson() => name;
}

PersonKind personKindFromJson(String value) {
  return PersonKind.values.firstWhere(
    (k) => k.name == value,
    orElse: () => throw FormatException('kind sconosciuto dal BFF: "$value"'),
  );
}
