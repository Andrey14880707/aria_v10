import 'dart:math';

class Message {
  final String id;
  final String role; // 'user' | 'assistant' | 'error'
  final String content;
  final DateTime timestamp;
  final String? provider;
  final String? model;
  final int? commandsRun;

  const Message({
    required this.id,
    required this.role,
    required this.content,
    required this.timestamp,
    this.provider,
    this.model,
    this.commandsRun,
  });

  bool get isUser => role == 'user';
  bool get isAssistant => role == 'assistant';
  bool get isError => role == 'error';

  static String _uid() =>
      DateTime.now().millisecondsSinceEpoch.toString() +
      Random().nextInt(9999).toString();

  factory Message.user(String content) => Message(
        id: _uid(),
        role: 'user',
        content: content,
        timestamp: DateTime.now(),
      );

  factory Message.assistant(
    String content, {
    String? provider,
    String? model,
    int? commandsRun,
  }) =>
      Message(
        id: _uid(),
        role: 'assistant',
        content: content,
        timestamp: DateTime.now(),
        provider: provider,
        model: model,
        commandsRun: commandsRun,
      );

  factory Message.error(String content) => Message(
        id: _uid(),
        role: 'error',
        content: content,
        timestamp: DateTime.now(),
      );
}
