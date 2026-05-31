// lib/screens/security/security_dashboard_screen.dart
import 'package:flutter/material.dart';
import 'roles_screen.dart';
import 'audit_screen.dart';
import 'gdpr_screen.dart';
import 'security_settings_screen.dart';

class SecurityDashboardScreen extends StatelessWidget {
  const SecurityDashboardScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Central de Seguranca'),
      ),
      body: GridView.count(
        padding: const EdgeInsets.all(16),
        crossAxisCount: 2,
        mainAxisSpacing: 16,
        crossAxisSpacing: 16,
        children: [
          _buildSecurityCard(
            context,
            'RBAC & Papeis',
            Icons.shield,
            Colors.blue,
            () => Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => const RolesScreen()),
            ),
          ),
          _buildSecurityCard(
            context,
            'Auditoria',
            Icons.receipt_long,
            Colors.orange,
            () => Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => const AuditScreen()),
            ),
          ),
          _buildSecurityCard(
            context,
            'LGPD / GDPR',
            Icons.privacy_tip,
            Colors.green,
            () => Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => const GDPRScreen()),
            ),
          ),
          _buildSecurityCard(
            context,
            'Configuracoes',
            Icons.settings,
            Colors.purple,
            () => Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => const SecuritySettingsScreen()),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSecurityCard(
    BuildContext context,
    String title,
    IconData icon,
    Color color,
    VoidCallback onTap,
  ) {
    return Card(
      elevation: 4,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                color: color.withOpacity(0.1),
                borderRadius: BorderRadius.circular(32),
              ),
              child: Icon(icon, size: 32, color: color),
            ),
            const SizedBox(height: 16),
            Text(
              title,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
