// lib/screens/memory_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/settings_model.dart';
import '../services/api_service.dart';

class MemoryScreen extends StatefulWidget {
  const MemoryScreen({super.key});

  @override
  State<MemoryScreen> createState() => _MemoryScreenState();
}

class _MemoryScreenState extends State<MemoryScreen> with SingleTickerProviderStateMixin {
  late TabController _tabs;
  MemoryStats? _stats;
  List<FactEntry> _facts = [];
  List<NoteEntry> _notes = [];
  bool _loading = false;
  String _searchQuery = '';
  final TextEditingController _searchCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  ApiService get _api {
    final settings = context.read<SettingsModel>();
    return ApiService(baseUrl: settings.backendUrl);
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final results = await Future.wait([
        _api.getMemoryStats(),
        _api.getFacts(query: _searchQuery),
        _api.getNotes(),
      ]);
      if (mounted) {
        setState(() {
          _stats = results[0] as MemoryStats;
          _facts = results[1] as List<FactEntry>;
          _notes = results[2] as List<NoteEntry>;
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Theme.of(context).colorScheme.error),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _deleteFact(int id) async {
    try {
      await _api.deleteFact(id);
      setState(() => _facts.removeWhere((f) => f.id == id));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    }
  }

  Future<void> _clearMemory() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Clear all memory?'),
        content: const Text('This will delete all facts and notes. Cannot be undone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Clear'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        await _api.clearMemory();
        await _load();
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      children: [
        // Stats
        if (_stats != null)
          Container(
            padding: const EdgeInsets.all(16),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _StatCard('Sessions', _stats!.sessions.toString(), Icons.history),
                _StatCard('Facts', _stats!.facts.toString(), Icons.lightbulb_outline),
                _StatCard('Commands', _stats!.commandsRun.toString(), Icons.terminal),
              ],
            ),
          ),
        // Search
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: TextField(
            controller: _searchCtrl,
            decoration: InputDecoration(
              hintText: 'Search facts...',
              prefixIcon: const Icon(Icons.search),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(24)),
              contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              suffixIcon: _searchQuery.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear),
                      onPressed: () {
                        _searchCtrl.clear();
                        setState(() => _searchQuery = '');
                        _load();
                      },
                    )
                  : null,
            ),
            onChanged: (q) {
              setState(() => _searchQuery = q);
              _load();
            },
          ),
        ),
        const SizedBox(height: 8),
        // Tabs
        TabBar(
          controller: _tabs,
          tabs: [
            Tab(text: 'Facts (${_facts.length})'),
            Tab(text: 'Notes (${_notes.length})'),
          ],
        ),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : TabBarView(
                  controller: _tabs,
                  children: [
                    _FactsList(facts: _facts, onDelete: _deleteFact),
                    _NotesList(notes: _notes),
                  ],
                ),
        ),
        // Actions
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _load,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Refresh'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _clearMemory,
                  icon: const Icon(Icons.delete_forever),
                  label: const Text('Clear All'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: theme.colorScheme.error,
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  @override
  void dispose() {
    _tabs.dispose();
    _searchCtrl.dispose();
    super.dispose();
  }
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;

  const _StatCard(this.label, this.value, this.icon);

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Icon(icon, color: Theme.of(context).colorScheme.primary),
        const SizedBox(height: 4),
        Text(value, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
        Text(label, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}

class _FactsList extends StatelessWidget {
  final List<FactEntry> facts;
  final Future<void> Function(int) onDelete;

  const _FactsList({required this.facts, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    if (facts.isEmpty) {
      return const Center(child: Text('No facts stored yet.'));
    }
    return ListView.separated(
      padding: const EdgeInsets.all(8),
      itemCount: facts.length,
      separatorBuilder: (_, __) => const Divider(height: 1),
      itemBuilder: (context, i) {
        final f = facts[i];
        return ListTile(
          leading: const Icon(Icons.lightbulb_outline),
          title: Text(f.fact, style: const TextStyle(fontSize: 14)),
          subtitle: Text(f.createdAt, style: const TextStyle(fontSize: 11)),
          trailing: IconButton(
            icon: const Icon(Icons.delete_outline, size: 18),
            onPressed: () => onDelete(f.id),
          ),
        );
      },
    );
  }
}

class _NotesList extends StatelessWidget {
  final List<NoteEntry> notes;
  const _NotesList({required this.notes});

  @override
  Widget build(BuildContext context) {
    if (notes.isEmpty) {
      return const Center(child: Text('No notes yet.'));
    }
    return ListView.separated(
      padding: const EdgeInsets.all(8),
      itemCount: notes.length,
      separatorBuilder: (_, __) => const Divider(height: 1),
      itemBuilder: (context, i) {
        final n = notes[i];
        return ListTile(
          leading: const Icon(Icons.note_outlined),
          title: Text(n.note, style: const TextStyle(fontSize: 14)),
          subtitle: Text(n.createdAt, style: const TextStyle(fontSize: 11)),
        );
      },
    );
  }
}
