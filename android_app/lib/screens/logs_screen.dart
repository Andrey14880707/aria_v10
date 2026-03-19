import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../models/settings_model.dart';
import '../services/api_service.dart';

class LogsScreen extends StatefulWidget {
  const LogsScreen({super.key});

  @override
  State<LogsScreen> createState() => _LogsScreenState();
}

class _LogsScreenState extends State<LogsScreen> {
  // Uses LogLine from api_service (already has safe parsing)
  List<LogLine> _lines = [];
  bool _loading = false;
  int _lineCount = 200;
  String _filter = '';
  bool _autoScroll = true;
  final _scrollCtrl = ScrollController();
  final _filterCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  ApiService get _api =>
      ApiService(baseUrl: context.read<SettingsModel>().backendUrl);

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final raw = await _api.getLogs(lines: _lineCount);
      if (mounted) {
        setState(() => _lines = raw);
        if (_autoScroll) _scrollToBottom();
      }
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

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.jumpTo(_scrollCtrl.position.maxScrollExtent);
      }
    });
  }

  void _copyAll() {
    final text = _lines.map((l) => l.display).join('\n');
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
          content: Text('Logs copied'), duration: Duration(seconds: 1)),
    );
  }

  List<LogLine> get _filtered {
    if (_filter.isEmpty) return _lines;
    final q = _filter.toLowerCase();
    return _lines.where((l) => l.display.toLowerCase().contains(q)).toList();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final filtered = _filtered;

    return Column(
      children: [
        // Toolbar
        Container(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
          color: scheme.surface,
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _filterCtrl,
                  decoration: InputDecoration(
                    hintText: 'Filter logs…',
                    prefixIcon: const Icon(Icons.search, size: 16),
                    isDense: true,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(20),
                      borderSide: BorderSide.none,
                    ),
                    filled: true,
                    fillColor: scheme.surfaceContainerHighest,
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 8),
                    suffixIcon: _filter.isNotEmpty
                        ? GestureDetector(
                            onTap: () {
                              _filterCtrl.clear();
                              setState(() => _filter = '');
                            },
                            child: const Icon(Icons.clear, size: 14),
                          )
                        : null,
                  ),
                  onChanged: (v) => setState(() => _filter = v),
                  style: const TextStyle(fontSize: 13),
                ),
              ),
              const SizedBox(width: 6),
              DropdownButton<int>(
                value: _lineCount,
                isDense: true,
                underline: const SizedBox(),
                borderRadius: BorderRadius.circular(8),
                items: const [
                  DropdownMenuItem(value: 100, child: Text('100')),
                  DropdownMenuItem(value: 200, child: Text('200')),
                  DropdownMenuItem(value: 500, child: Text('500')),
                  DropdownMenuItem(value: 1000, child: Text('1k')),
                ],
                onChanged: (v) {
                  if (v != null) {
                    setState(() => _lineCount = v);
                    _load();
                  }
                },
              ),
              IconButton(
                icon: const Icon(Icons.copy, size: 18),
                tooltip: 'Copy all',
                onPressed: _lines.isEmpty ? null : _copyAll,
              ),
              IconButton(
                icon: const Icon(Icons.refresh, size: 18),
                tooltip: 'Refresh',
                onPressed: _load,
              ),
            ],
          ),
        ),
        // Stats bar
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 4),
          child: Row(
            children: [
              Text(
                '${filtered.length} lines',
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: scheme.outline, fontSize: 10),
              ),
              const Spacer(),
              InkWell(
                onTap: () => setState(() => _autoScroll = !_autoScroll),
                child: Row(
                  children: [
                    Icon(
                      _autoScroll
                          ? Icons.lock_outlined
                          : Icons.lock_open_outlined,
                      size: 12,
                      color: scheme.outline,
                    ),
                    const SizedBox(width: 3),
                    Text(
                      _autoScroll ? 'Auto-scroll' : 'Scroll free',
                      style: TextStyle(fontSize: 10, color: scheme.outline),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: _loading && _lines.isEmpty
              ? const Center(child: CircularProgressIndicator())
              : filtered.isEmpty
                  ? Center(
                      child: Text('No logs.',
                          style: TextStyle(color: scheme.outline)),
                    )
                  : ListView.builder(
                      controller: _scrollCtrl,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 6),
                      itemCount: filtered.length,
                      itemBuilder: (_, i) => _LineRow(line: filtered[i]),
                    ),
        ),
      ],
    );
  }

  @override
  void dispose() {
    _scrollCtrl.dispose();
    _filterCtrl.dispose();
    super.dispose();
  }
}

// ── Log line renderer ─────────────────────────────────────────────────────────

class _LineRow extends StatelessWidget {
  final LogLine line;
  const _LineRow({required this.line});

  Color _color(BuildContext ctx) {
    final s = Theme.of(ctx).colorScheme;
    final t = line.display;
    if (line.level == 'error' ||
        t.contains('ERROR') ||
        t.contains('error') ||
        t.contains('⚠')) return s.error;
    if (line.level == 'warn' || t.contains('WARN')) return s.tertiary;
    if (t.contains('USER:')) return s.primary;
    if (t.contains('ARIA:')) return s.secondary;
    if (t.contains('boot') || t.contains('shutdown')) return s.tertiary;
    if (t.contains('[tool]') || t.contains('tool_')) return s.outline;
    return s.onSurfaceVariant;
  }

  @override
  Widget build(BuildContext context) {
    return SelectableText(
      line.display,
      style: TextStyle(
        fontFamily: 'monospace',
        fontSize: 11,
        height: 1.5,
        color: _color(context),
      ),
    );
  }
}
