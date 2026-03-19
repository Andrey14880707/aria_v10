import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/message.dart';
import '../models/settings_model.dart';
import '../services/api_service.dart';
import '../widgets/message_bubble.dart';
import '../widgets/model_selector.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _messages = <Message>[];
  final _inputCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  final _focusNode = FocusNode();
  bool _thinking = false;

  ApiService get _api =>
      ApiService(baseUrl: context.read<SettingsModel>().backendUrl);

  // ── Send ─────────────────────────────────────────────────────────────────

  Future<void> _send() async {
    final text = _inputCtrl.text.trim();
    if (text.isEmpty || _thinking) return;

    final settings = context.read<SettingsModel>();

    setState(() {
      _messages.add(Message.user(text));
      _thinking = true;
    });
    _inputCtrl.clear();
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
            commandsRun: result.commandsRun,
          ));
        });
        _scrollToBottom();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _messages.add(Message.error(e.toString()));
        });
        _scrollToBottom();
      }
    } finally {
      if (mounted) setState(() => _thinking = false);
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 280),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _clearChat() => setState(() => _messages.clear());

  // ── UI ────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Clear button row
        if (_messages.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 4, 12, 0),
            child: Row(
              children: [
                const Spacer(),
                TextButton.icon(
                  onPressed: _clearChat,
                  icon: const Icon(Icons.delete_sweep_outlined, size: 16),
                  label: const Text('Clear', style: TextStyle(fontSize: 12)),
                  style: TextButton.styleFrom(
                    foregroundColor:
                        Theme.of(context).colorScheme.outline,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 4),
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
              ],
            ),
          ),

        // Messages
        Expanded(
          child: _messages.isEmpty && !_thinking
              ? _EmptyState(onSuggest: (s) {
                  _inputCtrl.text = s;
                  _send();
                })
              : ListView.builder(
                  controller: _scrollCtrl,
                  padding: const EdgeInsets.only(top: 8, bottom: 8),
                  itemCount: _messages.length + (_thinking ? 1 : 0),
                  itemBuilder: (ctx, i) {
                    if (i == _messages.length) {
                      return const TypingIndicator();
                    }
                    return MessageBubble(message: _messages[i]);
                  },
                ),
        ),

        // Model selector
        Container(
          padding: const EdgeInsets.fromLTRB(12, 6, 12, 0),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            border: Border(
              top: BorderSide(
                color: Theme.of(context).colorScheme.outlineVariant,
                width: 0.5,
              ),
            ),
          ),
          child: const ModelSelector(),
        ),

        // Input bar
        _InputBar(
          controller: _inputCtrl,
          focusNode: _focusNode,
          busy: _thinking,
          onSend: _send,
        ),
      ],
    );
  }

  @override
  void dispose() {
    _inputCtrl.dispose();
    _scrollCtrl.dispose();
    _focusNode.dispose();
    super.dispose();
  }
}

// ── Empty state ───────────────────────────────────────────────────────────────

class _EmptyState extends StatelessWidget {
  final void Function(String) onSuggest;
  const _EmptyState({required this.onSuggest});

  static const _suggestions = [
    'What can you do?',
    'Check battery status',
    'List files in /sdcard',
    'Search the web for Flutter',
    'Show system info',
  ];

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Logo
            Text(
              'ARIA',
              style: Theme.of(context).textTheme.displayLarge?.copyWith(
                    color: scheme.primary,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 6,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              'Local AI Assistant',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: scheme.outline,
                    letterSpacing: 1,
                  ),
            ),
            const SizedBox(height: 36),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: _suggestions
                  .map(
                    (s) => ActionChip(
                      label:
                          Text(s, style: const TextStyle(fontSize: 13)),
                      onPressed: () => onSuggest(s),
                    ),
                  )
                  .toList(),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Input bar ─────────────────────────────────────────────────────────────────

class _InputBar extends StatelessWidget {
  final TextEditingController controller;
  final FocusNode focusNode;
  final bool busy;
  final VoidCallback onSend;

  const _InputBar({
    required this.controller,
    required this.focusNode,
    required this.busy,
    required this.onSend,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: EdgeInsets.fromLTRB(
          12, 8, 12, 8 + MediaQuery.of(context).viewInsets.bottom),
      color: scheme.surface,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: TextField(
              controller: controller,
              focusNode: focusNode,
              minLines: 1,
              maxLines: 6,
              textInputAction: TextInputAction.newline,
              keyboardType: TextInputType.multiline,
              decoration: InputDecoration(
                hintText: 'Message ARIA…',
                hintStyle: TextStyle(color: scheme.outline),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide.none,
                ),
                filled: true,
                fillColor: scheme.surfaceContainerHighest,
                contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16, vertical: 10),
              ),
            ),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 46,
            height: 46,
            child: FilledButton(
              onPressed: busy ? null : onSend,
              style: FilledButton.styleFrom(
                shape: const CircleBorder(),
                padding: EdgeInsets.zero,
              ),
              child: busy
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2.5,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.send, size: 20),
            ),
          ),
        ],
      ),
    );
  }
}
