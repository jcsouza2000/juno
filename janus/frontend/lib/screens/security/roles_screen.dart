// lib/screens/security/roles_screen.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../../config/api_config.dart';

class RolesScreen extends StatefulWidget {
  const RolesScreen({Key? key}) : super(key: key);

  @override
  State<RolesScreen> createState() => _RolesScreenState();
}

class _RolesScreenState extends State<RolesScreen> {
  List<dynamic> _roles = [];
  List<dynamic> _permissions = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    await Future.wait([_loadRoles(), _loadPermissions()]);
    setState(() => _isLoading = false);
  }

  Future<void> _loadRoles() async {
    try {
      final response = await http.get(
        Uri.parse('/api/v1/security/roles'),
        headers: ApiConfig.headers,
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() => _roles = data['roles'] ?? []);
      }
    } catch (e) {
      debugPrint('Erro ao carregar papeis: ');
    }
  }

  Future<void> _loadPermissions() async {
    try {
      final response = await http.get(
        Uri.parse('/api/v1/security/permissions/available'),
        headers: ApiConfig.headers,
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() => _permissions = data['permissions'] ?? []);
      }
    } catch (e) {
      debugPrint('Erro ao carregar permissoes: ');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Gestao de Papeis (RBAC)'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: _showCreateRoleDialog,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _roles.length,
              itemBuilder: (context, index) {
                final role = _roles[index];
                return _buildRoleCard(role);
              },
            ),
    );
  }

  Widget _buildRoleCard(dynamic role) {
    final perms = (role['permissions'] ?? []) as List;
    final isSystem = role['is_system_role'] ?? false;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ExpansionTile(
        leading: Icon(
          isSystem ? Icons.shield : Icons.person_outline,
          color: isSystem ? Colors.blue : Colors.grey,
        ),
        title: Text(
          role['name'],
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Text(
          role['description'] ?? '',
          style: TextStyle(fontSize: 12, color: Colors.grey[600]),
        ),
        trailing: isSystem
            ? const Chip(label: Text('Sistema', style: TextStyle(fontSize: 10)))
            : IconButton(
                icon: const Icon(Icons.delete, color: Colors.red),
                onPressed: () => _deleteRole(role['id']),
              ),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Divider(),
                const Text(
                  'Permissoes:',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: perms.map<Widget>((perm) {
                    return Chip(
                      label: Text(
                        perm.toString().split('.').join(' ').toUpperCase(),
                        style: const TextStyle(fontSize: 11),
                      ),
                      backgroundColor: Colors.blue[50],
                    );
                  }).toList(),
                ),
                if (!isSystem) ...[
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => _showAssignRoleDialog(role['id']),
                          icon: const Icon(Icons.person_add),
                          label: const Text('Atribuir a Usuario'),
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _showCreateRoleDialog() {
    final nameController = TextEditingController();
    final descController = TextEditingController();
    final Set<String> selectedPerms = {};

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: const Text('Novo Papel'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameController,
                  decoration: const InputDecoration(labelText: 'Nome'),
                ),
                TextField(
                  controller: descController,
                  decoration: const InputDecoration(labelText: 'Descricao'),
                ),
                const SizedBox(height: 16),
                const Text('Permissoes:', style: TextStyle(fontWeight: FontWeight.bold)),
                ..._permissions.map<Widget>((perm) {
                  final code = perm['code'] as String;
                  return CheckboxListTile(
                    title: Text(' - '),
                    subtitle: Text(code, style: const TextStyle(fontSize: 11)),
                    value: selectedPerms.contains(code),
                    onChanged: (checked) {
                      setState(() {
                        if (checked == true) {
                          selectedPerms.add(code);
                        } else {
                          selectedPerms.remove(code);
                        }
                      });
                    },
                  );
                }).toList(),
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
                    Uri.parse('/api/v1/security/roles'),
                    headers: {...ApiConfig.headers, 'Content-Type': 'application/json'},
                    body: json.encode({
                      'name': nameController.text,
                      'description': descController.text,
                      'permissions': selectedPerms.toList(),
                    }),
                  );

                  if (response.statusCode == 200) {
                    Navigator.pop(context);
                    _loadRoles();
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Papel criado com sucesso!')),
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

  void _showAssignRoleDialog(int roleId) {
    final userIdController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Atribuir Papel'),
        content: TextField(
          controller: userIdController,
          decoration: const InputDecoration(labelText: 'ID do Usuario'),
          keyboardType: TextInputType.number,
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
                  Uri.parse('/api/v1/security/roles/assign'),
                  headers: {...ApiConfig.headers, 'Content-Type': 'application/json'},
                  body: json.encode({
                    'user_id': int.parse(userIdController.text),
                    'role_id': roleId,
                  }),
                );

                if (response.statusCode == 200) {
                  Navigator.pop(context);
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Papel atribuido!')),
                  );
                }
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Erro: ')),
                );
              }
            },
            child: const Text('Atribuir'),
          ),
        ],
      ),
    );
  }

  void _deleteRole(int roleId) async {
    // Implementar delete
  }
}
