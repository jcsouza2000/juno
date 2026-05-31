import 'package:flutter/material.dart';

class ETLScreen extends StatefulWidget {
  const ETLScreen({Key? key}) : super(key: key);
  @override State<ETLScreen> createState() => _ETLScreenState();
}

class _ETLScreenState extends State<ETLScreen> {
  @override Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('ETL Pipeline')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.upload_file),
              label: const Text('Import CSV'),
            ),
            const SizedBox(height: 8),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.upload_file),
              label: const Text('Import Excel'),
            ),
            const SizedBox(height: 8),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.download),
              label: const Text('Export CSV'),
            ),
            const SizedBox(height: 8),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.download),
              label: const Text('Export Excel'),
            ),
          ],
        ),
      ),
    );
  }
}
