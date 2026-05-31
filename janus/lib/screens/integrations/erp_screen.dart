import 'package:flutter/material.dart';

class ERPScreen extends StatefulWidget {
  const ERPScreen({Key? key}) : super(key: key);
  @override State<ERPScreen> createState() => _ERPScreenState();
}

class _ERPScreenState extends State<ERPScreen> {
  String _provider = 'sap';

  @override Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('ERP Connectors')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            DropdownButtonFormField<String>(
              value: _provider,
              items: const ['sap', 'totvs', 'odoo'].map((p) => DropdownMenuItem(value: p, child: Text(p.toUpperCase()))).toList(),
              onChanged: (v) => setState(() => _provider = v!),
              decoration: const InputDecoration(labelText: 'Provider'),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.sync),
              label: const Text('Sync Products'),
            ),
            const SizedBox(height: 8),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.people),
              label: const Text('Sync Customers'),
            ),
            const SizedBox(height: 8),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.inventory),
              label: const Text('Sync Inventory'),
            ),
          ],
        ),
      ),
    );
  }
}
