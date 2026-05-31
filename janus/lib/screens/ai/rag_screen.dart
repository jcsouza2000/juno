import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:io';

class RAGScreen extends StatefulWidget {
  const RAGScreen({Key? key}) : super(key: key);
  @override State<RAGScreen> createState() => _RAGScreenState();
}

class _RAGScreenState extends State<RAGScreen> {
  final TextEditingController _queryController = TextEditingController();
  String _response = '';
  bool _loading = false;
  List<dynamic> _sources = [];

  Future<void> _queryRAG() async {
    setState(() => _loading = true);
    try {
      final response = await http.post(
        Uri.parse('http://localhost:8000/ai/rag/query'),
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer \${await _getToken()}'},
        body: jsonEncode({'query': _queryController.text, 'use_hybrid': true, 'top_k': 5}),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _response = data['answer'] ?? 'No response';
          _sources = data['sources'] ?? [];
          _loading = false;
        });
      }
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  Future<String> _getToken() async { return ''; }

  @override Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('RAG Knowledge Base')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            TextField(
              controller: _queryController,
              decoration: const InputDecoration(
                labelText: 'Ask a question...',
                suffixIcon: Icon(Icons.search),
              ),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _queryRAG,
              child: _loading ? const CircularProgressIndicator() : const Text('Search'),
            ),
            const SizedBox(height: 16),
            if (_response.isNotEmpty)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Text(_response),
                ),
              ),
            const SizedBox(height: 16),
            if (_sources.isNotEmpty)
              Expanded(
                child: ListView.builder(
                  itemCount: _sources.length,
                  itemBuilder: (context, index) {
                    final source = _sources[index];
                    return ListTile(
                      title: Text('Source \${index + 1}'),
                      subtitle: Text(source['content']?.substring(0, 100) ?? ''),
                      trailing: Text('Score: \${(source['hybrid_score'] ?? 0).toStringAsFixed(2)}'),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }
}
