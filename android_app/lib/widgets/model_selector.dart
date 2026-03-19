import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/settings_model.dart';

class ModelSelector extends StatelessWidget {
  const ModelSelector({super.key});

  static const _colors = {
    'anthropic': Color(0xFF7C3AED),
    'openai': Color(0xFF10A37F),
    'gemini': Color(0xFF1A73E8),
  };

  @override
  Widget build(BuildContext context) {
    final settings = context.watch<SettingsModel>();

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          // Provider chips
          ...SettingsModel.providerLabels.entries.map((e) {
            final active = settings.provider == e.key;
            final color = _colors[e.key] ?? Theme.of(context).colorScheme.primary;
            return Padding(
              padding: const EdgeInsets.only(right: 6),
              child: _ProviderChip(
                label: e.value,
                color: color,
                selected: active,
                onTap: () => settings.setProvider(e.key),
              ),
            );
          }),

          // Model dropdown
          if (settings.availableModels.isNotEmpty) ...[
            const SizedBox(width: 2),
            _ModelDrop(settings: settings),
          ],
        ],
      ),
    );
  }
}

class _ProviderChip extends StatelessWidget {
  final String label;
  final Color color;
  final bool selected;
  final VoidCallback onTap;

  const _ProviderChip({
    required this.label,
    required this.color,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: selected ? color : color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(20),
          border: selected
              ? null
              : Border.all(color: color.withOpacity(0.4), width: 1),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: selected ? Colors.white : color,
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}

class _ModelDrop extends StatelessWidget {
  final SettingsModel settings;
  const _ModelDrop({required this.settings});

  String _shortLabel(String model) {
    // e.g. "claude-sonnet-4-20250514" → "sonnet-4"
    final parts = model.split('-');
    if (parts.length >= 2) return '${parts[1]}-${parts[2]}';
    return model;
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return DropdownButton<String>(
      value: settings.availableModels.contains(settings.model)
          ? settings.model
          : settings.availableModels.first,
      isDense: true,
      underline: const SizedBox(),
      borderRadius: BorderRadius.circular(10),
      style: Theme.of(context)
          .textTheme
          .bodySmall
          ?.copyWith(color: scheme.onSurface),
      dropdownColor: scheme.surfaceContainerHighest,
      items: settings.availableModels
          .map((m) => DropdownMenuItem(
                value: m,
                child: Text(
                  _shortLabel(m),
                  style: const TextStyle(fontSize: 12),
                ),
              ))
          .toList(),
      onChanged: (m) {
        if (m != null) settings.setModel(m);
      },
    );
  }
}
