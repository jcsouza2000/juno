import 'package:flutter/material.dart';

class PaymentsScreen extends StatefulWidget {
  const PaymentsScreen({Key? key}) : super(key: key);
  @override State<PaymentsScreen> createState() => _PaymentsScreenState();
}

class _PaymentsScreenState extends State<PaymentsScreen> {
  String _provider = 'stripe';

  @override Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Payment Gateway')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            DropdownButtonFormField<String>(
              value: _provider,
              items: const ['stripe', 'pagarme'].map((p) => DropdownMenuItem(value: p, child: Text(p.toUpperCase()))).toList(),
              onChanged: (v) => setState(() => _provider = v!),
              decoration: const InputDecoration(labelText: 'Provider'),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.person_add),
              label: const Text('Create Customer'),
            ),
            const SizedBox(height: 8),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.payment),
              label: const Text('Create Payment Intent'),
            ),
            const SizedBox(height: 8),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.subscriptions),
              label: const Text('Create Subscription'),
            ),
          ],
        ),
      ),
    );
  }
}
