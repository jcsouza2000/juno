import 'package:flutter/material.dart';

class FineTuningScreen extends StatefulWidget {
  const FineTuningScreen({Key? key}) : super(key: key);
  @override State<FineTuningScreen> createState() => _FineTuningScreenState();
}

class _FineTuningScreenState extends State<FineTuningScreen> {
  String _baseModel = 'microsoft/DialoGPT-medium';
  double _loraR = 16;
  double _epochs = 3;

  @override Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Fine-tuning')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              decoration: const InputDecoration(labelText: 'Base Model'),
              controller: TextEditingController(text: _baseModel),
              onChanged: (v) => _baseModel = v,
            ),
            const SizedBox(height: 16),
            Text('LoRA R: \${_loraR.toInt()}'),
            Slider(
              value: _loraR,
              min: 4,
              max: 64,
              divisions: 15,
              onChanged: (v) => setState(() => _loraR = v),
            ),
            Text('Epochs: \${_epochs.toInt()}'),
            Slider(
              value: _epochs,
              min: 1,
              max: 10,
              divisions: 9,
              onChanged: (v) => setState(() => _epochs = v),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.model_training),
              label: const Text('Start Training'),
            ),
            const SizedBox(height: 8),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.upload_file),
              label: const Text('Upload Dataset'),
            ),
          ],
        ),
      ),
    );
  }
}
