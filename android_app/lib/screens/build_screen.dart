// lib/screens/build_screen.dart
// Triggers APK build pipeline via POST /build_apk
// Flow: git add → git commit → git push → CI builds APK
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../models/settings_model.dart';
import '../services/api_service.dart';

class BuildScreen extends StatefulWidget {
  const BuildScreen({super.key});

  @override
  State<BuildScreen> createState() => _BuildScreenState();
}

class _BuildScreenState extends State<BuildScreen> {
  final _msgCtrl = TextEditingController(text: 'ARIA: automated build trigger');
  final _filesCtrl = TextEditingController();
  final _remoteCtrl = TextEditingController(text: 'origin');
  final _branchCtrl = TextEditingController();
  final _repoCtrl = TextEditingController(text: '.');

  bool _running = false;
  List<_StepResult> _steps = [];
  String? _finalMsg;
  bool _success = false;

  @override
  void dispose() {
    _msgCtrl.dispose();
    _filesCtrl.dispose();
    _remoteCtrl.dispose();
    _branchCtrl.dispose();
    _repoCtrl.dispose();
    super.dispose();
  }

  ApiService get _api =>
      ApiService(baseUrl: context.read<SettingsModel>().backendUrl);

  Future<void> _trigger() async {
    if (_msgCtrl.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Commit message is required')),
      );
      return;
    }
    setState(() {
      _running = true;
      _steps = [];
      _finalMsg = null;
      _success = false;
    });

    final files = _filesCtrl.text
        .split(',')
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .toList();

    try {
      final result = await _api.buildApk(
        message: _msgCtrl.text.trim(),
        files: files,
        remote: _remoteCtrl.text.trim().isEmpty
            ? 'origin'
            : _remoteCtrl.text.trim(),
        branch: _branchCtrl.text.trim().isEmpty
            ? null
            : _branchCtrl.text.trim(),
        repoPath: _repoCtrl.text.trim().isEmpty
            ? '.'
            : _repoCtrl.text.trim(),
      );

      final rawSteps = result['steps'] as List? ?? [];
      if (mounted) {
        setState(() {
          _steps = rawSteps
              .map((s) => _StepResult(
                    step: (s as Map)['step'] as String? ?? '',
                    output: s['output'] as String? ?? '',
                  ))
              .toList();
          _finalMsg = result['message'] as String?;
          _success = result['status'] == 'ok';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _finalMsg = 'Request failed: $e';
          _success = false;
        });
      }
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Build APK'),
        centerTitle: false,
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // ── Info banner ─────────────────────────────────────────────────
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: scheme.primaryContainer,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              children: [
                Icon(Icons.info_outline,
                    size: 18, color: scheme.onPrimaryContainer),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Commits source changes and pushes to remote.\n'
                    'Your CI pipeline (GitHub Actions, etc.) builds the APK.',
                    style: TextStyle(
                        color: scheme.onPrimaryContainer, fontSize: 12),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 20),

          // ── Form ────────────────────────────────────────────────────────
          _Label('Commit Message *'),
          const SizedBox(height: 6),
          TextField(
            controller: _msgCtrl,
            maxLines: 2,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              hintText: 'feat: update ARIA build',
            ),
          ),

          const SizedBox(height: 14),

          _Label('Files to Stage (comma-separated, empty = git add -u)'),
          const SizedBox(height: 6),
          TextField(
            controller: _filesCtrl,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              hintText: 'android_app/lib/main.dart, router.py',
            ),
          ),

          const SizedBox(height: 14),

          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _Label('Remote'),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _remoteCtrl,
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        hintText: 'origin',
                        isDense: true,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _Label('Branch (optional)'),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _branchCtrl,
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        hintText: 'main',
                        isDense: true,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),

          const SizedBox(height: 14),

          _Label('Repo Path'),
          const SizedBox(height: 6),
          TextField(
            controller: _repoCtrl,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              hintText: '/data/data/com.termux/files/home/aria_v10',
            ),
          ),

          const SizedBox(height: 22),

          // ── Trigger button ───────────────────────────────────────────────
          FilledButton.icon(
            onPressed: _running ? null : _trigger,
            icon: _running
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2.5),
                  )
                : const Icon(Icons.rocket_launch),
            label: Text(_running ? 'Running…' : 'Trigger Build'),
          ),

          // ── Steps output ─────────────────────────────────────────────────
          if (_steps.isNotEmpty) ...[
            const SizedBox(height: 24),
            _Label('Pipeline Output'),
            const SizedBox(height: 8),
            ..._steps.map((s) => _StepTile(step: s)),
          ],

          // ── Final message ─────────────────────────────────────────────────
          if (_finalMsg != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: _success
                    ? scheme.primaryContainer
                    : scheme.errorContainer,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                children: [
                  Icon(
                    _success ? Icons.check_circle_outline : Icons.error_outline,
                    color: _success
                        ? scheme.onPrimaryContainer
                        : scheme.onErrorContainer,
                    size: 18,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _finalMsg!,
                      style: TextStyle(
                        color: _success
                            ? scheme.onPrimaryContainer
                            : scheme.onErrorContainer,
                        fontSize: 13,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],

          const SizedBox(height: 32),
        ],
      ),
    );
  }
}

class _Label extends StatelessWidget {
  final String text;
  const _Label(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: Theme.of(context).textTheme.labelMedium?.copyWith(
            color: Theme.of(context).colorScheme.primary,
          ),
    );
  }
}

class _StepResult {
  final String step;
  final String output;
  const _StepResult({required this.step, required this.output});
}

class _StepTile extends StatelessWidget {
  final _StepResult step;
  const _StepTile({super.key, required this.step});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final isError = step.output.startsWith('⚠') ||
        step.output.toLowerCase().contains('error') ||
        step.output.toLowerCase().contains('fatal');

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                isError ? Icons.close : Icons.check,
                size: 14,
                color: isError ? scheme.error : scheme.primary,
              ),
              const SizedBox(width: 6),
              Text(
                step.step,
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                  color: isError ? scheme.error : scheme.onSurface,
                ),
              ),
              const Spacer(),
              InkWell(
                onTap: () {
                  Clipboard.setData(ClipboardData(text: step.output));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                        content: Text('Copied'),
                        duration: Duration(seconds: 1)),
                  );
                },
                child: Icon(Icons.copy, size: 14, color: scheme.outline),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: scheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(6),
            ),
            child: SelectableText(
              step.output.isEmpty ? '(no output)' : step.output,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 11,
                height: 1.4,
                color: isError ? scheme.error : scheme.onSurface,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
