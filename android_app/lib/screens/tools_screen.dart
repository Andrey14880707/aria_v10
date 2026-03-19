import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../models/settings_model.dart';
import '../services/api_service.dart';

// Pre-defined argument schemas for known tools
const _toolSchemas = <String, List<_ArgDef>>{
  'battery_status': [],
  'system_info': [],
  'list_packages': [],
  'screenshot': [],
  'get_screen_size': [],
  'get_current_app': [],
  'wifi_info': [],
  'telephony_info': [],
  'torch': [_ArgDef('on', 'bool', 'true')],
  'location': [_ArgDef('provider', 'string', 'gps')],
  'speak': [_ArgDef('text', 'string', '')],
  'notification': [
    _ArgDef('title', 'string', 'ARIA'),
    _ArgDef('content', 'string', ''),
  ],
  'open_app': [_ArgDef('name', 'string', '')],
  'open_url': [_ArgDef('url', 'string', 'https://')],
  'open_settings': [_ArgDef('setting', 'string', '')],
  'vibrate': [_ArgDef('duration_ms', 'int', '500')],
  'volume': [
    _ArgDef('stream', 'string', 'music'),
    _ArgDef('direction', 'string', 'up'),
  ],
  'clipboard_get': [],
  'clipboard_set': [_ArgDef('text', 'string', '')],
  'input_text': [_ArgDef('text', 'string', '')],
  'keyevent': [_ArgDef('key_code', 'int', '3')],
  'tap': [
    _ArgDef('x', 'int', '540'),
    _ArgDef('y', 'int', '960'),
  ],
  'swipe': [
    _ArgDef('x1', 'int', '200'),
    _ArgDef('y1', 'int', '900'),
    _ArgDef('x2', 'int', '200'),
    _ArgDef('y2', 'int', '200'),
    _ArgDef('duration_ms', 'int', '500'),
  ],
  'list_dir': [_ArgDef('path', 'string', '/sdcard')],
  'read_file': [_ArgDef('path', 'string', '')],
  'internet_search': [_ArgDef('query', 'string', '')],
  'weather': [_ArgDef('city', 'string', '')],
  'http_get': [_ArgDef('url', 'string', 'https://')],
  'download_file': [
    _ArgDef('url', 'string', ''),
    _ArgDef('path', 'string', '/sdcard/Download/file'),
  ],
  'sleep': [_ArgDef('seconds', 'int', '1')],
  'echo': [_ArgDef('text', 'string', '')],
};

class _ArgDef {
  final String name;
  final String type; // 'string' | 'int' | 'bool'
  final String defaultValue;
  const _ArgDef(this.name, this.type, this.defaultValue);
}

// ── Screen ────────────────────────────────────────────────────────────────────

class ToolsScreen extends StatefulWidget {
  const ToolsScreen({super.key});

  @override
  State<ToolsScreen> createState() => _ToolsScreenState();
}

class _ToolsScreenState extends State<ToolsScreen> {
  List<String> _tools = [];
  bool _loading = false;
  String? _selected;
  String _result = '';
  bool _executing = false;
  String _filter = '';

  // controllers per arg field
  final Map<String, TextEditingController> _argCtrls = {};

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadTools());
  }

  ApiService get _api =>
      ApiService(baseUrl: context.read<SettingsModel>().backendUrl);

  Future<void> _loadTools() async {
    setState(() => _loading = true);
    try {
      final tools = await _api.getTools();
      if (mounted) setState(() => _tools = tools..sort());
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _selectTool(String name) {
    // Rebuild arg controllers
    for (final c in _argCtrls.values) c.dispose();
    _argCtrls.clear();
    final schema = _toolSchemas[name] ?? [];
    for (final def in schema) {
      _argCtrls[def.name] = TextEditingController(text: def.defaultValue);
    }
    setState(() {
      _selected = name;
      _result = '';
    });
  }

  Future<void> _execute() async {
    if (_selected == null) return;
    setState(() {
      _executing = true;
      _result = '';
    });

    try {
      Map<String, dynamic> args = {};
      final schema = _toolSchemas[_selected!] ?? [];
      for (final def in schema) {
        final raw = _argCtrls[def.name]?.text.trim() ?? '';
        if (raw.isEmpty) continue;
        if (def.type == 'int') {
          args[def.name] = int.tryParse(raw) ?? raw;
        } else if (def.type == 'bool') {
          args[def.name] = raw.toLowerCase() == 'true';
        } else {
          args[def.name] = raw;
        }
      }

      // For unknown tools use raw JSON
      if (!_toolSchemas.containsKey(_selected!) &&
          _argCtrls.containsKey('__json__')) {
        try {
          final j = jsonDecode(_argCtrls['__json__']!.text.trim());
          if (j is Map<String, dynamic>) args = j;
        } catch (_) {}
      }

      final result = await _api.executeTool(_selected!, args);
      if (mounted) setState(() => _result = result);
    } catch (e) {
      if (mounted) setState(() => _result = 'ERROR: $e');
    } finally {
      if (mounted) setState(() => _executing = false);
    }
  }

  List<String> get _filteredTools {
    if (_filter.isEmpty) return _tools;
    return _tools
        .where((t) => t.contains(_filter.toLowerCase()))
        .toList();
  }

  // ── Build ─────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        // Left panel: tool list
        SizedBox(
          width: 190,
          child: _ToolList(
            tools: _filteredTools,
            selected: _selected,
            loading: _loading,
            filter: _filter,
            onFilter: (f) => setState(() => _filter = f),
            onSelect: _selectTool,
            onRefresh: _loadTools,
          ),
        ),
        VerticalDivider(
          width: 1,
          color: Theme.of(context).colorScheme.outlineVariant,
        ),
        // Right panel: args + result
        Expanded(
          child: _selected == null
              ? _SelectPrompt()
              : _ToolDetail(
                  toolName: _selected!,
                  schema: _toolSchemas[_selected!] ?? [],
                  argCtrls: _argCtrls,
                  result: _result,
                  executing: _executing,
                  onExecute: _execute,
                ),
        ),
      ],
    );
  }

  @override
  void dispose() {
    for (final c in _argCtrls.values) c.dispose();
    super.dispose();
  }
}

// ── Left panel ────────────────────────────────────────────────────────────────

class _ToolList extends StatelessWidget {
  final List<String> tools;
  final String? selected;
  final bool loading;
  final String filter;
  final void Function(String) onFilter;
  final void Function(String) onSelect;
  final VoidCallback onRefresh;

  const _ToolList({
    required this.tools,
    required this.selected,
    required this.loading,
    required this.filter,
    required this.onFilter,
    required this.onSelect,
    required this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(8),
          child: TextField(
            decoration: InputDecoration(
              hintText: 'Filter…',
              prefixIcon: const Icon(Icons.search, size: 16),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(20),
                borderSide: BorderSide.none,
              ),
              filled: true,
              fillColor: scheme.surfaceContainerHighest,
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              isDense: true,
              suffixIcon: filter.isNotEmpty
                  ? GestureDetector(
                      onTap: () => onFilter(''),
                      child: const Icon(Icons.clear, size: 14),
                    )
                  : null,
            ),
            onChanged: onFilter,
            style: const TextStyle(fontSize: 13),
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8),
          child: Row(
            children: [
              Text(
                '${tools.length} tools',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: scheme.outline,
                    ),
              ),
              const Spacer(),
              InkWell(
                onTap: onRefresh,
                borderRadius: BorderRadius.circular(4),
                child: Padding(
                  padding: const EdgeInsets.all(4),
                  child: Icon(Icons.refresh, size: 14, color: scheme.outline),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 4),
        Expanded(
          child: loading
              ? const Center(child: CircularProgressIndicator())
              : ListView.builder(
                  itemCount: tools.length,
                  itemBuilder: (ctx, i) {
                    final t = tools[i];
                    final active = t == selected;
                    return ListTile(
                      dense: true,
                      selected: active,
                      selectedTileColor: scheme.primaryContainer,
                      title: Text(
                        t,
                        style: TextStyle(
                          fontSize: 12,
                          fontFamily: 'monospace',
                          color: active
                              ? scheme.onPrimaryContainer
                              : scheme.onSurface,
                        ),
                      ),
                      onTap: () => onSelect(t),
                    );
                  },
                ),
        ),
      ],
    );
  }
}

// ── Right panel ───────────────────────────────────────────────────────────────

class _SelectPrompt extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.touch_app_outlined,
            size: 48,
            color: Theme.of(context).colorScheme.outline,
          ),
          const SizedBox(height: 12),
          Text(
            'Select a tool',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.outline,
                ),
          ),
        ],
      ),
    );
  }
}

class _ToolDetail extends StatelessWidget {
  final String toolName;
  final List<_ArgDef> schema;
  final Map<String, TextEditingController> argCtrls;
  final String result;
  final bool executing;
  final VoidCallback onExecute;

  const _ToolDetail({
    required this.toolName,
    required this.schema,
    required this.argCtrls,
    required this.result,
    required this.executing,
    required this.onExecute,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final isError = result.startsWith('ERROR:');

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Tool name
          Container(
            padding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: scheme.primaryContainer,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              toolName,
              style: TextStyle(
                fontFamily: 'monospace',
                fontWeight: FontWeight.bold,
                color: scheme.onPrimaryContainer,
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Arg fields
          if (schema.isEmpty)
            Text(
              'No arguments required.',
              style: TextStyle(
                  color: scheme.outline, fontStyle: FontStyle.italic),
            )
          else ...[
            Text(
              'Arguments',
              style: Theme.of(context)
                  .textTheme
                  .labelMedium
                  ?.copyWith(color: scheme.outline),
            ),
            const SizedBox(height: 8),
            ...schema.map((def) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _ArgField(def: def, ctrl: argCtrls[def.name]!),
                )),
          ],

          // Execute button
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: executing ? null : onExecute,
              icon: executing
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child:
                          CircularProgressIndicator(strokeWidth: 2.5),
                    )
                  : const Icon(Icons.play_arrow),
              label: Text(executing ? 'Running…' : 'Execute'),
            ),
          ),

          // Result
          if (result.isNotEmpty) ...[
            const SizedBox(height: 16),
            Row(
              children: [
                Text(
                  'Result',
                  style: Theme.of(context)
                      .textTheme
                      .labelMedium
                      ?.copyWith(color: scheme.outline),
                ),
                const Spacer(),
                TextButton.icon(
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: result));
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                          content: Text('Copied'),
                          duration: Duration(seconds: 1)),
                    );
                  },
                  icon: const Icon(Icons.copy, size: 14),
                  label: const Text('Copy', style: TextStyle(fontSize: 12)),
                  style: TextButton.styleFrom(
                    foregroundColor: scheme.outline,
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: isError
                    ? scheme.errorContainer.withOpacity(0.6)
                    : scheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: isError
                      ? scheme.error.withOpacity(0.4)
                      : scheme.outlineVariant,
                  width: 0.5,
                ),
              ),
              child: SelectableText(
                result,
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 12,
                  color: isError ? scheme.error : scheme.onSurface,
                  height: 1.5,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _ArgField extends StatelessWidget {
  final _ArgDef def;
  final TextEditingController ctrl;
  const _ArgField({required this.def, required this.ctrl});

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: ctrl,
      decoration: InputDecoration(
        labelText: '${def.name} (${def.type})',
        border: const OutlineInputBorder(),
      ),
      keyboardType: def.type == 'int'
          ? TextInputType.number
          : TextInputType.text,
      style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
    );
  }
}
