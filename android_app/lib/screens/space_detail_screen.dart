import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../models/settings_model.dart';
import '../services/api_service.dart';

class SpaceDetailScreen extends StatefulWidget {
  final String spaceId;
  const SpaceDetailScreen({super.key, required this.spaceId});

  @override
  State<SpaceDetailScreen> createState() => _SpaceDetailScreenState();
}

class _SpaceDetailScreenState extends State<SpaceDetailScreen>
    with SingleTickerProviderStateMixin {
  SpaceManifest? _manifest;
  List<SpaceFile> _files = [];
  bool _loading = false;
  bool _patching = false;

  final _patchCtrl = TextEditingController();
  final _fileEditCtrl = TextEditingController();
  String? _openFilePath;
  String? _openFileContent;

  late final TabController _tabs;
  WebViewController? _webCtrl;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 3, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _tabs.dispose();
    _patchCtrl.dispose();
    _fileEditCtrl.dispose();
    super.dispose();
  }

  ApiService get _api =>
      ApiService(baseUrl: context.read<SettingsModel>().backendUrl);

  String get _base => context.read<SettingsModel>().backendUrl;

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final manifest = await _api.getSpace(widget.spaceId);
      final files = await _api.listSpaceFiles(widget.spaceId);
      if (mounted) {
        setState(() {
          _manifest = manifest;
          _files = files;
        });
        _initWebView();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Load failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _initWebView() {
    final manifest = _manifest;
    if (manifest == null || !manifest.previewable) return;
    final baseUrl = _base.endsWith('/') ? _base.substring(0, _base.length - 1) : _base;
    final url = '$baseUrl/spaces/${widget.spaceId}/files/content?path=${Uri.encodeQueryComponent(manifest.entrypoint)}';

    // We serve content as data URI since the backend returns JSON with content
    _loadPreview();
  }

  Future<void> _loadPreview() async {
    final manifest = _manifest;
    if (manifest == null || !manifest.previewable) return;
    try {
      final html = await _api.readSpaceFile(widget.spaceId, manifest.entrypoint);
      final ctrl = WebViewController()
        ..setJavaScriptMode(JavaScriptMode.unrestricted)
        ..loadHtmlString(html, baseUrl: 'about:blank');
      if (mounted) setState(() => _webCtrl = ctrl);
    } catch (e) {
      // Preview unavailable
    }
  }

  Future<void> _patch() async {
    final prompt = _patchCtrl.text.trim();
    if (prompt.isEmpty) return;
    setState(() => _patching = true);
    try {
      await _api.patchSpace(widget.spaceId, prompt);
      _patchCtrl.clear();
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Space updated!'), duration: Duration(seconds: 2)),
        );
        _tabs.animateTo(0); // jump to preview
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Patch failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _patching = false);
    }
  }

  Future<void> _uploadFile() async {
    final result = await FilePicker.platform.pickFiles(withData: true);
    if (result == null || result.files.isEmpty) return;
    final f = result.files.first;
    if (f.bytes == null) return;
    final path = f.name;
    try {
      await _api.uploadSpaceFile(widget.spaceId, path, f.bytes!, f.name);
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Uploaded: $path'), duration: const Duration(seconds: 2)),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Upload failed: $e')));
      }
    }
  }

  Future<void> _createFile() async {
    final ctrl = TextEditingController();
    final name = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('New File'),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          decoration: const InputDecoration(
            labelText: 'File name',
            hintText: 'e.g. style.css, script.js',
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, ctrl.text.trim()),
            child: const Text('Create'),
          ),
        ],
      ),
    );
    if (name == null || name.isEmpty) return;
    try {
      await _api.writeSpaceFile(widget.spaceId, name, '');
      await _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    }
  }

  Future<void> _deleteFile(SpaceFile f) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete File'),
        content: Text('Delete "${f.path}"?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await _api.deleteSpaceFile(widget.spaceId, f.path);
      await _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Delete failed: $e')));
      }
    }
  }

  Future<void> _openFile(SpaceFile f) async {
    setState(() {
      _openFilePath = f.path;
      _openFileContent = null;
    });
    try {
      final content = await _api.readSpaceFile(widget.spaceId, f.path);
      setState(() {
        _openFileContent = content;
        _fileEditCtrl.text = content;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Read failed: $e')));
      }
    }
  }

  Future<void> _saveFile() async {
    if (_openFilePath == null) return;
    try {
      await _api.writeSpaceFile(widget.spaceId, _openFilePath!, _fileEditCtrl.text);
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Saved'), duration: Duration(seconds: 1)),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Save failed: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final manifest = _manifest;

    return Scaffold(
      appBar: AppBar(
        title: Text(manifest?.name ?? 'Space'),
        centerTitle: false,
        actions: [
          if (manifest != null)
            Padding(
              padding: const EdgeInsets.only(right: 4),
              child: Chip(
                label: Text(
                  'v${manifest.version}',
                  style: const TextStyle(fontSize: 11),
                ),
                padding: EdgeInsets.zero,
                visualDensity: VisualDensity.compact,
                backgroundColor: scheme.surfaceContainerHighest,
              ),
            ),
          IconButton(
            icon: const Icon(Icons.refresh, size: 20),
            onPressed: _load,
          ),
        ],
        bottom: TabBar(
          controller: _tabs,
          tabs: const [
            Tab(icon: Icon(Icons.preview, size: 18), text: 'Preview'),
            Tab(icon: Icon(Icons.folder_outlined, size: 18), text: 'Files'),
            Tab(icon: Icon(Icons.auto_fix_high, size: 18), text: 'Patch'),
          ],
        ),
      ),
      body: _loading && manifest == null
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabs,
              children: [
                _buildPreview(scheme),
                _buildFiles(scheme),
                _buildPatch(scheme),
              ],
            ),
    );
  }

  // ── Preview tab ─────────────────────────────────────────────────────────────

  Widget _buildPreview(ColorScheme scheme) {
    final manifest = _manifest;
    if (manifest == null) return const Center(child: CircularProgressIndicator());

    if (!manifest.previewable) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.terminal, size: 48, color: scheme.outline),
            const SizedBox(height: 12),
            Text(
              'No preview for ${manifest.type}',
              style: TextStyle(color: scheme.outline),
            ),
            const SizedBox(height: 8),
            Text(
              'Use the Files tab to view/edit code',
              style: TextStyle(color: scheme.outline, fontSize: 12),
            ),
          ],
        ),
      );
    }

    if (_webCtrl == null) {
      return const Center(child: CircularProgressIndicator());
    }

    return Column(
      children: [
        Expanded(child: WebViewWidget(controller: _webCtrl!)),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          color: scheme.surfaceContainerHighest,
          child: Row(
            children: [
              Icon(Icons.info_outline, size: 14, color: scheme.outline),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  '${manifest.type} · ${manifest.template} · ${manifest.entrypoint}',
                  style: TextStyle(fontSize: 11, color: scheme.outline),
                ),
              ),
              TextButton.icon(
                onPressed: _loadPreview,
                icon: const Icon(Icons.refresh, size: 14),
                label: const Text('Reload', style: TextStyle(fontSize: 12)),
                style: TextButton.styleFrom(
                  visualDensity: VisualDensity.compact,
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  // ── Files tab ───────────────────────────────────────────────────────────────

  Widget _buildFiles(ColorScheme scheme) {
    if (_openFilePath != null) {
      return _buildFileEditor(scheme);
    }
    return Column(
      children: [
        // Toolbar
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          color: scheme.surfaceContainerHighest,
          child: Row(
            children: [
              Text(
                '${_files.length} file${_files.length == 1 ? '' : 's'}',
                style: TextStyle(fontSize: 12, color: scheme.outline),
              ),
              const Spacer(),
              TextButton.icon(
                onPressed: _uploadFile,
                icon: const Icon(Icons.upload_file, size: 16),
                label: const Text('Upload', style: TextStyle(fontSize: 12)),
                style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
              ),
              const SizedBox(width: 4),
              TextButton.icon(
                onPressed: _createFile,
                icon: const Icon(Icons.add, size: 16),
                label: const Text('New', style: TextStyle(fontSize: 12)),
                style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
              ),
            ],
          ),
        ),
        Expanded(
          child: _files.isEmpty
              ? Center(child: Text('No files', style: TextStyle(color: scheme.outline)))
              : ListView.builder(
                  padding: const EdgeInsets.all(8),
                  itemCount: _files.length,
                  itemBuilder: (_, i) {
                    final f = _files[i];
                    return Dismissible(
                      key: ValueKey(f.path),
                      direction: DismissDirection.endToStart,
                      background: Container(
                        alignment: Alignment.centerRight,
                        padding: const EdgeInsets.only(right: 16),
                        color: scheme.errorContainer,
                        child: Icon(Icons.delete_outline, color: scheme.error),
                      ),
                      confirmDismiss: (_) async {
                        await _deleteFile(f);
                        return false; // _load() already refreshes
                      },
                      child: ListTile(
                        leading: Icon(_fileIcon(f.path), size: 20, color: scheme.primary),
                        title: Text(f.path, style: const TextStyle(fontFamily: 'monospace', fontSize: 13)),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              _fmtSize(f.size),
                              style: TextStyle(fontSize: 11, color: scheme.outline),
                            ),
                            const SizedBox(width: 4),
                            Icon(Icons.chevron_right, size: 16, color: scheme.outline),
                          ],
                        ),
                        onTap: () => _openFile(f),
                        onLongPress: () => _deleteFile(f),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildFileEditor(ColorScheme scheme) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          color: scheme.surfaceContainerHighest,
          child: Row(
            children: [
              IconButton(
                icon: const Icon(Icons.arrow_back, size: 18),
                onPressed: () => setState(() {
                  _openFilePath = null;
                  _openFileContent = null;
                }),
                tooltip: 'Back',
              ),
              Expanded(
                child: Text(
                  _openFilePath ?? '',
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                ),
              ),
              FilledButton.icon(
                onPressed: _saveFile,
                icon: const Icon(Icons.save, size: 16),
                label: const Text('Save'),
                style: FilledButton.styleFrom(
                  visualDensity: VisualDensity.compact,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: _openFileContent == null
              ? const Center(child: CircularProgressIndicator())
              : TextField(
                  controller: _fileEditCtrl,
                  maxLines: null,
                  expands: true,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12, height: 1.5),
                  decoration: const InputDecoration(
                    border: InputBorder.none,
                    contentPadding: EdgeInsets.all(12),
                  ),
                  keyboardType: TextInputType.multiline,
                ),
        ),
      ],
    );
  }

  // ── Patch tab ───────────────────────────────────────────────────────────────

  Widget _buildPatch(ColorScheme scheme) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: scheme.primaryContainer,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              children: [
                Icon(Icons.auto_fix_high, size: 18, color: scheme.onPrimaryContainer),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Describe a change and the AI will patch the Space files automatically.',
                    style: TextStyle(
                        color: scheme.onPrimaryContainer, fontSize: 12),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _patchCtrl,
            maxLines: 4,
            enabled: !_patching,
            decoration: const InputDecoration(
              labelText: 'What to change?',
              hintText: 'e.g. "Add sound on hit", "Change color to dark blue"',
              border: OutlineInputBorder(),
              alignLabelWithHint: true,
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: _patching ? null : _patch,
              icon: _patching
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2.5),
                    )
                  : const Icon(Icons.auto_fix_high),
              label: Text(_patching ? 'Patching…' : 'Apply Patch'),
            ),
          ),
          if (_manifest != null) ...[
            const SizedBox(height: 24),
            Text(
              'Space info',
              style: Theme.of(context)
                  .textTheme
                  .labelMedium
                  ?.copyWith(color: scheme.primary),
            ),
            const SizedBox(height: 8),
            _InfoRow('ID', _manifest!.id),
            _InfoRow('Type', _manifest!.type),
            _InfoRow('Template', _manifest!.template),
            _InfoRow('Status', _manifest!.status),
            _InfoRow('Version', 'v${_manifest!.version}'),
            _InfoRow('Created', _manifest!.createdAt),
          ],
        ],
      ),
    );
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

String _fmtSize(int bytes) {
  if (bytes < 1024) return '${bytes}B';
  if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)}KB';
  return '${(bytes / (1024 * 1024)).toStringAsFixed(1)}MB';
}

IconData _fileIcon(String path) {
  if (path.endsWith('.html')) return Icons.html;
  if (path.endsWith('.css')) return Icons.style;
  if (path.endsWith('.js')) return Icons.javascript;
  if (path.endsWith('.py')) return Icons.code;
  if (path.endsWith('.json')) return Icons.data_object;
  if (path.endsWith('.txt') || path.endsWith('.md')) return Icons.article;
  return Icons.insert_drive_file_outlined;
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  const _InfoRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          SizedBox(
            width: 80,
            child: Text(
              label,
              style: TextStyle(
                  fontSize: 12,
                  color: scheme.outline,
                  fontWeight: FontWeight.w500),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                  fontSize: 12, fontFamily: 'monospace'),
            ),
          ),
        ],
      ),
    );
  }
}
