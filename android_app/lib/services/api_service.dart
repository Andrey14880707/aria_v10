import 'dart:convert';
import 'package:http/http.dart' as http;

// ── Exceptions ────────────────────────────────────────────────────────────────

class ApiException implements Exception {
  final String message;
  final int? statusCode;

  const ApiException(this.message, {this.statusCode});

  @override
  String toString() =>
      statusCode != null ? 'HTTP $statusCode: $message' : message;
}

// ── Data models ───────────────────────────────────────────────────────────────

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

  factory ChatResult.fromJson(Map<String, dynamic> j) => ChatResult(
        reply: j['reply'] as String? ?? '',
        provider: j['provider'] as String? ?? '',
        model: j['model'] as String? ?? '',
        commandsRun: j['commands_run'] as int? ?? 0,
        sessionId: j['session_id'] as int? ?? 0,
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

  factory MemoryStats.fromJson(Map<String, dynamic> j) => MemoryStats(
        sessions: j['sessions'] as int? ?? 0,
        facts: j['facts'] as int? ?? 0,
        commandsRun: j['commands_run'] as int? ?? 0,
        backgroundCycles: j['background_cycles'] as int? ?? 0,
        lastThought: j['last_thought'] as String? ?? '',
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

  factory FactEntry.fromJson(Map<String, dynamic> j) => FactEntry(
        id: j['id'] as int,
        fact: j['fact'] as String? ?? '',
        createdAt: j['created_at'] as String? ?? '',
        source: j['source'] as String? ?? '',
      );
}

class NoteEntry {
  final int id;
  final String note;
  final String createdAt;

  const NoteEntry({
    required this.id,
    required this.note,
    required this.createdAt,
  });

  factory NoteEntry.fromJson(Map<String, dynamic> j) => NoteEntry(
        id: j['id'] as int,
        note: j['note'] as String? ?? '',
        createdAt: j['created_at'] as String? ?? '',
      );
}

class ProviderInfo {
  final String id;
  final String name;
  final bool available;
  final List<String> models;

  const ProviderInfo({
    required this.id,
    required this.name,
    required this.available,
    required this.models,
  });

  factory ProviderInfo.fromJson(Map<String, dynamic> j) => ProviderInfo(
        id: j['id'] as String,
        name: j['name'] as String,
        available: j['available'] as bool? ?? false,
        models: (j['models'] as List?)?.cast<String>() ?? [],
      );
}

// ── Service ───────────────────────────────────────────────────────────────────

class ApiService {
  final String baseUrl;
  final Duration timeout;

  ApiService({
    required this.baseUrl,
    this.timeout = const Duration(seconds: 60),
  });

  // Trim trailing slash once
  String get _base => baseUrl.endsWith('/')
      ? baseUrl.substring(0, baseUrl.length - 1)
      : baseUrl;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };

  // ── helpers ──────────────────────────────────────────────────────────────

  Future<dynamic> _get(String path) async {
    final uri = Uri.parse('$_base$path');
    try {
      final res = await http.get(uri, headers: _headers).timeout(timeout);
      if (res.statusCode >= 400) {
        throw ApiException(_tryDecodeError(res.body), statusCode: res.statusCode);
      }
      return jsonDecode(res.body);
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException(e.toString());
    }
  }

  Future<dynamic> _post(String path, Map<String, dynamic> body) async {
    final uri = Uri.parse('$_base$path');
    try {
      final res = await http
          .post(uri, headers: _headers, body: jsonEncode(body))
          .timeout(timeout);
      if (res.statusCode >= 400) {
        throw ApiException(_tryDecodeError(res.body), statusCode: res.statusCode);
      }
      return jsonDecode(res.body);
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException(e.toString());
    }
  }

  Future<dynamic> _delete(String path) async {
    final uri = Uri.parse('$_base$path');
    try {
      final res = await http.delete(uri, headers: _headers).timeout(timeout);
      if (res.statusCode >= 400) {
        throw ApiException(_tryDecodeError(res.body), statusCode: res.statusCode);
      }
      if (res.body.isEmpty) return {};
      return jsonDecode(res.body);
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException(e.toString());
    }
  }

  String _tryDecodeError(String body) {
    try {
      final j = jsonDecode(body) as Map<String, dynamic>;
      return j['detail']?.toString() ?? body;
    } catch (_) {
      return body.length > 300 ? '${body.substring(0, 300)}…' : body;
    }
  }

  // ── public API ────────────────────────────────────────────────────────────

  Future<bool> checkHealth() async {
    try {
      final uri = Uri.parse('$_base/health');
      final res = await http
          .get(uri, headers: _headers)
          .timeout(const Duration(seconds: 5));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<ChatResult> chat({
    required String message,
    required String provider,
    required String model,
  }) async {
    final d = await _post('/chat', {
      'message': message,
      'provider': provider,
      'model': model,
    });
    return ChatResult.fromJson(d as Map<String, dynamic>);
  }

  Future<MemoryStats> getMemoryStats() async {
    final d = await _get('/memory');
    return MemoryStats.fromJson(d as Map<String, dynamic>);
  }

  Future<List<FactEntry>> getFacts({String query = '', int limit = 50}) async {
    final q = Uri.encodeQueryComponent(query);
    final d = await _get('/facts?query=$q&limit=$limit');
    return (d as List)
        .map((e) => FactEntry.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<NoteEntry>> getNotes({int limit = 50}) async {
    final d = await _get('/notes?limit=$limit');
    return (d as List)
        .map((e) => NoteEntry.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<String>> getLogs({int lines = 200}) async {
    final d = await _get('/logs?lines=$lines');
    return (d as List).map((e) => (e as Map)['line'] as String).toList();
  }

  Future<List<String>> getTools() async {
    final d = await _get('/tools');
    return ((d as Map)['tools'] as List).cast<String>();
  }

  Future<String> executeTool(String tool, Map<String, dynamic> args) async {
    final d = await _post('/tools/execute', {'tool': tool, 'args': args});
    return (d as Map)['result']?.toString() ?? '';
  }

  Future<Map<String, dynamic>> getSettings() async {
    final d = await _get('/settings');
    return d as Map<String, dynamic>;
  }

  Future<void> updateSettings(Map<String, dynamic> settings) async {
    await _post('/settings', settings);
  }

  Future<List<ProviderInfo>> getProviders() async {
    final d = await _get('/providers');
    return ((d as Map)['providers'] as List)
        .map((e) => ProviderInfo.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<void> deleteFact(int id) => _delete('/memory/facts/$id');

  Future<void> clearMemory() => _delete('/memory/clear');
}
