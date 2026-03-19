// lib/screens/settings_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/settings_model.dart';
import '../services/api_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late TextEditingController _backendUrlCtrl;
  late TextEditingController _ownerNameCtrl;
  late TextEditingController _anthropicKeyCtrl;
  late TextEditingController _openaiKeyCtrl;
  late TextEditingController _geminiKeyCtrl;
  bool _saving = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    final s = context.read<SettingsModel>();
    _backendUrlCtrl = TextEditingController(text: s.backendUrl);
    _ownerNameCtrl = TextEditingController(text: s.ownerName);
    _anthropicKeyCtrl = TextEditingController(text: s.anthropicKey);
    _openaiKeyCtrl = TextEditingController(text: s.openaiKey);
    _geminiKeyCtrl = TextEditingController(text: s.geminiKey);
  }

  @override
  void dispose() {
    _backendUrlCtrl.dispose();
    _ownerNameCtrl.dispose();
    _anthropicKeyCtrl.dispose();
    _openaiKeyCtrl.dispose();
    _geminiKeyCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final settings = context.read<SettingsModel>();
    setState(() {
      _saving = true;
      _message = null;
    });

    await settings.save(
      backendUrl: _backendUrlCtrl.text.trim(),
      ownerName: _ownerNameCtrl.text.trim(),
      anthropicKey: _anthropicKeyCtrl.text.trim(),
      openaiKey: _openaiKeyCtrl.text.trim(),
      geminiKey: _geminiKeyCtrl.text.trim(),
    );

    // Push keys to backend
    try {
      final api = ApiService(baseUrl: _backendUrlCtrl.text.trim());
      await api.updateSettings({
        if (_anthropicKeyCtrl.text.trim().isNotEmpty)
          'anthropic_api_key': _anthropicKeyCtrl.text.trim(),
        if (_openaiKeyCtrl.text.trim().isNotEmpty)
          'openai_api_key': _openaiKeyCtrl.text.trim(),
        if (_geminiKeyCtrl.text.trim().isNotEmpty)
          'gemini_api_key': _geminiKeyCtrl.text.trim(),
        if (_ownerNameCtrl.text.trim().isNotEmpty)
          'owner_name': _ownerNameCtrl.text.trim(),
      });
      if (mounted) setState(() => _message = 'Settings saved.');
    } catch (e) {
      if (mounted) setState(() => _message = 'Local settings saved. Backend sync failed: $e');
    }

    if (mounted) setState(() => _saving = false);
  }

  @override
  Widget build(BuildContext context) {
    final settings = context.watch<SettingsModel>();
    final theme = Theme.of(context);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _SectionHeader('Connection'),
        _Field(
          controller: _backendUrlCtrl,
          label: 'Backend URL',
          hint: 'http://localhost:8000',
          icon: Icons.link,
        ),
        const SizedBox(height: 16),
        _SectionHeader('Profile'),
        _Field(
          controller: _ownerNameCtrl,
          label: 'Your name',
          icon: Icons.person_outline,
        ),
        const SizedBox(height: 16),
        _SectionHeader('API Keys'),
        _Field(
          controller: _anthropicKeyCtrl,
          label: 'Anthropic API Key',
          icon: Icons.key,
          obscure: true,
        ),
        const SizedBox(height: 12),
        _Field(
          controller: _openaiKeyCtrl,
          label: 'OpenAI API Key',
          icon: Icons.key,
          obscure: true,
        ),
        const SizedBox(height: 12),
        _Field(
          controller: _geminiKeyCtrl,
          label: 'Gemini API Key',
          icon: Icons.key,
          obscure: true,
        ),
        const SizedBox(height: 24),
        _SectionHeader('Active Provider'),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: SettingsModel.providerModels.keys
              .map((p) => ChoiceChip(
                    label: Text(p.toUpperCase()),
                    selected: settings.provider == p,
                    onSelected: (_) => settings.setProvider(p),
                  ))
              .toList(),
        ),
        const SizedBox(height: 8),
        if (settings.availableModels.isNotEmpty)
          DropdownButtonFormField<String>(
            value: settings.model,
            decoration: const InputDecoration(
              labelText: 'Model',
              border: OutlineInputBorder(),
            ),
            items: settings.availableModels
                .map((m) => DropdownMenuItem(value: m, child: Text(m)))
                .toList(),
            onChanged: (m) {
              if (m != null) settings.save(model: m);
            },
          ),
        const SizedBox(height: 32),
        if (_message != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(
              _message!,
              style: TextStyle(
                color: _message!.contains('fail')
                    ? theme.colorScheme.error
                    : theme.colorScheme.primary,
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
              : const Icon(Icons.save),
          label: const Text('Save Settings'),
        ),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: Theme.of(context).textTheme.labelLarge?.copyWith(
              color: Theme.of(context).colorScheme.primary,
              fontWeight: FontWeight.bold,
            ),
      ),
    );
  }
}

class _Field extends StatefulWidget {
  final TextEditingController controller;
  final String label;
  final String? hint;
  final IconData icon;
  final bool obscure;

  const _Field({
    required this.controller,
    required this.label,
    this.hint,
    required this.icon,
    this.obscure = false,
  });

  @override
  State<_Field> createState() => _FieldState();
}

class _FieldState extends State<_Field> {
  late bool _obscure;

  @override
  void initState() {
    super.initState();
    _obscure = widget.obscure;
  }

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: widget.controller,
      obscureText: _obscure,
      decoration: InputDecoration(
        labelText: widget.label,
        hintText: widget.hint,
        prefixIcon: Icon(widget.icon),
        border: const OutlineInputBorder(),
        suffixIcon: widget.obscure
            ? IconButton(
                icon: Icon(_obscure ? Icons.visibility_off : Icons.visibility),
                onPressed: () => setState(() => _obscure = !_obscure),
              )
            : null,
      ),
    );
  }
}
