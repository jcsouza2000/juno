import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({Key? key}) : super(key: key);
  @override State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  List<dynamic> _alerts = [];
  bool _loading = true;

  @override void initState() { super.initState(); _fetchAlerts(); }

  Future<void> _fetchAlerts() async {
    try {
      final response = await http.get(
        Uri.parse('http://localhost:8000/alerts/active'),
        headers: {'Authorization': 'Bearer \${await _getToken()}'},
      );
      if (response.statusCode == 200) {
        setState(() { _alerts = jsonDecode(response.body); _loading = false; });
      }
    } catch (e) { setState(() => _loading = false); }
  }

  Future<String> _getToken() async { return ''; }

  @override Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Active Alerts')),
      body: _loading ? const Center(child: CircularProgressIndicator())
        : _alerts.isEmpty ? const Center(child: Text('No active alerts'))
        : ListView.builder(
            itemCount: _alerts.length,
            itemBuilder: (context, index) {
              final alert = _alerts[index];
              final labels = alert['labels'] ?? {};
              return Card(
                color: (labels['severity'] == 'critical') ? Colors.red.shade50 : Colors.orange.shade50,
                child: ListTile(
                  leading: Icon(
                    labels['severity'] == 'critical' ? Icons.error : Icons.warning,
                    color: labels['severity'] == 'critical' ? Colors.red : Colors.orange,
                  ),
                  title: Text(labels['alertname'] ?? 'Unknown'),
                  subtitle: Text('Severity: \${labels['severity'] ?? 'unknown'}\nInstance: \${labels['instance'] ?? 'N/A'}'),
                  isThreeLine: true,
                  trailing: TextButton(
                    child: const Text('Silence'),
                    onPressed: () => _silenceAlert(alert),
                  ),
                ),
              );
            },
          ),
    );
  }

  void _silenceAlert(dynamic alert) { }
}
