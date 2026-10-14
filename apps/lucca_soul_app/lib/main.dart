import 'package:flutter/material.dart';

import 'api/bff_client.dart';
import 'screens/citizen_screen.dart';
import 'screens/dashboard_screen.dart';
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
      home: _HomeScreen(bffClient: _bffClient, personId: _personId),
    );
  }
}

/// Punto di ingresso: sceglie tra il percorso Turista (onboarding
/// conversazionale), la vista Cittadino (Urban Memory) e la dashboard
/// Comune/Operatori (Urban Intelligence Index, Wave 4).
///
/// "Il Cittadino non paga: alimenta la Urban Memory ed è la condizione di
/// sostenibilità sociale del sistema" (CLAUDE.md) — è un percorso di prima
/// classe fin dalla radice dell'app, non una funzione nascosta dentro
/// quello del turista. La dashboard non porta `person_id`: gli indicatori
/// sono aggregati e anonimi, non un dato di sessione di una persona.
class _HomeScreen extends StatelessWidget {
  final BffClient bffClient;
  final String personId;

  const _HomeScreen({required this.bffClient, required this.personId});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Lucca Soul Lab')),
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.auto_awesome, size: 48, color: Theme.of(context).colorScheme.primary),
                const SizedBox(height: 16),
                Text(
                  'Chi sei oggi?',
                  style: Theme.of(context).textTheme.headlineSmall,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    icon: const Icon(Icons.explore_outlined),
                    label: const Text('Sono un visitatore'),
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => OnboardingScreen(bffClient: bffClient, personId: personId),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.groups_outlined),
                    label: const Text('Sono cittadino/a di Lucca'),
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => CitizenScreen(bffClient: bffClient, personId: personId),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.bar_chart_outlined),
                    label: const Text('Dashboard Comune / Operatori'),
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(builder: (_) => DashboardScreen(bffClient: bffClient)),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
