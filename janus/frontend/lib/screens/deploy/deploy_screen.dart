// lib/screens/deploy/deploy_screen.dart
import 'package:flutter/material.dart';
import 'status_screen.dart';

class DeployScreen extends StatelessWidget {
  const DeployScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Deploy & DevOps'),
          bottom: const TabBar(
            tabs: [
              Tab(icon: Icon(Icons.health_and_safety), text: 'Status'),
              Tab(icon: Icon(Icons.settings), text: 'Configuracoes'),
            ],
          ),
        ),
        body: const TabBarView(
          children: [
            StatusScreen(),
            DeployConfigScreen(),
          ],
        ),
      ),
    );
  }
}

class DeployConfigScreen extends StatelessWidget {
  const DeployConfigScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildSectionTitle('Ambiente'),
        Card(
          child: Column(
            children: [
              ListTile(
                leading: const Icon(Icons.cloud, color: Colors.blue),
                title: const Text('Ambiente Atual'),
                subtitle: const Text('staging'),
                trailing: Chip(
                  label: const Text('STAGING'),
                  backgroundColor: Colors.blue[100],
                ),
              ),
              const Divider(height: 1),
              ListTile(
                leading: const Icon(Icons.dns, color: Colors.green),
                title: const Text('Docker Compose'),
                subtitle: const Text('8 servicos ativos'),
                trailing: const Icon(Icons.check_circle, color: Colors.green),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        _buildSectionTitle('Acoes'),
        _buildActionCard(
          context,
          'Reiniciar Servicos',
          Icons.restart_alt,
          Colors.orange,
          () => _showConfirmDialog(context, 'Reiniciar todos os servicos?'),
        ),
        _buildActionCard(
          context,
          'Forcar Backup',
          Icons.backup,
          Colors.blue,
          () => _showConfirmDialog(context, 'Executar backup agora?'),
        ),
        _buildActionCard(
          context,
          'Ver Logs',
          Icons.article,
          Colors.grey,
          () => debugPrint('Ver logs'),
        ),
        const SizedBox(height: 24),
        _buildSectionTitle('Documentacao'),
        _buildDocCard(
          'Docker Compose',
          'docker-compose.yml — Stack completa',
        ),
        _buildDocCard(
          'Nginx Config',
          'infra/nginx/nginx.conf — Reverse proxy',
        ),
        _buildDocCard(
          'CI/CD',
          '.github/workflows/ — GitHub Actions',
        ),
      ],
    );
  }

  Widget _buildSectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.bold,
          color: Colors.indigo,
        ),
      ),
    );
  }

  Widget _buildActionCard(BuildContext context, String title, IconData icon, Color color, VoidCallback onTap) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Icon(icon, color: color),
        title: Text(title),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    );
  }

  Widget _buildDocCard(String title, String description) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: const Icon(Icons.description, color: Colors.indigo),
        title: Text(title),
        subtitle: Text(description, style: const TextStyle(fontSize: 12)),
      ),
    );
  }

  void _showConfirmDialog(BuildContext context, String message) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Confirmar'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Comando enviado!')),
              );
            },
            child: const Text('Confirmar'),
          ),
        ],
      ),
    );
  }
}
