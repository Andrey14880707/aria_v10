// lib/screens/tools_screen.dart
// Two-tab screen:
//   "Shell Tools"  — calls POST /execute (backend allowlisted tools)
//   "Native"       — calls Android platform channel directly (no backend needed)
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../models/settings_model.dart';
import '../services/api_service.dart';
import '../services/native_service.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Shell tool schemas (argument definitions for the 8 /execute tools)
// ─────────────────────────────────────────────────────────────────────────────

class _ArgDef {
  final String name;
  final String type; // 'string' | 'int' | 'bool' | 'list'
  final String defaultValue;
  final String hint;

  const _ArgDef(this.name, this.type, this.defaultValue, [this.hint = '']);
}

const _shellSchemas = <String, List<_ArgDef>>{
  'run_shell': [
    _ArgDef('command', 'string', 'ls -la', 'e.g. ls -la /sdcard'),
    _ArgDef('cwd', 'string', '', 'working directory (optional)'),
    _ArgDef('timeout', 'int', '30', 'max seconds'),
  ],
  'read_file': [
    _ArgDef('path', 'string', '', '/path/to/file'),
    _ArgDef('max_lines', 'int', '200', 'max lines to return'),
  ],
  'write_file': [
    _ArgDef('path', 'string', '', '/path/to/file'),
    _ArgDef('content', 'string', '', 'file content'),
    _ArgDef('append', 'bool', 'false', 'true = append, false = overwrite'),
  ],
  'list_dir': [
    _ArgDef('path', 'string', '/sdcard', 'directory path'),
  ],
  'git_status': [
    _ArgDef('repo_path', 'string', '.', 'path to git repo'),
  ],
  'git_add': [
    _ArgDef('files', 'list', '', 'comma-separated file paths to stage'),
    _ArgDef('repo_path', 'string', '.', 'path to git repo'),
  ],
  'git_commit': [
    _ArgDef('message', 'string', '', 'commit message'),
    _ArgDef('repo_path', 'string', '.', 'path to git repo'),
  ],
  'git_push': [
    _ArgDef('remote', 'string', 'origin', 'git remote name'),
    _ArgDef('branch', 'string', '', 'branch (leave empty for current)'),
    _ArgDef('repo_path', 'string', '.', 'path to git repo'),
    _ArgDef('timeout', 'int', '60', 'max seconds'),
  ],
};

// ─────────────────────────────────────────────────────────────────────────────
// Screen
// ─────────────────────────────────────────────────────────────────────────────

class ToolsScreen extends StatefulWidget {
  const ToolsScreen({super.key});

  @override
  State<ToolsScreen> createState() => _ToolsScreenState();
}

class _ToolsScreenState extends State<ToolsScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      children: [
        TabBar(
          controller: _tabs,
          tabs: const [
            Tab(icon: Icon(Icons.terminal, size: 18), text: 'Shell / Git'),
            Tab(icon: Icon(Icons.phone_android, size: 18), text: 'Native'),
          ],
        ),
        Expanded(
          child: TabBarView(
            controller: _tabs,
            children: const [
              _ShellToolsPanel(),
              _NativeActionsPanel(),
            ],
          ),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tab 1: Shell / Git tools  →  POST /execute
// ─────────────────────────────────────────────────────────────────────────────

class _ShellToolsPanel extends StatefulWidget {
  const _ShellToolsPanel();

  @override
  State<_ShellToolsPanel> createState() => _ShellToolsPanelState();
}

class _ShellToolsPanelState extends State<_ShellToolsPanel> {
  String? _selected;
  String _result = '';
  bool _executing = false;
  final Map<String, TextEditingController> _ctrls = {};

  @override
  void dispose() {
    for (final c in _ctrls.values) c.dispose();
    super.dispose();
  }

  ApiService get _api =>
      ApiService(baseUrl: context.read<SettingsModel>().backendUrl);

  void _selectTool(String name) {
    for (final c in _ctrls.values) c.dispose();
    _ctrls.clear();
    for (final def in _shellSchemas[name] ?? []) {
      _ctrls[def.name] = TextEditingController(text: def.defaultValue);
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

    final Map<String, dynamic> args = {};
    for (final def in _shellSchemas[_selected!] ?? []) {
      final raw = _ctrls[def.name]?.text.trim() ?? '';
      if (raw.isEmpty) continue;
      switch (def.type) {
        case 'int':
          args[def.name] = int.tryParse(raw) ?? raw;
          break;
        case 'bool':
          args[def.name] = raw.toLowerCase() == 'true';
          break;
        case 'list':
          // comma-separated → List<String>
          args[def.name] = raw.split(',').map((s) => s.trim()).where((s) => s.isNotEmpty).toList();
          break;
        default:
          args[def.name] = raw;
      }
    }

    try {
      final result = await _api.executeShellTool(_selected!, args);
      if (mounted) setState(() => _result = result);
    } catch (e) {
      if (mounted) setState(() => _result = 'ERROR: $e');
    } finally {
      if (mounted) setState(() => _executing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        // Left: tool list
        SizedBox(
          width: 160,
          child: _ToolList(
            tools: _shellSchemas.keys.toList(),
            selected: _selected,
            onSelect: _selectTool,
          ),
        ),
        VerticalDivider(
          width: 1,
          color: Theme.of(context).colorScheme.outlineVariant,
        ),
        // Right: args + execute + result
        Expanded(
          child: _selected == null
              ? _SelectHint()
              : _ToolDetail(
                  toolName: _selected!,
                  defs: _shellSchemas[_selected!] ?? [],
                  ctrls: _ctrls,
                  result: _result,
                  executing: _executing,
                  onExecute: _execute,
                ),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tab 2: Native Android actions  →  platform channel
// ─────────────────────────────────────────────────────────────────────────────

class _NativeActionsPanel extends StatefulWidget {
  const _NativeActionsPanel();

  @override
  State<_NativeActionsPanel> createState() => _NativeActionsPanelState();
}

class _NativeActionsPanelState extends State<_NativeActionsPanel> {
  bool _torchOn = false;
  bool _hasFlash = false;
  String _log = '';
  final _vibrateCtrl = TextEditingController(text: '300');

  @override
  void initState() {
    super.initState();
    _checkFlash();
  }

  @override
  void dispose() {
    _vibrateCtrl.dispose();
    super.dispose();
  }

  Future<void> _checkFlash() async {
    final has = await NativeService.hasFlashlight();
    if (mounted) setState(() => _hasFlash = has);
  }

  void _appendLog(String msg) {
    if (!mounted) return;
    setState(() => _log = '[${_ts()}] $msg\n$_log');
  }

  String _ts() {
    final n = DateTime.now();
    return '${n.hour.toString().padLeft(2, '0')}:${n.minute.toString().padLeft(2, '0')}:${n.second.toString().padLeft(2, '0')}';
  }

  Future<void> _toggleTorch() async {
    try {
      if (_torchOn) {
        await NativeService.flashlightOff();
        setState(() => _torchOn = false);
        _appendLog('Flashlight OFF');
      } else {
        await NativeService.flashlightOn();
        setState(() => _torchOn = true);
        _appendLog('Flashlight ON');
      }
    } on NativeServiceException catch (e) {
      _appendLog('Flashlight error: ${e.code} — ${e.message}');
    } catch (e) {
      _appendLog('Flashlight error: $e');
    }
  }

  Future<void> _vibrate() async {
    final ms = int.tryParse(_vibrateCtrl.text.trim()) ?? 300;
    try {
      await NativeService.vibrate(durationMs: ms);
      _appendLog('Vibrated ${ms}ms');
    } on NativeServiceException catch (e) {
      _appendLog('Vibrate error: ${e.code} — ${e.message}');
    } catch (e) {
      _appendLog('Vibrate error: $e');
    }
  }

  Future<void> _openSettings() async {
    try {
      await NativeService.openAppSettings();
      _appendLog('Opened App Settings');
    } on NativeServiceException catch (e) {
      _appendLog('Settings error: ${e.code} — ${e.message}');
    } catch (e) {
      _appendLog('Settings error: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionLabel('Android Native Actions'),
          const SizedBox(height: 4),
          Text(
            'These call directly into Android via platform channels.\nNo backend required.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: scheme.outline,
                ),
          ),
          const SizedBox(height: 20),

          // ── Flashlight ──────────────────────────────────────────────────
          _SectionLabel('Flashlight'),
          const SizedBox(height: 8),
          if (!_hasFlash)
            _InfoChip(
              Icons.no_photography,
              'No flash hardware detected',
              scheme.errorContainer,
              scheme.onErrorContainer,
            )
          else
            Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _toggleTorch,
                    icon: Icon(
                      _torchOn ? Icons.flashlight_off : Icons.flashlight_on,
                    ),
                    label: Text(_torchOn ? 'Turn OFF' : 'Turn ON'),
                    style: FilledButton.styleFrom(
                      backgroundColor:
                          _torchOn ? scheme.error : scheme.primary,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  width: 16,
                  height: 16,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _torchOn ? Colors.yellow : scheme.outlineVariant,
                    boxShadow: _torchOn
                        ? [
                            BoxShadow(
                              color: Colors.yellow.withOpacity(0.8),
                              blurRadius: 10,
                              spreadRadius: 2,
                            )
                          ]
                        : null,
                  ),
                ),
              ],
            ),

          const SizedBox(height: 24),

          // ── Vibration ───────────────────────────────────────────────────
          _SectionLabel('Vibration'),
          const SizedBox(height: 8),
          Row(
            children: [
              SizedBox(
                width: 100,
                child: TextField(
                  controller: _vibrateCtrl,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'ms',
                    border: OutlineInputBorder(),
                    isDense: true,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton.icon(
                  onPressed: _vibrate,
                  icon: const Icon(Icons.vibration),
                  label: const Text('Vibrate'),
                ),
              ),
            ],
          ),

          const SizedBox(height: 24),

          // ── App Settings ────────────────────────────────────────────────
          _SectionLabel('System'),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _openSettings,
              icon: const Icon(Icons.settings_outlined),
              label: const Text('Open App Settings'),
            ),
          ),

          const SizedBox(height: 28),

          // ── Action log ──────────────────────────────────────────────────
          Row(
            children: [
              _SectionLabel('Action Log'),
              const Spacer(),
              if (_log.isNotEmpty)
                TextButton.icon(
                  onPressed: () => setState(() => _log = ''),
                  icon: const Icon(Icons.delete_outline, size: 14),
                  label: const Text('Clear', style: TextStyle(fontSize: 12)),
                  style: TextButton.styleFrom(
                    foregroundColor: scheme.outline,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 6),
          Container(
            width: double.infinity,
            constraints: const BoxConstraints(minHeight: 60, maxHeight: 220),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: scheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                  color: scheme.outlineVariant, width: 0.5),
            ),
            child: _log.isEmpty
                ? Text(
                    'No actions yet.',
                    style: TextStyle(
                        color: scheme.outline, fontStyle: FontStyle.italic),
                  )
                : SelectableText(
                    _log,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 11,
                      height: 1.5,
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared sub-widgets
// ─────────────────────────────────────────────────────────────────────────────

class _ToolList extends StatelessWidget {
  final List<String> tools;
  final String? selected;
  final void Function(String) onSelect;

  const _ToolList({
    required this.tools,
    required this.selected,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(10, 10, 10, 4),
          child: Text(
            '${tools.length} tools',
            style: Theme.of(context)
                .textTheme
                .labelSmall
                ?.copyWith(color: scheme.outline),
          ),
        ),
        Expanded(
          child: ListView.builder(
            itemCount: tools.length,
            itemBuilder: (_, i) {
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
                    fontWeight:
                        active ? FontWeight.bold : FontWeight.normal,
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

class _SelectHint extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.touch_app_outlined,
              size: 40, color: Theme.of(context).colorScheme.outline),
          const SizedBox(height: 12),
          Text(
            'Select a tool',
            style: TextStyle(color: Theme.of(context).colorScheme.outline),
          ),
        ],
      ),
    );
  }
}

class _ToolDetail extends StatelessWidget {
  final String toolName;
  final List<_ArgDef> defs;
  final Map<String, TextEditingController> ctrls;
  final String result;
  final bool executing;
  final VoidCallback onExecute;

  const _ToolDetail({
    required this.toolName,
    required this.defs,
    required this.ctrls,
    required this.result,
    required this.executing,
    required this.onExecute,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final isError = result.startsWith('ERROR:') || result.startsWith('⚠');

    return SingleChildScrollView(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Tool name badge
          Container(
            padding:
                const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: scheme.primaryContainer,
              borderRadius: BorderRadius.circular(6),
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
          const SizedBox(height: 14),

          // Arg fields
          ...defs.map((def) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _ArgField(def: def, ctrl: ctrls[def.name]!),
              )),

          const SizedBox(height: 6),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: executing ? null : onExecute,
              icon: executing
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2.5),
                    )
                  : const Icon(Icons.play_arrow),
              label: Text(executing ? 'Running…' : 'Execute'),
            ),
          ),

          // Result
          if (result.isNotEmpty) ...[
            const SizedBox(height: 14),
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
                        duration: Duration(seconds: 1),
                        behavior: SnackBarBehavior.floating,
                      ),
                    );
                  },
                  icon: const Icon(Icons.copy, size: 14),
                  label: const Text('Copy', style: TextStyle(fontSize: 12)),
                  style: TextButton.styleFrom(
                    foregroundColor: scheme.outline,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: isError
                    ? scheme.errorContainer.withOpacity(0.5)
                    : scheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(8),
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
                  height: 1.5,
                  color: isError ? scheme.error : scheme.onSurface,
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
      maxLines: def.type == 'string' && def.name == 'content' ? 5 : 1,
      keyboardType: def.type == 'int'
          ? TextInputType.number
          : TextInputType.text,
      style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
      decoration: InputDecoration(
        labelText: '${def.name}  (${def.type})',
        hintText: def.hint.isNotEmpty ? def.hint : null,
        border: const OutlineInputBorder(),
        isDense: true,
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: Theme.of(context).colorScheme.primary,
            fontWeight: FontWeight.bold,
            letterSpacing: 1.2,
          ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color bg;
  final Color fg;
  const _InfoChip(this.icon, this.label, this.bg, this.fg);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: fg),
          const SizedBox(width: 8),
          Text(label, style: TextStyle(color: fg, fontSize: 13)),
        ],
      ),
    );
  }
}
