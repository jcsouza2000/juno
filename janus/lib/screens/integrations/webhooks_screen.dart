import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class WebhooksScreen extends StatefulWidget {
  const WebhooksScreen({Key? key}) : super(key: key);
  @override State<WebhooksScreen> createState() => _WebhooksScreenState();
}

class _WebhooksScreenState extends State<WebhooksScreen> {
  List<dynamic> _subs = [];
  bool _loading = true;

  @override void initState() { super.initState(); _fetchSubs(); }

  Future<void> _fetchSubs() async {
    try {
      final response = await http.get(
        Uri.parse('http://localhost:8000/webhooks/subscriptions'),
        headers: {'Authorization': 'Bearer \${await _getToken()}'},
      );
      if (response.statusCode == 200) {
        setState(() { _subs = jsonDecode(response.body); _loading = false; });
      }
    } catch (e) { setState(() => _loading = false); }
  }

  Future<String> _getToken() async { return ''; }

  @override Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Webhook Subscriptions')),
      body: _loading ? const Center(child: CircularProgressIndicator())
        : ListView.builder(
            itemCount: _subs.length,
            itemBuilder: (context, index) {
              final sub = _subs[index];
              return Card(
                child: ListTile(
                  leading: const Icon(Icons.webhook),
                  title: Text(sub['url'] ?? 'Unknown'),
                  subtitle: Text('Events: \${(sub['event_types'] ?? []).join(', ')}'),
                  trailing: Chip(label: Text(sub['active'] ? 'Active' : 'Inactive')),
                ),
              );
            },
          ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {},
        child: const Icon(Icons.add),
      ),
    );
  }
}
