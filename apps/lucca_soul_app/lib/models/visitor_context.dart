import 'emotional_profile.dart';
import 'person_kind.dart';
import 'signal.dart';

/// Rispecchia `VisitorContext` in `docs/DATA_CONTRACTS.md` §1.
/// Input di `POST /itinerary`. `personId` è uno PSEUDONIMO locale, mai PII.
class VisitorContext {
  final String personId;
  final PersonKind kind;
  final EmotionalProfile profile;
  final Signal signal;
  final List<String> luoghiGiaVisti;

  const VisitorContext({
    required this.personId,
    this.kind = PersonKind.turista,
    required this.profile,
    required this.signal,
    this.luoghiGiaVisti = const [],
  });

  Map<String, dynamic> toJson() => {
        'person_id': personId,
        'kind': kind.toJson(),
        'profile': profile.toJson(),
        'signal': signal.toJson(),
        'luoghi_gia_visti': luoghiGiaVisti,
      };
}
