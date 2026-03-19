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
  List<_LogLine> _lines = [];
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
        setState(() {
          _lines = raw.map(_LogLine.parse).toList();
        });
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
    final text = _lines.map((l) => l.raw).join('\n');
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
          content: Text('Logs copied'), duration: Duration(seconds: 1)),
    );
  }

  List<_LogLine> get _filtered {
    if (_filter.isEmpty) return _lines;
    return _lines.where((l) => l.raw.contains(_filter)).toList();
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
              // Filter field
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
              // Line count picker
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
              // Actions
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
                onTap: () =>
                    setState(() => _autoScroll = !_autoScroll),
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
                      style: TextStyle(
                          fontSize: 10, color: scheme.outline),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const Divider(height: 1),
        // Log lines
        Expanded(
          child: _loading && _lines.isEmpty
              ? const Center(child: CircularProgressIndicator())
              : filtered.isEmpty
                  ? Center(
                      child: Text(
                        'No logs.',
                        style: TextStyle(color: scheme.outline),
                      ),
                    )
                  : ListView.builder(
                      controller: _scrollCtrl,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 6),
                      itemCount: filtered.length,
                      itemBuilder: (ctx, i) {
                        final l = filtered[i];
                        return _LineRow(line: l);
                      },
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

// ── Log line model ────────────────────────────────────────────────────────────

enum _LogLevel { info, user, aria, error, boot, tool }

class _LogLine {
  final String raw;
  final _LogLevel level;

  const _LogLine(this.raw, this.level);

  factory _LogLine.parse(String raw) {
    if (raw.contains('ERROR') || raw.contains('error') || raw.contains('⚠')) {
      return _LogLine(raw, _LogLevel.error);
    }
    if (raw.contains('[API] USER:') || raw.contains('USER:')) {
      return _LogLine(raw, _LogLevel.user);
    }
    if (raw.contains('[API] ARIA:') || raw.contains('ARIA:')) {
      return _LogLine(raw, _LogLevel.aria);
    }
    if (raw.contains('boot') || raw.contains('shutdown')) {
      return _LogLine(raw, _LogLevel.boot);
    }
    if (raw.contains('tool_') || raw.contains('[tool]')) {
      return _LogLine(raw, _LogLevel.tool);
    }
    return _LogLine(raw, _LogLevel.info);
  }
}

class _LineRow extends StatelessWidget {
  final _LogLine line;
  const _LineRow({super.key, required this.line});

  Color _color(BuildContext ctx) {
    final s = Theme.of(ctx).colorScheme;
    switch (line.level) {
      case _LogLevel.error:
        return s.error;
      case _LogLevel.user:
        return s.primary;
      case _LogLevel.aria:
        return s.secondary;
      case _LogLevel.boot:
        return s.tertiary;
      case _LogLevel.tool:
        return s.outline;
      case _LogLevel.info:
        return s.onSurfaceVariant;
    }
  }

  @override
  Widget build(BuildContext context) {
    return SelectableText(
      line.raw,
      style: TextStyle(
        fontFamily: 'monospace',
        fontSize: 11,
        height: 1.5,
        color: _color(context),
      ),
    );
  }
}
