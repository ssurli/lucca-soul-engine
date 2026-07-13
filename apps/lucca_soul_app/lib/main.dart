import 'package:flutter/material.dart';

import 'api/bff_client.dart';
import 'screens/onboarding_screen.dart';
import 'util/person_id.dart';

void main() {
  runApp(const LuccaSoulApp());
}

/// Radice dell'app. Un solo `BffClient` per l'intera sessione: l'app parla
/// SOLO con il BFF (`services/api`), mai con i servizi interni.
///
/// `person_id` è generato qui, una volta, come pseudonimo locale: non è
/// mai persistito sul device né contiene alcun dato personale.
class LuccaSoulApp extends StatefulWidget {
  const LuccaSoulApp({super.key});

  @override
  State<LuccaSoulApp> createState() => _LuccaSoulAppState();
}

class _LuccaSoulAppState extends State<LuccaSoulApp> {
  late final BffClient _bffClient = BffClient();
  late final String _personId = generatePersonId();

  @override
  void dispose() {
    _bffClient.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Lucca Soul Lab',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF7A5C3E)),
        useMaterial3: true,
      ),
      home: OnboardingScreen(bffClient: _bffClient, personId: _personId),
    );
  }
}
