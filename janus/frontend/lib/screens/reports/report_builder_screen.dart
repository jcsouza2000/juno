// lib/screens/reports/report_builder_screen.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../../config/api_config.dart';

class ReportBuilderScreen extends StatefulWidget {
  final int? reportId; // null = novo relatório

  const ReportBuilderScreen({Key? key, this.reportId}) : super(key: key);

  @override
  State<ReportBuilderScreen> createState() => _ReportBuilderScreenState();
}

class _ReportBuilderScreenState extends State<ReportBuilderScreen> {
  final _nameController = TextEditingController();
  final _descriptionController = TextEditingController();
  
  String _selectedDataSource = 'sales_by_period';
  String _selectedReportType = 'table';
  List<Map<String, dynamic>> _columns = [];
  List<Map<String, dynamic>> _filters = [];
  List<Map<String, dynamic>> _sorts = [];
  
  List<dynamic> _previewData = [];
  bool _isLoading = false;
  bool _showPreview = false;

  final List<String> _dataSources = [
    'sales_by_period',
    'sales_by_product',
    'inventory_status',
    'customers',
    'products',
    'financial_summary'
  ];

  final List<String> _reportTypes = ['table', 'chart', 'pivot'];

  @override
  void initState() {
    super.initState();
    if (widget.reportId != null) {
      _loadReport();
    }
  }

  Future<void> _loadReport() async {
    // Carregar relatório existente para edição
  }

  Future<void> _previewReport() async {
    setState(() {
      _isLoading = true;
      _showPreview = true;
    });

    try {
      final body = {
        'name': _nameController.text,
        'description': _descriptionController.text,
        'report_type': _selectedReportType,
        'data_source': _selectedDataSource,
        'column_config': _columns,
        'filter_config': _filters,
        'sort_config': _sorts,
      };

      // Primeiro criar/salvar
      final saveResponse = await http.post(
        Uri.parse('${ApiConfig.baseUrl}/api/v1/reports/definitions'),
        headers: {...ApiConfig.headers, 'Content-Type': 'application/json'},
        body: json.encode(body),
      );

      if (saveResponse.statusCode == 200) {
        final saved = json.decode(saveResponse.body);
        final reportId = saved['id'];

        // Executar para preview
        final execResponse = await http.post(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/reports/definitions/$reportId/execute'),
          headers: {...ApiConfig.headers, 'Content-Type': 'application/json'},
          body: json.encode({
            'parameters': {},
            'page': 1,
            'page_size': 10,
          }),
        );

        if (execResponse.statusCode == 200) {
          final result = json.decode(execResponse.body);
          setState(() {
            _previewData = result['data'] ?? [];
            _isLoading = false;
          });
        }
      }
    } catch (e) {
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Erro: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.reportId == null ? 'Novo Relatório' : 'Editar Relatório'),
        actions: [
          TextButton.icon(
            onPressed: _previewReport,
            icon: const Icon(Icons.visibility, color: Colors.white),
            label: const Text('Preview', style: TextStyle(color: Colors.white)),
          ),
          TextButton.icon(
            onPressed: _saveReport,
            icon: const Icon(Icons.save, color: Colors.white),
            label: const Text('Salvar', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
      body: Row(
        children: [
          // Painel de configuração (esquerda)
          Container(
            width: 350,
            decoration: BoxDecoration(
              color: Colors.grey[50],
              border: Border(right: BorderSide(color: Colors.grey[300]!)),
            ),
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildSectionTitle('Configurações Básicas'),
                  TextField(
                    controller: _nameController,
                    decoration: const InputDecoration(
                      labelText: 'Nome do Relatório',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _descriptionController,
                    decoration: const InputDecoration(
                      labelText: 'Descrição',
                      border: OutlineInputBorder(),
                    ),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 16),
                  
                  _buildSectionTitle('Fonte de Dados'),
                  DropdownButtonFormField<String>(
                    value: _selectedDataSource,
                    decoration: const InputDecoration(
                      border: OutlineInputBorder(),
                    ),
                    items: _dataSources.map((source) {
                      return DropdownMenuItem(
                        value: source,
                        child: Text(source.replaceAll('_', ' ').toUpperCase()),
                      );
                    }).toList(),
                    onChanged: (value) => setState(() => _selectedDataSource = value!),
                  ),
                  const SizedBox(height: 16),
                  
                  _buildSectionTitle('Tipo de Relatório'),
                  DropdownButtonFormField<String>(
                    value: _selectedReportType,
                    decoration: const InputDecoration(
                      border: OutlineInputBorder(),
                    ),
                    items: _reportTypes.map((type) {
                      return DropdownMenuItem(
                        value: type,
                        child: Text(type.toUpperCase()),
                      );
                    }).toList(),
                    onChanged: (value) => setState(() => _selectedReportType = value!),
                  ),
                  const SizedBox(height: 24),
                  
                  _buildSectionTitle('Colunas'),
                  ..._columns.asMap().entries.map((entry) {
                    final idx = entry.key;
                    final col = entry.value;
                    return ListTile(
                      dense: true,
                      title: Text(col['label'] ?? col['field'] ?? ''),
                      subtitle: Text(col['type'] ?? 'string'),
                      trailing: IconButton(
                        icon: const Icon(Icons.delete, size: 18, color: Colors.red),
                        onPressed: () => setState(() => _columns.removeAt(idx)),
                      ),
                    );
                  }).toList(),
                  OutlinedButton.icon(
                    onPressed: _addColumn,
                    icon: const Icon(Icons.add),
                    label: const Text('Adicionar Coluna'),
                  ),
                  const SizedBox(height: 24),
                  
                  _buildSectionTitle('Filtros'),
                  ..._filters.asMap().entries.map((entry) {
                    final idx = entry.key;
                    final filter = entry.value;
                    return ListTile(
                      dense: true,
                      title: Text('${filter['field']} ${filter['operator']}'),
                      trailing: IconButton(
                        icon: const Icon(Icons.delete, size: 18, color: Colors.red),
                        onPressed: () => setState(() => _filters.removeAt(idx)),
                      ),
                    );
                  }).toList(),
                  OutlinedButton.icon(
                    onPressed: _addFilter,
                    icon: const Icon(Icons.add),
                    label: const Text('Adicionar Filtro'),
                  ),
                ],
              ),
            ),
          ),
          
          // Preview (direita)
          Expanded(
            child: _showPreview
                ? _buildPreviewPanel()
                : const Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.preview, size: 64, color: Colors.grey),
                        SizedBox(height: 16),
                        Text(
                          'Clique em Preview para ver o resultado',
                          style: TextStyle(color: Colors.grey),
                        ),
                      ],
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.bold,
          color: Colors.grey,
        ),
      ),
    );
  }

  Widget _buildPreviewPanel() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_previewData.isEmpty) {
      return const Center(
        child: Text('Nenhum dado para preview', style: TextStyle(color: Colors.grey)),
      );
    }

    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          color: Colors.blue[50],
          child: Row(
            children: [
              const Icon(Icons.visibility, color: Colors.blue),
              const SizedBox(width: 8),
              Text(
                'Preview (${_previewData.length} registros)',
                style: const TextStyle(color: Colors.blue, fontWeight: FontWeight.bold),
              ),
              const Spacer(),
              TextButton.icon(
                onPressed: () => _exportReport('pdf'),
                icon: const Icon(Icons.picture_as_pdf, size: 18),
                label: const Text('PDF'),
              ),
              TextButton.icon(
                onPressed: () => _exportReport('excel'),
                icon: const Icon(Icons.table_chart, size: 18),
                label: const Text('Excel'),
              ),
            ],
          ),
        ),
        Expanded(
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: DataTable(
              columns: _previewData.isNotEmpty
                  ? _previewData.first.keys.map<DataColumn>((key) {
                      return DataColumn(
                        label: Text(
                          key.toString().toUpperCase(),
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                      );
                    }).toList()
                  : [],
              rows: _previewData.map<DataRow>((row) {
                return DataRow(
                  cells: row.values.map<DataCell>((value) {
                    return DataCell(Text(value?.toString() ?? ''));
                  }).toList(),
                );
              }).toList(),
            ),
          ),
        ),
      ],
    );
  }

  void _addColumn() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Adicionar Coluna'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              decoration: const InputDecoration(labelText: 'Campo'),
              onSubmitted: (field) {
                setState(() {
                  _columns.add({
                    'field': field,
                    'label': field.replaceAll('_', ' ').toUpperCase(),
                    'type': 'string',
                  });
                });
                Navigator.pop(context);
              },
            ),
          ],
        ),
      ),
    );
  }

  void _addFilter() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Adicionar Filtro'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              decoration: const InputDecoration(labelText: 'Campo'),
              onSubmitted: (field) {
                setState(() {
                  _filters.add({
                    'field': field,
                    'operator': 'eq',
                    'param_name': field,
                  });
                });
                Navigator.pop(context);
              },
            ),
          ],
        ),
      ),
    );
  }

  void _saveReport() {
    // Implementar salvamento
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Relatório salvo com sucesso!')),
    );
  }

  void _exportReport(String format) {
    // Implementar exportação
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Exportação para ${format.toUpperCase()} iniciada')),
    );
  }
}
