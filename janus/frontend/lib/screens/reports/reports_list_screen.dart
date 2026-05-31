// lib/screens/reports/reports_list_screen.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../../config/api_config.dart';
import 'report_builder_screen.dart';
import 'dashboard_viewer_screen.dart';

class ReportsListScreen extends StatefulWidget {
  const ReportsListScreen({Key? key}) : super(key: key);

  @override
  State<ReportsListScreen> createState() => _ReportsListScreenState();
}

class _ReportsListScreenState extends State<ReportsListScreen> {
  List<dynamic> _reports = [];
  List<dynamic> _dashboards = [];
  List<dynamic> _templates = [];
  bool _isLoading = true;
  int _selectedTab = 0;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    await Future.wait([
      _loadReports(),
      _loadDashboards(),
      _loadTemplates(),
    ]);
    setState(() => _isLoading = false);
  }

  Future<void> _loadReports() async {
    try {
      final response = await http.get(
        Uri.parse('${ApiConfig.baseUrl}/api/v1/reports/definitions'),
        headers: ApiConfig.headers,
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() => _reports = data['reports'] ?? []);
      }
    } catch (e) {
      debugPrint('Erro ao carregar relatórios: $e');
    }
  }

  Future<void> _loadDashboards() async {
    try {
      final response = await http.get(
        Uri.parse('${ApiConfig.baseUrl}/api/v1/reports/dashboards'),
        headers: ApiConfig.headers,
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() => _dashboards = data['dashboards'] ?? []);
      }
    } catch (e) {
      debugPrint('Erro ao carregar dashboards: $e');
    }
  }

  Future<void> _loadTemplates() async {
    try {
      final response = await http.get(
        Uri.parse('${ApiConfig.baseUrl}/api/v1/reports/templates'),
        headers: ApiConfig.headers,
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() => _templates = data['templates'] ?? []);
      }
    } catch (e) {
      debugPrint('Erro ao carregar templates: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Relatórios & BI'),
        bottom: TabBar(
          onTap: (index) => setState(() => _selectedTab = index),
          tabs: const [
            Tab(icon: Icon(Icons.insert_drive_file), text: 'Relatórios'),
            Tab(icon: Icon(Icons.dashboard), text: 'Dashboards'),
            Tab(icon: Icon(Icons.library_books), text: 'Templates'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              children: [
                _buildReportsTab(),
                _buildDashboardsTab(),
                _buildTemplatesTab(),
              ],
            ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          if (_selectedTab == 0) {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => const ReportBuilderScreen()),
            );
          } else if (_selectedTab == 1) {
            // Criar dashboard
          }
        },
        icon: const Icon(Icons.add),
        label: Text(_selectedTab == 0 ? 'Relatório' : 'Dashboard'),
      ),
    );
  }

  Widget _buildReportsTab() {
    if (_reports.isEmpty) {
      return _buildEmptyState('Nenhum relatório criado', 'Crie seu primeiro relatório');
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _reports.length,
      itemBuilder: (context, index) {
        final report = _reports[index];
        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: _getReportTypeColor(report['report_type']).withOpacity(0.2),
              child: Icon(
                _getReportTypeIcon(report['report_type']),
                color: _getReportTypeColor(report['report_type']),
              ),
            ),
            title: Text(report['name']),
            subtitle: Text(
              '${report['report_type']} • ${report['data_source']} • ${report['execution_count']} execuções',
              style: TextStyle(fontSize: 12, color: Colors.grey[600]),
            ),
            trailing: PopupMenuButton<String>(
              onSelected: (value) {
                if (value == 'view') _viewReport(report['id']);
                if (value == 'edit') _editReport(report['id']);
                if (value == 'delete') _deleteReport(report['id']);
              },
              itemBuilder: (context) => [
                const PopupMenuItem(value: 'view', child: Text('Visualizar')),
                const PopupMenuItem(value: 'edit', child: Text('Editar')),
                const PopupMenuItem(value: 'export', child: Text('Exportar')),
                const PopupMenuItem(value: 'delete', child: Text('Excluir', style: TextStyle(color: Colors.red))),
              ],
            ),
            onTap: () => _viewReport(report['id']),
          ),
        );
      },
    );
  }

  Widget _buildDashboardsTab() {
    if (_dashboards.isEmpty) {
      return _buildEmptyState('Nenhum dashboard criado', 'Crie seu primeiro dashboard');
    }

    return GridView.builder(
      padding: const EdgeInsets.all(16),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        childAspectRatio: 1.2,
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
      ),
      itemCount: _dashboards.length,
      itemBuilder: (context, index) {
        final dashboard = _dashboards[index];
        return Card(
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: () => _viewDashboard(dashboard['id']),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Icon(
                        Icons.dashboard,
                        color: Theme.of(context).primaryColor,
                        size: 32,
                      ),
                      if (dashboard['is_default'] == true)
                        const Chip(
                          label: Text('Padrão', style: TextStyle(fontSize: 10)),
                          padding: EdgeInsets.zero,
                        ),
                    ],
                  ),
                  const Spacer(),
                  Text(
                    dashboard['name'],
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${dashboard['widget_count']} widgets',
                    style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildTemplatesTab() {
    if (_templates.isEmpty) {
      return _buildEmptyState('Nenhum template disponível', 'Templates serão carregados do servidor');
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _templates.length,
      itemBuilder: (context, index) {
        final template = _templates[index];
        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: ListTile(
            leading: const Icon(Icons.description, color: Colors.indigo),
            title: Text(template['name']),
            subtitle: Text(template['description'] ?? ''),
            trailing: ElevatedButton.icon(
              onPressed: () => _createFromTemplate(template['key']),
              icon: const Icon(Icons.add, size: 16),
              label: const Text('Usar'),
            ),
          ),
        );
      },
    );
  }

  Widget _buildEmptyState(String title, String subtitle) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.insert_drive_file_outlined, size: 64, color: Colors.grey[400]),
          const SizedBox(height: 16),
          Text(title, style: TextStyle(fontSize: 18, color: Colors.grey[600])),
          const SizedBox(height: 8),
          Text(subtitle, style: TextStyle(color: Colors.grey[500])),
        ],
      ),
    );
  }

  Color _getReportTypeColor(String type) {
    switch (type) {
      case 'table': return Colors.blue;
      case 'chart': return Colors.green;
      case 'pivot': return Colors.purple;
      case 'dashboard': return Colors.orange;
      default: return Colors.grey;
    }
  }

  IconData _getReportTypeIcon(String type) {
    switch (type) {
      case 'table': return Icons.table_chart;
      case 'chart': return Icons.bar_chart;
      case 'pivot': return Icons.pivot_table_chart;
      case 'dashboard': return Icons.dashboard;
      default: return Icons.insert_drive_file;
    }
  }

  void _viewReport(int reportId) {
    // Navegar para visualização do relatório
  }

  void _editReport(int reportId) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (context) => ReportBuilderScreen(reportId: reportId)),
    );
  }

  void _deleteReport(int reportId) async {
    // Confirmar e deletar
  }

  void _viewDashboard(int dashboardId) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (context) => DashboardViewerScreen(dashboardId: dashboardId)),
    );
  }

  void _createFromTemplate(String templateKey) async {
    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.baseUrl}/api/v1/reports/templates/$templateKey/create'),
        headers: ApiConfig.headers,
      );

      if (response.statusCode == 200) {
        _loadReports();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Relatório criado do template!')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Erro: $e')),
      );
    }
  }
}
