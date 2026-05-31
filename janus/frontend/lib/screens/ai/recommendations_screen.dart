// lib/screens/ai/recommendations_screen.dart
import 'package:flutter/material.dart';

class RecommendationsScreen extends StatelessWidget {
  const RecommendationsScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Recomendações')),
      body: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.lightbulb_outline, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text('Tela de Recomendações', style: TextStyle(fontSize: 20)),
            SizedBox(height: 8),
            Text('Em desenvolvimento', style: TextStyle(color: Colors.grey)),
          ],
        ),
      ),
    );
  }
}
