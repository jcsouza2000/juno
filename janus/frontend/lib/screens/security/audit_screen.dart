// lib/screens/security/audit_screen.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../../config/api_config.dart';

class AuditScreen extends StatefulWidget {
  const AuditScreen({Key? key}) : super(key: key);

  @override
  State<AuditScreen> createState() => _AuditScreenState();
}

class _AuditScreenState extends State<AuditScreen> {
  List<dynamic> _logs = [];
  Map<String, dynamic> _stats = {};
  bool _isLoading = true;
  String? _selectedAction;
  String? _selectedSeverity;

  final List<String> _actions = ['CREATE', 'READ', 'UPDATE', 'DELETE', 'LOGIN', 'EXPORT'];
  final List<String> _severities = ['debug', 'info', 'warning', 'error', 'critical'];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    await Future.wait([_loadLogs(), _loadStats()]);
    setState(() => _isLoading = false);
  }

  Future<void> _loadLogs() async {
    try {
      final queryParams = <String, String>{'limit': '100'};
      if (_selectedAction != null) queryParams['action'] = _selectedAction!;
      if (_selectedSeverity != null) queryParams['severity'] = _selectedSeverity!;

      final response = await http.post(
        Uri.parse('/api/v1/security/audit/query').replace(queryParameters: queryParams),
        headers: {...ApiConfig.headers, 'Content-Type': 'application/json'},
        body: json.encode({}),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() => _logs = data['logs'] ?? []);
      }
    } catch (e) {
      debugPrint('Erro ao carregar logs: ');
    }
  }

  Future<void> _loadStats() async {
    try {
      final response = await http.get(
        Uri.parse('/api/v1/security/audit/statistics?days=30'),
        headers: ApiConfig.headers,
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() => _stats = data);
      }
    } catch (e) {
      debugPrint('Erro ao carregar estatisticas: ');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Auditoria & Logs'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadData,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                _buildStatsCards(),
                _buildFilters(),
                Expanded(
                  child: _buildLogsList(),
                ),
              ],
            ),
    );
  }

  Widget _buildStatsCards() {
    final byAction = _stats['by_action'] ?? {};
    final bySeverity = _stats['by_severity'] ?? {};
    final failedLogins = _stats['failed_logins'] ?? 0;

    return Container(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          Row(
            children: [
              _buildStatCard('Total Eventos', (_stats['total_events'] ?? 0).toString(), Colors.blue),
              const SizedBox(width: 12),
              _buildStatCard('Falhas Login', failedLogins.toString(), Colors.red),
            ],
          ),
          const SizedBox(height: 12),
          if (bySeverity.isNotEmpty)
            Wrap(
              spacing: 8,
              children: bySeverity.entries.map<Widget>((entry) {
                Color color;
                switch (entry.key) {
                  case 'critical': color = Colors.red; break;
                  case 'error': color = Colors.orange; break;
                  case 'warning': color = Colors.yellow.shade700; break;
                  default: color = Colors.green;
                }
                return Chip(
                  label: Text(': ', style: const TextStyle(fontSize: 11)),
                  backgroundColor: color.withOpacity(0.2),
                );
              }).toList(),
            ),
        ],
      ),
    );
  }

  Widget _buildStatCard(String label, String value, Color color) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            children: [
              Text(value, style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: color)),
              Text(label, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFilters() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          Expanded(
            child: DropdownButtonFormField<String>(
              value: _selectedAction,
              hint: const Text('Acao'),
              isExpanded: true,
              items: [null, ..._actions].map((action) {
                return DropdownMenuItem(
                  value: action,
                  child: Text(action ?? 'Todas'),
                );
              }).toList(),
              onChanged: (value) {
                setState(() => _selectedAction = value);
                _loadLogs();
              },
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: DropdownButtonFormField<String>(
              value: _selectedSeverity,
              hint: const Text('Severidade'),
              isExpanded: true,
              items: [null, ..._severities].map((sev) {
                return DropdownMenuItem(
                  value: sev,
                  child: Text(sev?.toUpperCase() ?? 'Todas'),
                );
              }).toList(),
              onChanged: (value) {
                setState(() => _selectedSeverity = value);
                _loadLogs();
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLogsList() {
    if (_logs.isEmpty) {
      return const Center(child: Text('Nenhum log encontrado'));
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _logs.length,
      itemBuilder: (context, index) {
        final log = _logs[index];
        return _buildLogCard(log);
      },
    );
  }

  Widget _buildLogCard(dynamic log) {
    final severity = log['severity'] ?? 'info';
    final Color severityColor;
    final IconData severityIcon;

    switch (severity) {
      case 'critical':
        severityColor = Colors.red;
        severityIcon = Icons.error;
        break;
      case 'error':
        severityColor = Colors.orange;
        severityIcon = Icons.warning;
        break;
      case 'warning':
        severityColor = Colors.yellow.shade700;
        severityIcon = Icons.info;
        break;
      default:
        severityColor = Colors.green;
        severityIcon = Icons.check_circle;
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Icon(severityIcon, color: severityColor),
        title: Text(
          ' ',
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'User:  | IP: ',
              style: TextStyle(fontSize: 11, color: Colors.grey[600]),
            ),
            if (log['error_message'] != null)
              Text(
                'Erro: ',
                style: const TextStyle(fontSize: 11, color: Colors.red),
              ),
          ],
        ),
        trailing: Text(
          _formatDate(log['created_at']),
          style: TextStyle(fontSize: 11, color: Colors.grey[500]),
        ),
        onTap: () => _showLogDetails(log),
      ),
    );
  }

  String _formatDate(String? isoDate) {
    if (isoDate == null) return 'N/A';
    try {
      final dt = DateTime.parse(isoDate).toLocal();
      return '/ :';
    } catch (e) {
      return isoDate;
    }
  }

  void _showLogDetails(dynamic log) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Detalhes do Log'),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              _buildDetailRow('ID', log['id'].toString()),
              _buildDetailRow('Acao', log['action']),
              _buildDetailRow('Recurso', ' #'),
              _buildDetailRow('Usuario', log['user_id']?.toString() ?? 'System'),
              _buildDetailRow('IP', log['ip_address'] ?? 'N/A'),
              _buildDetailRow('Severidade', log['severity']),
              _buildDetailRow('Sucesso', log['success'] ? 'Sim' : 'Nao'),
              if (log['old_values'] != null)
                _buildDetailRow('Valores Antigos', jsonEncode(log['old_values'])),
              if (log['new_values'] != null)
                _buildDetailRow('Valores Novos', jsonEncode(log['new_values'])),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Fechar'),
          ),
        ],
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(
              label,
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
            ),
          ),
          Expanded(
            child: Text(value, style: const TextStyle(fontSize: 13)),
          ),
        ],
      ),
    );
  }
}
