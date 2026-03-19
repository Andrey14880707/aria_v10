// lib/screens/logs_screen.dart
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
  List<String> _lines = [];
  bool _loading = false;
  int _lineCount = 100;
  final ScrollController _scrollCtrl = ScrollController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  ApiService get _api {
    final settings = context.read<SettingsModel>();
    return ApiService(baseUrl: settings.backendUrl);
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final lines = await _api.getLogs(lines: _lineCount);
      if (mounted) {
        setState(() => _lines = lines.reversed.toList());
        _scrollToTop();
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

  void _scrollToTop() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          0,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _copyAll() {
    Clipboard.setData(ClipboardData(text: _lines.reversed.join('\n')));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Logs copied to clipboard')),
    );
  }

  Color _lineColor(BuildContext context, String line) {
    final theme = Theme.of(context);
    if (line.contains('ERROR') || line.contains('error') || line.contains('⚠')) {
      return theme.colorScheme.error;
    }
    if (line.contains('USER:')) return theme.colorScheme.primary;
    if (line.contains('ARIA:')) return theme.colorScheme.secondary;
    if (line.contains('boot') || line.contains('shutdown')) {
      return theme.colorScheme.tertiary;
    }
    return theme.colorScheme.onSurfaceVariant;
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Controls
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              const Text('Show last:'),
              const SizedBox(width: 8),
              DropdownButton<int>(
                value: _lineCount,
                isDense: true,
                items: const [
                  DropdownMenuItem(value: 50, child: Text('50')),
                  DropdownMenuItem(value: 100, child: Text('100')),
                  DropdownMenuItem(value: 250, child: Text('250')),
                  DropdownMenuItem(value: 500, child: Text('500')),
                ],
                onChanged: (v) {
                  if (v != null) {
                    setState(() => _lineCount = v);
                    _load();
                  }
                },
              ),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.copy),
                tooltip: 'Copy all',
                onPressed: _lines.isEmpty ? null : _copyAll,
              ),
              IconButton(
                icon: const Icon(Icons.refresh),
                tooltip: 'Refresh',
                onPressed: _load,
              ),
            ],
          ),
        ),
        // Log lines
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _lines.isEmpty
                  ? const Center(child: Text('No logs available.'))
                  : ListView.builder(
                      controller: _scrollCtrl,
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                      itemCount: _lines.length,
                      itemBuilder: (context, i) {
                        final line = _lines[i];
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 1),
                          child: SelectableText(
                            line,
                            style: TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 11,
                              color: _lineColor(context, line),
                              height: 1.4,
                            ),
                          ),
                        );
                      },
                    ),
        ),
      ],
    );
  }

  @override
  void dispose() {
    _scrollCtrl.dispose();
    super.dispose();
  }
}
