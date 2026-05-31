// lib/screens/security/security_settings_screen.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../../config/api_config.dart';

class SecuritySettingsScreen extends StatefulWidget {
  const SecuritySettingsScreen({Key? key}) : super(key: key);

  @override
  State<SecuritySettingsScreen> createState() => _SecuritySettingsScreenState();
}

class _SecuritySettingsScreenState extends State<SecuritySettingsScreen> {
  Map<String, dynamic> _settings = {};
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    try {
      final response = await http.get(
        Uri.parse('/api/v1/security/settings'),
        headers: ApiConfig.headers,
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() {
          _settings = data;
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _saveSettings() async {
    try {
      final response = await http.put(
        Uri.parse('/api/v1/security/settings'),
        headers: {...ApiConfig.headers, 'Content-Type': 'application/json'},
        body: json.encode(_settings),
      );

      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Configuracoes salvas!')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Erro: ')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Configuracoes de Seguranca'),
        actions: [
          IconButton(
            icon: const Icon(Icons.save),
            onPressed: _saveSettings,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildSectionTitle('Autenticacao'),
                  SwitchListTile(
                    title: const Text('MFA Obrigatorio'),
                    subtitle: const Text('Exige autenticacao de dois fatores'),
                    value: _settings['mfa_required'] ?? false,
                    onChanged: (value) => setState(() => _settings['mfa_required'] = value),
                  ),
                  _buildNumberField(
                    'Timeout da Sessao (minutos)',
                    _settings['session_timeout_minutes'] ?? 30,
                    (val) => _settings['session_timeout_minutes'] = val,
                  ),
                  _buildNumberField(
                    'Maximo de Tentativas de Login',
                    _settings['max_login_attempts'] ?? 5,
                    (val) => _settings['max_login_attempts'] = val,
                  ),
                  _buildNumberField(
                    'Duracao do Bloqueio (minutos)',
                    _settings['lockout_duration_minutes'] ?? 30,
                    (val) => _settings['lockout_duration_minutes'] = val,
                  ),
                  _buildNumberField(
                    'Troca de Senha Obrigatoria (dias)',
                    _settings['require_password_change_days'] ?? 90,
                    (val) => _settings['require_password_change_days'] = val,
                  ),
                  const Divider(height: 32),
                  _buildSectionTitle('Retencao de Dados'),
                  _buildNumberField(
                    'Retencao de Dados (dias)',
                    _settings['data_retention_days'] ?? 2555,
                    (val) => _settings['data_retention_days'] = val,
                  ),
                  const Divider(height: 32),
                  _buildSectionTitle('Criptografia'),
                  SwitchListTile(
                    title: const Text('Criptografia em Repouso'),
                    subtitle: const Text('Dados criptografados no banco'),
                    value: _settings['encryption_at_rest'] ?? true,
                    onChanged: (value) => setState(() => _settings['encryption_at_rest'] = value),
                  ),
                  SwitchListTile(
                    title: const Text('Criptografia em Transito'),
                    subtitle: const Text('HTTPS obrigatorio'),
                    value: _settings['encryption_in_transit'] ?? true,
                    onChanged: (value) => setState(() => _settings['encryption_in_transit'] = value),
                  ),
                  const Divider(height: 32),
                  _buildSectionTitle('Compliance'),
                  SwitchListTile(
                    title: const Text('GDPR (Europeu)'),
                    subtitle: const Text('Conformidade com GDPR'),
                    value: _settings['gdpr_enabled'] ?? true,
                    onChanged: (value) => setState(() => _settings['gdpr_enabled'] = value),
                  ),
                  SwitchListTile(
                    title: const Text('LGPD (Brasil)'),
                    subtitle: const Text('Conformidade com LGPD'),
                    value: _settings['lgpd_enabled'] ?? true,
                    onChanged: (value) => setState(() => _settings['lgpd_enabled'] = value),
                  ),
                  const SizedBox(height: 32),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: _saveSettings,
                      icon: const Icon(Icons.save),
                      label: const Text('SALVAR CONFIGURACOES'),
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 16),
                      ),
                    ),
                  ),
                ],
              ),
            ),
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

  Widget _buildNumberField(String label, int value, Function(int) onChanged) {
    return ListTile(
      title: Text(label),
      trailing: SizedBox(
        width: 80,
        child: TextField(
          controller: TextEditingController(text: value.toString()),
          keyboardType: TextInputType.number,
          textAlign: TextAlign.center,
          decoration: const InputDecoration(
            border: OutlineInputBorder(),
            contentPadding: EdgeInsets.symmetric(horizontal: 8),
          ),
          onSubmitted: (text) => onChanged(int.tryParse(text) ?? value),
        ),
      ),
    );
  }
}
