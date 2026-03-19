import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/settings_model.dart';
import '../services/api_service.dart';
import 'space_detail_screen.dart';

class SpacesScreen extends StatefulWidget {
  const SpacesScreen({super.key});

  @override
  State<SpacesScreen> createState() => _SpacesScreenState();
}

class _SpacesScreenState extends State<SpacesScreen> {
  List<SpaceSummary> _spaces = [];
  bool _loading = false;
  final _promptCtrl = TextEditingController();
  final _nameCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _promptCtrl.dispose();
    _nameCtrl.dispose();
    super.dispose();
  }

  ApiService get _api =>
      ApiService(baseUrl: context.read<SettingsModel>().backendUrl);

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final list = await _api.listSpaces();
      if (mounted) setState(() => _spaces = list);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _create() async {
    final prompt = _promptCtrl.text.trim();
    if (prompt.isEmpty) return;
    final name = _nameCtrl.text.trim().isEmpty ? null : _nameCtrl.text.trim();

    Navigator.of(context).pop(); // close dialog
    setState(() => _loading = true);

    try {
      final manifest = await _api.createSpace(prompt: prompt, name: name);
      _promptCtrl.clear();
      _nameCtrl.clear();
      await _load();
      if (mounted) {
        Navigator.of(context).push(MaterialPageRoute(
          builder: (_) => SpaceDetailScreen(spaceId: manifest.id),
        ));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Create failed: $e')));
        setState(() => _loading = false);
      }
    }
  }

  void _showCreateDialog() {
    _promptCtrl.clear();
    _nameCtrl.clear();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('New Space'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _nameCtrl,
              decoration: const InputDecoration(
                labelText: 'Name (optional)',
                border: OutlineInputBorder(),
                isDense: true,
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _promptCtrl,
              maxLines: 3,
              autofocus: true,
              decoration: const InputDecoration(
                labelText: 'Describe what to build *',
                hintText: 'e.g. "Make a battleship game"',
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: _create,
            child: const Text('Create'),
          ),
        ],
      ),
    );
  }

  Future<void> _delete(SpaceSummary s) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete Space'),
        content: Text('Delete "${s.name}"?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text('Delete', style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ),
        ],
      ),
    );
    if (ok == true) {
      try {
        await _api.deleteSpace(s.id);
        _load();
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Open Space'),
        centerTitle: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, size: 20),
            onPressed: _load,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showCreateDialog,
        icon: const Icon(Icons.add),
        label: const Text('New Space'),
      ),
      body: _loading && _spaces.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : _spaces.isEmpty
              ? _EmptyState(onTap: _showCreateDialog)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView.builder(
                    padding: const EdgeInsets.fromLTRB(12, 8, 12, 80),
                    itemCount: _spaces.length,
                    itemBuilder: (_, i) => _SpaceCard(
                      space: _spaces[i],
                      onTap: () async {
                        await Navigator.of(context).push(MaterialPageRoute(
                          builder: (_) =>
                              SpaceDetailScreen(spaceId: _spaces[i].id),
                        ));
                        _load();
                      },
                      onDelete: () => _delete(_spaces[i]),
                    ),
                  ),
                ),
    );
  }
}

// ── Space card ────────────────────────────────────────────────────────────────

class _SpaceCard extends StatelessWidget {
  final SpaceSummary space;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  const _SpaceCard({
    required this.space,
    required this.onTap,
    required this.onDelete,
  });

  IconData _icon() {
    switch (space.type) {
      case 'web_app':
        return Icons.web;
      case 'code_tool':
        return Icons.terminal;
      case 'workflow':
        return Icons.account_tree_outlined;
      default:
        return Icons.apps;
    }
  }

  Color _statusColor(BuildContext ctx) {
    final s = Theme.of(ctx).colorScheme;
    switch (space.status) {
      case 'ready':
        return Colors.greenAccent;
      case 'created':
        return s.primary;
      default:
        return s.outline;
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: scheme.primaryContainer,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(_icon(), color: scheme.onPrimaryContainer, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      space.name,
                      style: Theme.of(context)
                          .textTheme
                          .titleSmall
                          ?.copyWith(fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 3),
                    Row(
                      children: [
                        Container(
                          width: 6,
                          height: 6,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: _statusColor(context),
                          ),
                        ),
                        const SizedBox(width: 5),
                        Text(
                          '${space.type} · ${space.status}',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: scheme.outline,
                                fontSize: 11,
                              ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.delete_outline, size: 18),
                color: scheme.error,
                onPressed: onDelete,
                tooltip: 'Delete',
              ),
              const Icon(Icons.chevron_right, size: 18),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Empty state ───────────────────────────────────────────────────────────────

class _EmptyState extends StatelessWidget {
  final VoidCallback onTap;
  const _EmptyState({required this.onTap});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.space_dashboard_outlined, size: 64, color: scheme.outline),
          const SizedBox(height: 16),
          Text(
            'No Spaces yet',
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(color: scheme.outline),
          ),
          const SizedBox(height: 8),
          Text(
            'Tap + to create your first Space',
            style: Theme.of(context)
                .textTheme
                .bodySmall
                ?.copyWith(color: scheme.outline),
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: onTap,
            icon: const Icon(Icons.add),
            label: const Text('New Space'),
          ),
        ],
      ),
    );
  }
}
