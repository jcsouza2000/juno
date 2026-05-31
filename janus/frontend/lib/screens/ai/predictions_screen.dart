// lib/screens/ai/predictions_screen.dart
import 'package:flutter/material.dart';

class PredictionsScreen extends StatelessWidget {
  const PredictionsScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Previsões')),
      body: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.trending_up, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text('Tela de Previsões', style: TextStyle(fontSize: 20)),
            SizedBox(height: 8),
            Text('Em desenvolvimento', style: TextStyle(color: Colors.grey)),
          ],
        ),
      ),
    );
  }
}
