import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:intl/intl.dart';

import '../models/message.dart';

// ── Public widget ─────────────────────────────────────────────────────────────

class MessageBubble extends StatelessWidget {
  final Message message;
  const MessageBubble({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    if (message.isError) return _ErrorBubble(message: message);
    return message.isUser
        ? _UserBubble(message: message)
        : _AssistantBubble(message: message);
  }
}

// ── User bubble ───────────────────────────────────────────────────────────────

class _UserBubble extends StatelessWidget {
  final Message message;
  const _UserBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(48, 4, 12, 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          GestureDetector(
            onLongPress: () => _copy(context, message.content),
            child: Container(
              decoration: BoxDecoration(
                color: scheme.primary,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(18),
                  topRight: Radius.circular(18),
                  bottomLeft: Radius.circular(18),
                  bottomRight: Radius.circular(4),
                ),
              ),
              padding:
                  const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: SelectableText(
                message.content,
                style: TextStyle(
                  color: scheme.onPrimary,
                  fontSize: 15,
                  height: 1.4,
                ),
              ),
            ),
          ),
          const SizedBox(height: 2),
          Text(
            _fmt(message.timestamp),
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: scheme.outline,
                  fontSize: 10,
                ),
          ),
        ],
      ),
    );
  }
}

// ── Assistant bubble ──────────────────────────────────────────────────────────

class _AssistantBubble extends StatelessWidget {
  final Message message;
  const _AssistantBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 4, 48, 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Avatar row
          Row(
            children: [
              _AvatarA(scheme: scheme),
              const SizedBox(width: 6),
              Text(
                'ARIA',
                style: theme.textTheme.labelSmall?.copyWith(
                  color: scheme.primary,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1,
                ),
              ),
              if (message.provider != null) ...[
                const SizedBox(width: 4),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                  decoration: BoxDecoration(
                    color: scheme.primaryContainer,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    message.provider!,
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: scheme.onPrimaryContainer,
                      fontSize: 9,
                    ),
                  ),
                ),
              ],
              if (message.commandsRun != null && message.commandsRun! > 0) ...[
                const SizedBox(width: 4),
                Icon(Icons.terminal, size: 11, color: scheme.outline),
                Text(
                  '${message.commandsRun}',
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: scheme.outline,
                    fontSize: 10,
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: 4),
          GestureDetector(
            onLongPress: () => _copy(context, message.content),
            child: Container(
              decoration: BoxDecoration(
                color: scheme.surfaceContainerHighest,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(4),
                  topRight: Radius.circular(18),
                  bottomLeft: Radius.circular(18),
                  bottomRight: Radius.circular(18),
                ),
              ),
              padding:
                  const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: MarkdownBody(
                data: message.content,
                selectable: true,
                styleSheet: MarkdownStyleSheet(
                  p: TextStyle(
                    color: scheme.onSurfaceVariant,
                    fontSize: 15,
                    height: 1.45,
                  ),
                  code: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 13,
                    color: scheme.secondary,
                    backgroundColor:
                        scheme.secondaryContainer.withOpacity(0.4),
                  ),
                  codeblockDecoration: BoxDecoration(
                    color: scheme.surface,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: scheme.outlineVariant,
                      width: 0.5,
                    ),
                  ),
                  blockquoteDecoration: BoxDecoration(
                    color: scheme.surfaceContainerHighest,
                    border: Border(
                      left: BorderSide(color: scheme.primary, width: 3),
                    ),
                  ),
                  h1: TextStyle(
                    color: scheme.onSurface,
                    fontWeight: FontWeight.bold,
                  ),
                  h2: TextStyle(
                    color: scheme.onSurface,
                    fontWeight: FontWeight.w600,
                  ),
                  h3: TextStyle(
                    color: scheme.onSurface,
                    fontWeight: FontWeight.w600,
                  ),
                  listBullet: TextStyle(color: scheme.primary),
                ),
              ),
            ),
          ),
          const SizedBox(height: 2),
          Text(
            _fmt(message.timestamp),
            style: theme.textTheme.bodySmall?.copyWith(
              color: scheme.outline,
              fontSize: 10,
            ),
          ),
        ],
      ),
    );
  }
}

// ── Error bubble ──────────────────────────────────────────────────────────────

class _ErrorBubble extends StatelessWidget {
  final Message message;
  const _ErrorBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Container(
        padding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: scheme.errorContainer,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            Icon(Icons.error_outline, color: scheme.error, size: 18),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                message.content,
                style: TextStyle(color: scheme.onErrorContainer, fontSize: 13),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Typing indicator ──────────────────────────────────────────────────────────

class TypingIndicator extends StatefulWidget {
  const TypingIndicator({super.key});

  @override
  State<TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<TypingIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 4, 48, 4),
      child: Row(
        children: [
          _AvatarA(scheme: scheme),
          const SizedBox(width: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: scheme.surfaceContainerHighest,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(4),
                topRight: Radius.circular(18),
                bottomLeft: Radius.circular(18),
                bottomRight: Radius.circular(18),
              ),
            ),
            child: AnimatedBuilder(
              animation: _ctrl,
              builder: (_, __) => Row(
                mainAxisSize: MainAxisSize.min,
                children: List.generate(3, (i) {
                  final phase = (_ctrl.value - i * 0.2).clamp(0.0, 1.0);
                  final y = -4.0 *
                      (phase < 0.5
                          ? 2 * phase * phase
                          : 1 - 2 * (1 - phase) * (1 - phase));
                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 2),
                    child: Transform.translate(
                      offset: Offset(0, y),
                      child: Container(
                        width: 7,
                        height: 7,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: scheme.primary.withOpacity(0.7),
                        ),
                      ),
                    ),
                  );
                }),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Shared helpers ────────────────────────────────────────────────────────────

class _AvatarA extends StatelessWidget {
  final ColorScheme scheme;
  const _AvatarA({required this.scheme});

  @override
  Widget build(BuildContext context) {
    return CircleAvatar(
      radius: 14,
      backgroundColor: scheme.primaryContainer,
      child: Text(
        'A',
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.bold,
          color: scheme.onPrimaryContainer,
        ),
      ),
    );
  }
}

String _fmt(DateTime dt) => DateFormat('HH:mm').format(dt);

void _copy(BuildContext context, String text) {
  Clipboard.setData(ClipboardData(text: text));
  ScaffoldMessenger.of(context).showSnackBar(
    const SnackBar(
      content: Text('Copied to clipboard'),
      duration: Duration(seconds: 1),
      behavior: SnackBarBehavior.floating,
    ),
  );
}
