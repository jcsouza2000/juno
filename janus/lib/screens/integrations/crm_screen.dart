import 'package:flutter/material.dart';

class CRMScreen extends StatefulWidget {
  const CRMScreen({Key? key}) : super(key: key);
  @override State<CRMScreen> createState() => _CRMScreenState();
}

class _CRMScreenState extends State<CRMScreen> {
  String _provider = 'salesforce';

  @override Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('CRM Integration')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            DropdownButtonFormField<String>(
              value: _provider,
              items: const ['salesforce', 'hubspot'].map((p) => DropdownMenuItem(value: p, child: Text(p.toUpperCase()))).toList(),
              onChanged: (v) => setState(() => _provider = v!),
              decoration: const InputDecoration(labelText: 'Provider'),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.sync),
              label: const Text('Sync Contacts'),
            ),
            const SizedBox(height: 8),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.business),
              label: const Text('Sync Opportunities'),
            ),
          ],
        ),
      ),
    );
  }
}
