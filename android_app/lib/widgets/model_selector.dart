// lib/widgets/model_selector.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/settings_model.dart';

class ModelSelector extends StatelessWidget {
  const ModelSelector({super.key});

  @override
  Widget build(BuildContext context) {
    final settings = context.watch<SettingsModel>();
    final theme = Theme.of(context);

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _ProviderChip(
          label: 'Claude',
          id: 'anthropic',
          selected: settings.provider == 'anthropic',
          color: const Color(0xFF7C3AED),
          onTap: () => settings.setProvider('anthropic'),
        ),
        const SizedBox(width: 6),
        _ProviderChip(
          label: 'GPT',
          id: 'openai',
          selected: settings.provider == 'openai',
          color: const Color(0xFF10A37F),
          onTap: () => settings.setProvider('openai'),
        ),
        const SizedBox(width: 6),
        _ProviderChip(
          label: 'Gemini',
          id: 'gemini',
          selected: settings.provider == 'gemini',
          color: const Color(0xFF1A73E8),
          onTap: () => settings.setProvider('gemini'),
        ),
        const SizedBox(width: 8),
        if (settings.availableModels.isNotEmpty)
          DropdownButton<String>(
            value: settings.model,
            isDense: true,
            underline: const SizedBox(),
            style: theme.textTheme.bodySmall,
            items: settings.availableModels
                .map((m) => DropdownMenuItem(
                      value: m,
                      child: Text(m.split('-').take(2).join('-'), overflow: TextOverflow.ellipsis),
                    ))
                .toList(),
            onChanged: (m) {
              if (m != null) settings.save(model: m);
            },
          ),
      ],
    );
  }
}

class _ProviderChip extends StatelessWidget {
  final String label;
  final String id;
  final bool selected;
  final Color color;
  final VoidCallback onTap;

  const _ProviderChip({
    required this.label,
    required this.id,
    required this.selected,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: selected ? color : color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: color,
            width: selected ? 0 : 1,
          ),
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
