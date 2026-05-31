// lib/screens/ai/anomalies_screen.dart
import 'package:flutter/material.dart';

class AnomaliesScreen extends StatelessWidget {
  const AnomaliesScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Anomalias')),
      body: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.warning_amber, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text('Tela de Anomalias', style: TextStyle(fontSize: 20)),
            SizedBox(height: 8),
            Text('Em desenvolvimento', style: TextStyle(color: Colors.grey)),
          ],
        ),
      ),
    );
  }
}
