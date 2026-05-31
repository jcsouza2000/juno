import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class TracingScreen extends StatefulWidget {
  const TracingScreen({Key? key}) : super(key: key);
  @override State<TracingScreen> createState() => _TracingScreenState();
}

class _TracingScreenState extends State<TracingScreen> {
  List<dynamic> _traces = [];
  bool _loading = true;

  @override void initState() { super.initState(); _fetchTraces(); }

  Future<void> _fetchTraces() async {
    try {
      final response = await http.get(Uri.parse('http://localhost:16686/api/traces?service=juno-api&limit=20'));
      if (response.statusCode == 200) {
        setState(() { _traces = jsonDecode(response.body)['data'] ?? []; _loading = false; });
      }
    } catch (e) { setState(() => _loading = false); }
  }

  @override Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Distributed Tracing')),
      body: _loading ? const Center(child: CircularProgressIndicator())
        : ListView.builder(
            itemCount: _traces.length,
            itemBuilder: (context, index) {
              final trace = _traces[index];
              return Card(
                child: ListTile(
                  leading: const Icon(Icons.timeline),
                  title: Text('Trace ID: \${trace['traceID']?.substring(0, 8) ?? 'N/A'}...'),
                  subtitle: Text('Spans: \${trace['spans']?.length ?? 0}'),
                  trailing: IconButton(icon: const Icon(Icons.open_in_new), onPressed: () {}),
                ),
              );
            },
          ),
    );
  }
}
