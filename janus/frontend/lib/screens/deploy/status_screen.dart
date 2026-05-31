// lib/screens/deploy/status_screen.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../../config/api_config.dart';

class StatusScreen extends StatefulWidget {
  const StatusScreen({Key? key}) : super(key: key);

  @override
  State<StatusScreen> createState() => _StatusScreenState();
}

class _StatusScreenState extends State<StatusScreen> {
  Map<String, dynamic> _health = {};
  Map<String, dynamic> _metrics = {};
  Map<String, dynamic> _dependencies = {};
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    await Future.wait([
      _loadHealth(),
      _loadMetrics(),
      _loadDependencies(),
    ]);
    setState(() => _isLoading = false);
  }

  Future<void> _loadHealth() async {
    try {
      final response = await http.get(
        Uri.parse('/api/v1/health/'),
      );
      if (response.statusCode == 200) {
        setState(() => _health = json.decode(response.body));
      }
    } catch (e) {
      setState(() => _health = {'status': 'offline', 'error': e.toString()});
    }
  }

  Future<void> _loadMetrics() async {
    try {
      final response = await http.get(
        Uri.parse('/api/v1/health/metrics'),
        headers: ApiConfig.headers,
      );
      if (response.statusCode == 200) {
        setState(() => _metrics = json.decode(response.body));
      }
    } catch (e) {
      debugPrint('Erro metrics: ');
    }
  }

  Future<void> _loadDependencies() async {
    try {
      final response = await http.get(
        Uri.parse('/api/v1/health/dependencies'),
        headers: ApiConfig.headers,
      );
      if (response.statusCode == 200) {
        setState(() => _dependencies = json.decode(response.body));
      }
    } catch (e) {
      debugPrint('Erro dependencies: ');
    }
  }

  @override
  Widget build(BuildContext context) {
    final isHealthy = _health['status'] == 'healthy';

    return Scaffold(
      appBar: AppBar(
        title: const Text('Status do Sistema'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              setState(() => _isLoading = true);
              _loadData();
            },
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadData,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _buildStatusCard(isHealthy),
                  const SizedBox(height: 16),
                  _buildMetricsCard(),
                  const SizedBox(height: 16),
                  _buildDependenciesCard(),
                  const SizedBox(height: 16),
                  _buildInfoCard(),
                ],
              ),
            ),
    );
  }

  Widget _buildStatusCard(bool isHealthy) {
    return Card(
      color: isHealthy ? Colors.green[50] : Colors.red[50],
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Icon(
              isHealthy ? Icons.check_circle : Icons.error,
              size: 64,
              color: isHealthy ? Colors.green : Colors.red,
            ),
            const SizedBox(height: 12),
            Text(
              isHealthy ? 'SISTEMA OPERACIONAL' : 'SISTEMA COM PROBLEMAS',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: isHealthy ? Colors.green[800] : Colors.red[800],
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Uptime: ',
              style: TextStyle(color: Colors.grey[600]),
            ),
            Text(
              'Versao: ',
              style: TextStyle(color: Colors.grey[600]),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricsCard() {
    if (_metrics.isEmpty) return const SizedBox.shrink();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Metricas do Servidor',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const Divider(),
            _buildMetricRow('CPU', '%', Colors.blue),
            _buildMetricRow('Memoria', '%', Colors.orange),
            _buildMetricRow('Disco', '%', Colors.purple),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricRow(String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(6)),
          ),
          const SizedBox(width: 12),
          Text(label, style: const TextStyle(fontWeight: FontWeight.w500)),
          const Spacer(),
          Text(value, style: TextStyle(fontWeight: FontWeight.bold, color: color)),
        ],
      ),
    );
  }

  Widget _buildDependenciesCard() {
    if (_dependencies.isEmpty) return const SizedBox.shrink();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Dependencias',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const Divider(),
            ..._dependencies.entries.map((entry) {
              final status = entry.value['status'] ?? 'unknown';
              final isOk = status == 'ok';
              return ListTile(
                leading: Icon(
                  isOk ? Icons.check_circle : Icons.error,
                  color: isOk ? Colors.green : Colors.red,
                ),
                title: Text(entry.key.toUpperCase()),
                subtitle: Text(status),
                trailing: !isOk
                    ? Text(
                        entry.value['message'] ?? '',
                        style: const TextStyle(color: Colors.red, fontSize: 12),
                      )
                    : null,
              );
            }).toList(),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Links de Monitoramento',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const Divider(),
            _buildLinkTile('Grafana', 'http://localhost:3000', Icons.dashboard),
            _buildLinkTile('Prometheus', 'http://localhost:9090', Icons.show_chart),
            _buildLinkTile('API Docs', '/api/v1/docs', Icons.api),
          ],
        ),
      ),
    );
  }

  Widget _buildLinkTile(String title, String url, IconData icon) {
    return ListTile(
      leading: Icon(icon, color: Colors.indigo),
      title: Text(title),
      subtitle: Text(url, style: const TextStyle(fontSize: 12)),
      trailing: const Icon(Icons.open_in_new, size: 18),
      onTap: () {
        // Abrir URL (usar url_launcher em producao)
        debugPrint('Abrir: ');
      },
    );
  }

  String _formatDuration(int seconds) {
    final duration = Duration(seconds: seconds);
    final days = duration.inDays;
    final hours = duration.inHours % 24;
    final mins = duration.inMinutes % 60;
    if (days > 0) return 'd h m';
    if (hours > 0) return 'h m';
    return 'm';
  }
}
