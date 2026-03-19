// lib/models/message.dart
class Message {
  final String id;
  final String role; // 'user' | 'assistant'
  final String content;
  final DateTime timestamp;
  final String? provider;
  final String? model;

  const Message({
    required this.id,
    required this.role,
    required this.content,
    required this.timestamp,
    this.provider,
    this.model,
  });

  bool get isUser => role == 'user';
  bool get isAssistant => role == 'assistant';

  factory Message.user(String content) => Message(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        role: 'user',
        content: content,
        timestamp: DateTime.now(),
      );

  factory Message.assistant(
    String content, {
    String? provider,
    String? model,
  }) =>
      Message(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        role: 'assistant',
        content: content,
        timestamp: DateTime.now(),
        provider: provider,
        model: model,
      );

  factory Message.fromJson(Map<String, dynamic> json) => Message(
        id: json['id']?.toString() ?? DateTime.now().millisecondsSinceEpoch.toString(),
        role: json['role'] as String,
        content: json['content'] as String,
        timestamp: DateTime.tryParse(json['timestamp'] as String? ?? '') ?? DateTime.now(),
        provider: json['provider'] as String?,
        model: json['model'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'role': role,
        'content': content,
        'timestamp': timestamp.toIso8601String(),
        if (provider != null) 'provider': provider,
        if (model != null) 'model': model,
      };
}
