// lib/screens/chat_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/message.dart';
import '../models/settings_model.dart';
import '../services/api_service.dart';
import '../widgets/message_bubble.dart';
import '../widgets/model_selector.dart';
import 'settings_screen.dart';
import 'memory_screen.dart';
import 'logs_screen.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final List<Message> _messages = [];
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  bool _isLoading = false;
  bool _backendOnline = false;
  String? _error;
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _checkBackend());
  }

  ApiService get _api {
    final settings = context.read<SettingsModel>();
    return ApiService(baseUrl: settings.backendUrl);
  }

  Future<void> _checkBackend() async {
    final alive = await _api.checkHealth();
    if (mounted) {
      setState(() => _backendOnline = alive);
      if (!alive) {
        setState(() => _error = 'Backend offline. Start ARIA backend on port 8000.');
      } else {
        setState(() => _error = null);
      }
    }
  }

  Future<void> _sendMessage() async {
    final text = _inputController.text.trim();
    if (text.isEmpty || _isLoading) return;

    final settings = context.read<SettingsModel>();

    setState(() {
      _messages.add(Message.user(text));
      _isLoading = true;
      _error = null;
    });
    _inputController.clear();
    _scrollToBottom();

    try {
      final result = await _api.chat(
        message: text,
        provider: settings.provider,
        model: settings.model,
      );
      if (mounted) {
        setState(() {
          _messages.add(Message.assistant(
            result.reply,
            provider: result.provider,
            model: result.model,
          ));
        });
        _scrollToBottom();
      }
    } catch (e) {
      if (mounted) {
        setState(() => _error = e.toString());
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _clearChat() {
    setState(() {
      _messages.clear();
      _error = null;
    });
  }

  Widget _buildChatBody() {
    return Column(
      children: [
        // Status bar
        AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          height: _error != null ? null : 0,
          child: _error != null
              ? Container(
                  width: double.infinity,
                  color: Theme.of(context).colorScheme.errorContainer,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Row(
                    children: [
                      Icon(Icons.error_outline,
                          size: 16,
                          color: Theme.of(context).colorScheme.onErrorContainer),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _error!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.onErrorContainer,
                            fontSize: 12,
                          ),
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.refresh, size: 16),
                        onPressed: _checkBackend,
                        color: Theme.of(context).colorScheme.onErrorContainer,
                      ),
                    ],
                  ),
                )
              : const SizedBox.shrink(),
        ),
        // Messages
        Expanded(
          child: _messages.isEmpty && !_isLoading
              ? _buildEmptyState()
              : ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  itemCount: _messages.length + (_isLoading ? 1 : 0),
                  itemBuilder: (context, i) {
                    if (i == _messages.length) return const TypingIndicator();
                    return MessageBubble(message: _messages[i]);
                  },
                ),
        ),
        // Model selector
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 4, 12, 0),
          child: Row(
            children: [
              const Expanded(child: ModelSelector()),
              if (!_backendOnline)
                Icon(Icons.cloud_off,
                    size: 16,
                    color: Theme.of(context).colorScheme.error),
              if (_backendOnline)
                Icon(Icons.cloud_done,
                    size: 16,
                    color: Theme.of(context).colorScheme.primary),
            ],
          ),
        ),
        // Input
        _InputBar(
          controller: _inputController,
          isLoading: _isLoading,
          onSend: _sendMessage,
        ),
      ],
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            'ARIA',
            style: Theme.of(context).textTheme.displayMedium?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 4,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            'Local AI Assistant',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.outline,
                ),
          ),
          const SizedBox(height: 32),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            alignment: WrapAlignment.center,
            children: [
              'What can you do?',
              'Check battery',
              'Search the web',
              'Read a file',
            ]
                .map((s) => ActionChip(
                      label: Text(s, style: const TextStyle(fontSize: 12)),
                      onPressed: () {
                        _inputController.text = s;
                        _sendMessage();
                      },
                    ))
                .toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildPage() {
    switch (_currentIndex) {
      case 0:
        return _buildChatBody();
      case 1:
        return const MemoryScreen();
      case 2:
        return const LogsScreen();
      case 3:
        return const SettingsScreen();
      default:
        return _buildChatBody();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('ARIA', style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 2)),
        centerTitle: false,
        actions: [
          if (_currentIndex == 0)
            IconButton(
              icon: const Icon(Icons.delete_sweep_outlined),
              tooltip: 'Clear chat',
              onPressed: _clearChat,
            ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Reconnect',
            onPressed: _checkBackend,
          ),
        ],
      ),
      body: SafeArea(child: _buildPage()),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (i) => setState(() => _currentIndex = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.chat_outlined), selectedIcon: Icon(Icons.chat), label: 'Chat'),
          NavigationDestination(icon: Icon(Icons.memory_outlined), selectedIcon: Icon(Icons.memory), label: 'Memory'),
          NavigationDestination(icon: Icon(Icons.article_outlined), selectedIcon: Icon(Icons.article), label: 'Logs'),
          NavigationDestination(icon: Icon(Icons.settings_outlined), selectedIcon: Icon(Icons.settings), label: 'Settings'),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }
}

class _InputBar extends StatelessWidget {
  final TextEditingController controller;
  final bool isLoading;
  final VoidCallback onSend;

  const _InputBar({
    required this.controller,
    required this.isLoading,
    required this.onSend,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(
          top: BorderSide(
            color: Theme.of(context).colorScheme.outlineVariant,
            width: 0.5,
          ),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: controller,
              maxLines: 5,
              minLines: 1,
              textInputAction: TextInputAction.newline,
              decoration: InputDecoration(
                hintText: 'Message ARIA...',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide.none,
                ),
                filled: true,
                fillColor: Theme.of(context).colorScheme.surfaceContainerHighest,
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              ),
              onSubmitted: (_) => onSend(),
            ),
          ),
          const SizedBox(width: 8),
          FilledButton.icon(
            onPressed: isLoading ? null : onSend,
            icon: isLoading
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.send),
            label: const Text('Send'),
            style: FilledButton.styleFrom(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
            ),
          ),
        ],
      ),
    );
  }
}
