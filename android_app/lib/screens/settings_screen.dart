import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/settings_model.dart';
import '../services/api_service.dart';
import 'build_screen.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _urlCtrl;
  late final TextEditingController _ownerCtrl;
  late final TextEditingController _anthropicCtrl;
  late final TextEditingController _openaiCtrl;
  late final TextEditingController _geminiCtrl;

  bool _saving = false;
  bool _testing = false;
  String? _saveMsg;
  bool _saveMsgOk = true;

  @override
  void initState() {
    super.initState();
    final s = context.read<SettingsModel>();
    _urlCtrl = TextEditingController(text: s.backendUrl);
    _ownerCtrl = TextEditingController(text: s.ownerName);
    _anthropicCtrl = TextEditingController(text: s.anthropicKey);
    _openaiCtrl = TextEditingController(text: s.openaiKey);
    _geminiCtrl = TextEditingController(text: s.geminiKey);
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    _ownerCtrl.dispose();
    _anthropicCtrl.dispose();
    _openaiCtrl.dispose();
    _geminiCtrl.dispose();
    super.dispose();
  }

  Future<void> _testConnection() async {
    setState(() => _testing = true);
    final api = ApiService(baseUrl: _urlCtrl.text.trim());
    final ok = await api.checkHealth();
    if (mounted) {
      setState(() {
        _testing = false;
        _saveMsg = ok
            ? '✓ Connected to backend.'
            : '✗ Cannot reach backend. Is it running?';
        _saveMsgOk = ok;
      });
    }
  }

  Future<void> _save() async {
    final settings = context.read<SettingsModel>();
    setState(() {
      _saving = true;
      _saveMsg = null;
    });

    await settings.save(
      backendUrl: _urlCtrl.text.trim(),
      ownerName: _ownerCtrl.text.trim(),
      anthropicKey: _anthropicCtrl.text.trim(),
      openaiKey: _openaiCtrl.text.trim(),
      geminiKey: _geminiCtrl.text.trim(),
    );

    // Sync keys to backend
    try {
      final api = ApiService(baseUrl: _urlCtrl.text.trim());
      final body = <String, dynamic>{};
      if (_ownerCtrl.text.trim().isNotEmpty) {
        body['owner_name'] = _ownerCtrl.text.trim();
      }
      if (_anthropicCtrl.text.trim().isNotEmpty) {
        body['anthropic_api_key'] = _anthropicCtrl.text.trim();
      }
      if (_openaiCtrl.text.trim().isNotEmpty) {
        body['openai_api_key'] = _openaiCtrl.text.trim();
      }
      if (_geminiCtrl.text.trim().isNotEmpty) {
        body['gemini_api_key'] = _geminiCtrl.text.trim();
      }
      if (body.isNotEmpty) await api.updateSettings(body);
      if (mounted) {
        setState(() {
          _saveMsg = '✓ Settings saved and synced to backend.';
          _saveMsgOk = true;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _saveMsg = '⚠ Saved locally. Backend sync failed: $e';
          _saveMsgOk = false;
        });
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final settings = context.watch<SettingsModel>();
    final scheme = Theme.of(context).colorScheme;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // ── Connection ──────────────────────────────────────────────────────
        _Section('Backend Connection'),
        _FieldTile(
          ctrl: _urlCtrl,
          label: 'Backend URL',
          hint: 'http://127.0.0.1:8000',
          icon: Icons.dns_outlined,
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _testing ? null : _testConnection,
                icon: _testing
                    ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.network_check, size: 16),
                label: const Text('Test connection'),
              ),
            ),
          ],
        ),

        const SizedBox(height: 20),

        // ── Profile ─────────────────────────────────────────────────────────
        _Section('Profile'),
        _FieldTile(
          ctrl: _ownerCtrl,
          label: 'Your name',
          icon: Icons.person_outline,
        ),

        const SizedBox(height: 20),

        // ── API Keys ────────────────────────────────────────────────────────
        _Section('API Keys'),
        _SecretField(
          ctrl: _anthropicCtrl,
          label: 'Anthropic API Key',
          hint: 'sk-ant-…',
        ),
        const SizedBox(height: 12),
        _SecretField(
          ctrl: _openaiCtrl,
          label: 'OpenAI API Key',
          hint: 'sk-…',
        ),
        const SizedBox(height: 12),
        _SecretField(
          ctrl: _geminiCtrl,
          label: 'Google Gemini API Key',
          hint: 'AI…',
        ),

        const SizedBox(height: 20),

        // ── Default provider ────────────────────────────────────────────────
        _Section('Default Provider'),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: SettingsModel.providerLabels.entries.map((e) {
            final active = settings.provider == e.key;
            return ChoiceChip(
              label: Text(e.value),
              selected: active,
              onSelected: (_) => settings.setProvider(e.key),
              selectedColor: scheme.primaryContainer,
            );
          }).toList(),
        ),
        const SizedBox(height: 12),
        if (settings.availableModels.isNotEmpty)
          DropdownButtonFormField<String>(
            value: settings.availableModels.contains(settings.model)
                ? settings.model
                : settings.availableModels.first,
            decoration: const InputDecoration(
              labelText: 'Default Model',
              border: OutlineInputBorder(),
            ),
            items: settings.availableModels
                .map((m) => DropdownMenuItem(value: m, child: Text(m)))
                .toList(),
            onChanged: (m) {
              if (m != null) settings.setModel(m);
            },
          ),

        const SizedBox(height: 28),

        // ── Save button ─────────────────────────────────────────────────────
        if (_saveMsg != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: _saveMsgOk
                    ? scheme.primaryContainer
                    : scheme.errorContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                _saveMsg!,
                style: TextStyle(
                  color: _saveMsgOk
                      ? scheme.onPrimaryContainer
                      : scheme.onErrorContainer,
                  fontSize: 13,
                ),
              ),
            ),
          ),

        FilledButton.icon(
          onPressed: _saving ? null : _save,
          icon: _saving
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.save_outlined),
          label: const Text('Save Settings'),
        ),

        const SizedBox(height: 20),

        // ── Build pipeline ───────────────────────────────────────────────────
        _Section('Build Pipeline'),
        const SizedBox(height: 8),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton.icon(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const BuildScreen()),
            ),
            icon: const Icon(Icons.rocket_launch_outlined),
            label: const Text('Trigger APK Build (git push → CI)'),
          ),
        ),

        const SizedBox(height: 24),

        // ── About ────────────────────────────────────────────────────────────
        _Section('About'),
        const SizedBox(height: 8),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('ARIA v10',
                    style: Theme.of(context)
                        .textTheme
                        .titleMedium
                        ?.copyWith(fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                Text(
                  'Local AI Assistant\nFlutter + Python FastAPI + Termux',
                  style: TextStyle(
                      color: scheme.outline,
                      fontSize: 12,
                      height: 1.5),
                ),
                const SizedBox(height: 8),
                const Divider(),
                const SizedBox(height: 8),
                _AboutRow('Backend', 'Python FastAPI on port 8000'),
                _AboutRow('LLM Providers', 'Anthropic · OpenAI · Gemini'),
                _AboutRow('Memory', 'SQLite via backend'),
                _AboutRow(
                    'Tools', '30+ Termux API & system tools'),
              ],
            ),
          ),
        ),
        const SizedBox(height: 32),
      ],
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  const _Section(this.title);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Text(
        title.toUpperCase(),
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: Theme.of(context).colorScheme.primary,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.2,
            ),
      ),
    );
  }
}

class _FieldTile extends StatelessWidget {
  final TextEditingController ctrl;
  final String label;
  final String? hint;
  final IconData icon;

  const _FieldTile({
    required this.ctrl,
    required this.label,
    this.hint,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: ctrl,
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixIcon: Icon(icon),
        border: const OutlineInputBorder(),
      ),
    );
  }
}

class _SecretField extends StatefulWidget {
  final TextEditingController ctrl;
  final String label;
  final String hint;

  const _SecretField({
    required this.ctrl,
    required this.label,
    required this.hint,
  });

  @override
  State<_SecretField> createState() => _SecretFieldState();
}

class _SecretFieldState extends State<_SecretField> {
  bool _hidden = true;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: widget.ctrl,
      obscureText: _hidden,
      decoration: InputDecoration(
        labelText: widget.label,
        hintText: widget.hint,
        prefixIcon: const Icon(Icons.key_outlined),
        border: const OutlineInputBorder(),
        suffixIcon: IconButton(
          icon: Icon(
              _hidden ? Icons.visibility_off_outlined : Icons.visibility_outlined,
              size: 18),
          onPressed: () => setState(() => _hidden = !_hidden),
          tooltip: _hidden ? 'Show' : 'Hide',
        ),
      ),
    );
  }
}

class _AboutRow extends StatelessWidget {
  final String label;
  final String value;
  const _AboutRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 110,
            child: Text(
              label,
              style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).colorScheme.outline,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }
}
