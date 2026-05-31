import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class SLOsScreen extends StatefulWidget {
  const SLOsScreen({Key? key}) : super(key: key);
  @override State<SLOsScreen> createState() => _SLOsScreenState();
}

class _SLOsScreenState extends State<SLOsScreen> {
  List<dynamic> _slos = [];
  bool _loading = true;

  @override void initState() { super.initState(); _fetchSLOs(); }

  Future<void> _fetchSLOs() async {
    try {
      final response = await http.get(
        Uri.parse('http://localhost:8000/slos/status'),
        headers: {'Authorization': 'Bearer \${await _getToken()}'},
      );
      if (response.statusCode == 200) {
        setState(() { _slos = jsonDecode(response.body); _loading = false; });
      }
    } catch (e) { setState(() => _loading = false); }
  }

  Future<String> _getToken() async { return ''; }

  Color _getStatusColor(String status) {
    switch (status) {
      case 'HEALTHY': return Colors.green;
      case 'AT_RISK': return Colors.orange;
      case 'BREACH': return Colors.red;
      default: return Colors.grey;
    }
  }

  @override Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('SLOs & Reliability')),
      body: _loading ? const Center(child: CircularProgressIndicator())
        : ListView.builder(
            itemCount: _slos.length,
            itemBuilder: (context, index) {
              final slo = _slos[index];
              return Card(
                child: ListTile(
                  leading: CircleAvatar(
                    backgroundColor: _getStatusColor(slo['status']),
                    child: Icon(
                      slo['status'] == 'HEALTHY' ? Icons.check : Icons.warning,
                      color: Colors.white,
                    ),
                  ),
                  title: Text(slo['name']),
                  subtitle: Text('Target: \${slo['target']} | Current: \${slo['current'].toStringAsFixed(2)}'),
                  trailing: Chip(
                    label: Text(slo['status']),
                    backgroundColor: _getStatusColor(slo['status']).withOpacity(0.2),
                  ),
                ),
              );
            },
          ),
    );
  }
}
