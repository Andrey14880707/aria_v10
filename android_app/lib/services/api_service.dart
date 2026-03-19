// lib/services/api_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiException implements Exception {
  final String message;
  final int? statusCode;
  const ApiException(this.message, {this.statusCode});

  @override
  String toString() => 'ApiException($statusCode): $message';
}

class ChatResult {
  final String reply;
  final String provider;
  final String model;
  final int commandsRun;
  final int sessionId;

  const ChatResult({
    required this.reply,
    required this.provider,
    required this.model,
    required this.commandsRun,
    required this.sessionId,
  });

  factory ChatResult.fromJson(Map<String, dynamic> json) => ChatResult(
        reply: json['reply'] as String,
        provider: json['provider'] as String,
        model: json['model'] as String,
        commandsRun: json['commands_run'] as int? ?? 0,
        sessionId: json['session_id'] as int? ?? 0,
      );
}

class MemoryStats {
  final int sessions;
  final int facts;
  final int commandsRun;
  final int backgroundCycles;
  final String lastThought;

  const MemoryStats({
    required this.sessions,
    required this.facts,
    required this.commandsRun,
    required this.backgroundCycles,
    required this.lastThought,
  });

  factory MemoryStats.fromJson(Map<String, dynamic> json) => MemoryStats(
        sessions: json['sessions'] as int? ?? 0,
        facts: json['facts'] as int? ?? 0,
        commandsRun: json['commands_run'] as int? ?? 0,
        backgroundCycles: json['background_cycles'] as int? ?? 0,
        lastThought: json['last_thought'] as String? ?? '',
      );
}

class FactEntry {
  final int id;
  final String fact;
  final String createdAt;
  final String source;

  const FactEntry({
    required this.id,
    required this.fact,
    required this.createdAt,
    required this.source,
  });

  factory FactEntry.fromJson(Map<String, dynamic> json) => FactEntry(
        id: json['id'] as int,
        fact: json['fact'] as String,
        createdAt: json['created_at'] as String? ?? '',
        source: json['source'] as String? ?? '',
      );
}

class NoteEntry {
  final int id;
  final String note;
  final String createdAt;

  const NoteEntry({required this.id, required this.note, required this.createdAt});

  factory NoteEntry.fromJson(Map<String, dynamic> json) => NoteEntry(
        id: json['id'] as int,
        note: json['note'] as String,
        createdAt: json['created_at'] as String? ?? '',
      );
}

class ApiService {
  final String baseUrl;
  final Duration timeout;

  ApiService({required this.baseUrl, this.timeout = const Duration(seconds: 60)});

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };

  Future<T> _get<T>(String path, T Function(dynamic) parser) async {
    final uri = Uri.parse('$baseUrl$path');
    try {
      final res = await http.get(uri, headers: _headers).timeout(timeout);
      if (res.statusCode >= 400) {
        throw ApiException(res.body, statusCode: res.statusCode);
      }
      return parser(jsonDecode(res.body));
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException(e.toString());
    }
  }

  Future<T> _post<T>(String path, Map<String, dynamic> body, T Function(dynamic) parser) async {
    final uri = Uri.parse('$baseUrl$path');
    try {
      final res = await http
          .post(uri, headers: _headers, body: jsonEncode(body))
          .timeout(timeout);
      if (res.statusCode >= 400) {
        throw ApiException(res.body, statusCode: res.statusCode);
      }
      return parser(jsonDecode(res.body));
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException(e.toString());
    }
  }

  Future<bool> checkHealth() async {
    try {
      final uri = Uri.parse('$baseUrl/health');
      final res = await http.get(uri, headers: _headers).timeout(const Duration(seconds: 5));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<ChatResult> chat({
    required String message,
    required String provider,
    required String model,
  }) =>
      _post('/chat', {'message': message, 'provider': provider, 'model': model},
          (d) => ChatResult.fromJson(d as Map<String, dynamic>));

  Future<MemoryStats> getMemoryStats() =>
      _get('/memory', (d) => MemoryStats.fromJson(d as Map<String, dynamic>));

  Future<List<FactEntry>> getFacts({String query = '', int limit = 30}) =>
      _get('/facts?query=${Uri.encodeQueryComponent(query)}&limit=$limit',
          (d) => (d as List).map((e) => FactEntry.fromJson(e as Map<String, dynamic>)).toList());

  Future<List<NoteEntry>> getNotes({int limit = 30}) =>
      _get('/notes?limit=$limit',
          (d) => (d as List).map((e) => NoteEntry.fromJson(e as Map<String, dynamic>)).toList());

  Future<List<String>> getLogs({int lines = 100}) =>
      _get('/logs?lines=$lines',
          (d) => (d as List).map((e) => (e as Map)['line'] as String).toList());

  Future<List<String>> getTools() =>
      _get('/tools', (d) => (d as Map)['tools'] as List<String>? ?? []);

  Future<Map<String, dynamic>> getSettings() =>
      _get('/settings', (d) => d as Map<String, dynamic>);

  Future<void> updateSettings(Map<String, dynamic> settings) =>
      _post('/settings', settings, (_) {});

  Future<Map<String, dynamic>> getProviders() =>
      _get('/providers', (d) => d as Map<String, dynamic>);

  Future<void> deleteFact(int id) async {
    final uri = Uri.parse('$baseUrl/memory/facts/$id');
    final res = await http.delete(uri, headers: _headers).timeout(timeout);
    if (res.statusCode >= 400) {
      throw ApiException(res.body, statusCode: res.statusCode);
    }
  }

  Future<void> clearMemory() async {
    final uri = Uri.parse('$baseUrl/memory/clear');
    final res = await http.delete(uri, headers: _headers).timeout(timeout);
    if (res.statusCode >= 400) {
      throw ApiException(res.body, statusCode: res.statusCode);
    }
  }
}
