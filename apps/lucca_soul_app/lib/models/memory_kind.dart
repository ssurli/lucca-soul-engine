/// Rispecchia `MemoryKind` in `docs/DATA_CONTRACTS.md` §4 / `packages/contracts`.
/// Nessun valore in più: il tipo di contributo alla Urban Memory.
enum MemoryKind { racconto, fotografia, musica, mestiere, ricetta, dialetto, testimonianza }

extension MemoryKindJsonCodec on MemoryKind {
  String toJson() => name;
}

MemoryKind memoryKindFromJson(String value) {
  return MemoryKind.values.firstWhere(
    (k) => k.name == value,
    orElse: () => throw FormatException('kind di memoria sconosciuto dal BFF: "$value"'),
  );
}
