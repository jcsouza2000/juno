// lib/screens/security/gdpr_screen.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../../config/api_config.dart';

class GDPRScreen extends StatefulWidget {
  const GDPRScreen({Key? key}) : super(key: key);

  @override
  State<GDPRScreen> createState() => _GDPRScreenState();
}

class _GDPRScreenState extends State<GDPRScreen> {
  List<dynamic> _dsrs = [];
  Map<String, dynamic> _complianceReport = {};
  bool _isLoading = true;
  int _selectedTab = 0;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    await Future.wait([_loadDSRs(), _loadComplianceReport()]);
    setState(() => _isLoading = false);
  }

  Future<void> _loadDSRs() async {
    try {
      final response = await http.get(
        Uri.parse('/api/v1/security/dsr'),
        headers: ApiConfig.headers,
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() => _dsrs = data['dsrs'] ?? []);
      }
    } catch (e) {
      debugPrint('Erro ao carregar DSRs: ');
    }
  }

  Future<void> _loadComplianceReport() async {
    try {
      final response = await http.get(
        Uri.parse('/api/v1/security/compliance/report'),
        headers: ApiConfig.headers,
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() => _complianceReport = data);
      }
    } catch (e) {
      debugPrint('Erro ao carregar relatorio: ');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('LGPD / GDPR'),
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
                _buildComplianceHeader(),
                Expanded(
                  child: DefaultTabController(
                    length: 2,
                    child: Column(
                      children: [
                        const TabBar(
                          tabs: [
                            Tab(icon: Icon(Icons.request_page), text: 'Requisicoes'),
                            Tab(icon: Icon(Icons.verified), text: 'Compliance'),
                          ],
                        ),
                        Expanded(
                          child: TabBarView(
                            children: [
                              _buildDSRList(),
                              _buildComplianceTab(),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showCreateDSRDialog,
        icon: const Icon(Icons.add),
        label: const Text('Nova Requisicao'),
      ),
    );
  }

  Widget _buildComplianceHeader() {
    final dsrStats = _complianceReport['data_subject_requests'] ?? {};
    final consentStats = _complianceReport['consents'] ?? {};

    return Container(
      padding: const EdgeInsets.all(16),
      color: Colors.indigo[50],
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: _buildComplianceCard(
                  'DSRs Pendentes',
                  (dsrStats['pending'] ?? 0).toString(),
                  Icons.pending_actions,
                  Colors.orange,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildComplianceCard(
                  'Atrasadas',
                  (dsrStats['overdue'] ?? 0).toString(),
                  Icons.warning,
                  Colors.red,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildComplianceCard(
                  'Taxa Compliance',
                  '%',
                  Icons.check_circle,
                  Colors.green,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildComplianceCard(String label, String value, IconData icon, Color color) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Icon(icon, color: color, size: 28),
            const SizedBox(height: 8),
            Text(value, style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: color)),
            Text(label, style: TextStyle(fontSize: 11, color: Colors.grey[600]), textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }

  Widget _buildDSRList() {
    if (_dsrs.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.inbox, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text('Nenhuma requisicao encontrada', style: TextStyle(color: Colors.grey)),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _dsrs.length,
      itemBuilder: (context, index) {
        final dsr = _dsrs[index];
        return _buildDSRCard(dsr);
      },
    );
  }

  Widget _buildDSRCard(dynamic dsr) {
    final status = dsr['status'] ?? 'pending';
    final Color statusColor;
    final IconData statusIcon;

    switch (status) {
      case 'completed':
        statusColor = Colors.green;
        statusIcon = Icons.check_circle;
        break;
      case 'rejected':
        statusColor = Colors.red;
        statusIcon = Icons.cancel;
        break;
      default:
        statusColor = Colors.orange;
        statusIcon = Icons.pending;
    }

    final daysRemaining = dsr['days_remaining'] ?? 0;
    final isOverdue = status == 'pending' && daysRemaining <= 0;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: Icon(statusIcon, color: statusColor, size: 32),
        title: Text(
          ' - ',
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Status: ',
              style: TextStyle(color: statusColor, fontWeight: FontWeight.w500),
            ),
            if (isOverdue)
              const Text(
                'ATRASADA - URGENTE',
                style: TextStyle(color: Colors.red, fontWeight: FontWeight.bold, fontSize: 12),
              )
            else if (status == 'pending')
              Text(
                'Prazo:  dias',
                style: TextStyle(fontSize: 12, color: Colors.grey[600]),
              ),
          ],
        ),
        trailing: status == 'pending'
            ? PopupMenuButton<String>(
                onSelected: (value) {
                  if (value == 'approve') _processDSR(dsr['id'], true);
                  if (value == 'reject') _processDSR(dsr['id'], false);
                },
                itemBuilder: (context) => [
                  const PopupMenuItem(value: 'approve', child: Text('Aprovar')),
                  const PopupMenuItem(value: 'reject', child: Text('Rejeitar')),
                ],
              )
            : null,
      ),
    );
  }

  Widget _buildComplianceTab() {
    final recommendations = (_complianceReport['recommendations'] ?? []) as List;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Recomendacoes',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
          const Divider(),
          ...recommendations.whereType<String>().map<Widget>((rec) {
            return ListTile(
              leading: const Icon(Icons.lightbulb, color: Colors.amber),
              title: Text(rec, style: const TextStyle(fontSize: 14)),
            );
          }).toList(),
          const SizedBox(height: 24),
          const Text(
            'Consentimentos',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
          const Divider(),
          _buildConsentStats(),
        ],
      ),
    );
  }

  Widget _buildConsentStats() {
    final consentStats = _complianceReport['consents'] ?? {};

    return Row(
      children: [
        Expanded(
          child: _buildStatCard('Total', (consentStats['total'] ?? 0).toString(), Colors.blue),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildStatCard('Ativos', (consentStats['active'] ?? 0).toString(), Colors.green),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildStatCard('Revogados', (consentStats['withdrawn'] ?? 0).toString(), Colors.red),
        ),
      ],
    );
  }

  Widget _buildStatCard(String label, String value, Color color) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Text(value, style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: color)),
            Text(label, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
          ],
        ),
      ),
    );
  }

  void _showCreateDSRDialog() {
    final emailController = TextEditingController();
    final nameController = TextEditingController();
    final detailsController = TextEditingController();
    String selectedType = 'access';

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: const Text('Nova Requisicao LGPD'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  value: selectedType,
                  decoration: const InputDecoration(labelText: 'Tipo de Requisicao'),
                  items: const [
                    DropdownMenuItem(value: 'access', child: Text('Acesso aos dados')),
                    DropdownMenuItem(value: 'rectification', child: Text('Retificacao')),
                    DropdownMenuItem(value: 'erasure', child: Text('Exclusao (Direito ao Esquecimento)')),
                    DropdownMenuItem(value: 'portability', child: Text('Portabilidade')),
                    DropdownMenuItem(value: 'restriction', child: Text('Restricao de processamento')),
                  ],
                  onChanged: (value) => setState(() => selectedType = value!),
                ),
                TextField(
                  controller: emailController,
                  decoration: const InputDecoration(labelText: 'Email do Titular'),
                  keyboardType: TextInputType.emailAddress,
                ),
                TextField(
                  controller: nameController,
                  decoration: const InputDecoration(labelText: 'Nome do Titular'),
                ),
                TextField(
                  controller: detailsController,
                  decoration: const InputDecoration(labelText: 'Detalhes'),
                  maxLines: 3,
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancelar'),
            ),
            ElevatedButton(
              onPressed: () async {
                try {
                  final response = await http.post(
                    Uri.parse('/api/v1/security/dsr'),
                    headers: {...ApiConfig.headers, 'Content-Type': 'application/json'},
                    body: json.encode({
                      'request_type': selectedType,
                      'data_subject_email': emailController.text,
                      'data_subject_name': nameController.text,
                      'request_details': detailsController.text,
                    }),
                  );

                  if (response.statusCode == 200) {
                    Navigator.pop(context);
                    _loadData();
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Requisicao criada!')),
                    );
                  }
                } catch (e) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Erro: ')),
                  );
                }
              },
              child: const Text('Criar'),
            ),
          ],
        ),
      ),
    );
  }

  void _processDSR(int dsrId, bool approve) async {
    try {
      final response = await http.post(
        Uri.parse('/api/v1/security/dsr//process'),
        headers: {...ApiConfig.headers, 'Content-Type': 'application/json'},
        body: json.encode({'approve': approve}),
      );

      if (response.statusCode == 200) {
        _loadData();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(approve ? 'DSR aprovada!' : 'DSR rejeitada')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Erro: ')),
      );
    }
  }
}
