import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/settings_model.dart';
import '../services/api_service.dart';
import 'chat_screen.dart';
import 'tools_screen.dart';
import 'logs_screen.dart';
import 'settings_screen.dart';

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _index = 0;
  bool _online = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _ping());
  }

  ApiService get _api =>
      ApiService(baseUrl: context.read<SettingsModel>().backendUrl);

  Future<void> _ping() async {
    final ok = await _api.checkHealth();
    if (mounted) setState(() => _online = ok);
  }

  static const _destinations = [
    NavigationDestination(
      icon: Icon(Icons.chat_bubble_outline),
      selectedIcon: Icon(Icons.chat_bubble),
      label: 'Chat',
    ),
    NavigationDestination(
      icon: Icon(Icons.build_outlined),
      selectedIcon: Icon(Icons.build),
      label: 'Tools',
    ),
    NavigationDestination(
      icon: Icon(Icons.article_outlined),
      selectedIcon: Icon(Icons.article),
      label: 'Logs',
    ),
    NavigationDestination(
      icon: Icon(Icons.settings_outlined),
      selectedIcon: Icon(Icons.settings),
      label: 'Settings',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Text(
              'ARIA',
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w800,
                letterSpacing: 3,
                color: theme.colorScheme.primary,
              ),
            ),
            const SizedBox(width: 8),
            AnimatedContainer(
              duration: const Duration(milliseconds: 400),
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _online ? Colors.greenAccent : Colors.redAccent,
              ),
            ),
            const SizedBox(width: 4),
            Text(
              _online ? 'online' : 'offline',
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.outline,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, size: 20),
            tooltip: 'Reconnect',
            onPressed: _ping,
          ),
        ],
      ),
      body: IndexedStack(
        index: _index,
        children: const [
          ChatScreen(),
          ToolsScreen(),
          LogsScreen(),
          SettingsScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: _destinations,
      ),
    );
  }
}
