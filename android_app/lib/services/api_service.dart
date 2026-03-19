import 'dart:convert';
import 'package:http/http.dart' as http;

// ── Safe parse helpers ────────────────────────────────────────────────────────

/// Safe String: handles null, int, double, bool → String.
String _s(dynamic v, [String def = '']) {
  if (v == null) return def;
  if (v is String) return v;
  return v.toString();
}

/// Safe int: handles null, String, double → int.
int _i(dynamic v, [int def = 0]) {
  if (v == null) return def;
  if (v is int) return v;
  if (v is double) return v.toInt();
  if (v is String) return int.tryParse(v) ?? def;
  return def;
}

/// Safe bool.
bool _b(dynamic v, [bool def = false]) {
  if (v == null) return def;
  if (v is bool) return v;
  if (v is String) return v.toLowerCase() == 'true';
  if (v is int) return v != 0;
  return def;
}

/// Safe List — never throws; returns [] for non-list values.
List<dynamic> _l(dynamic v) {
  if (v is List) return v;
  if (v is Map) {
    // Some endpoints wrap a list: {"items": [...]}
    for (final key in ['items', 'data', 'results', 'list']) {
      if (v[key] is List) return v[key] as List;
    }
  }
  return [];
}

/// Safe Map — never throws; returns {} for non-map values.
Map<String, dynamic> _m(dynamic v) {
  if (v is Map<String, dynamic>) return v;
  if (v is Map) {
    try {
      return v.map((k, val) => MapEntry(k.toString(), val));
    } catch (_) {}
  }
  return {};
}

/// Safe List<String> from a dynamic list.
List<String> _ls(dynamic v) => _l(v).map(_s).toList();

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

  factory ChatResult.fromJson(dynamic raw) {
    final j = _m(raw);
    // Try reply → response → message → text in order
    final reply = _s(j['reply']).isNotEmpty
        ? _s(j['reply'])
        : _s(j['response']).isNotEmpty
            ? _s(j['response'])
            : _s(j['message']).isNotEmpty
                ? _s(j['message'])
                : _s(j['text']);
    return ChatResult(
      reply: reply,
      provider: _s(j['provider']),
      model: _s(j['model']),
      commandsRun: _i(j['commands_run']),
      sessionId: _i(j['session_id']),
    );
  }
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

  factory MemoryStats.fromJson(dynamic raw) {
    final j = _m(raw);
    return MemoryStats(
      sessions: _i(j['sessions']),
      facts: _i(j['facts']),
      commandsRun: _i(j['commands_run']),
      backgroundCycles: _i(j['background_cycles']),
      lastThought: _s(j['last_thought']),
    );
  }
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

  factory FactEntry.fromJson(dynamic raw) {
    final j = _m(raw);
    return FactEntry(
      id: _i(j['id']),
      fact: _s(j['fact']),
      createdAt: _s(j['created_at']),
      source: _s(j['source']),
    );
  }
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

  factory NoteEntry.fromJson(dynamic raw) {
    final j = _m(raw);
    return NoteEntry(
      id: _i(j['id']),
      note: _s(j['note']),
      createdAt: _s(j['created_at']),
    );
  }
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

  factory ProviderInfo.fromJson(dynamic raw) {
    final j = _m(raw);
    return ProviderInfo(
      id: _s(j['id']),
      name: _s(j['name']),
      available: _b(j['available']),
      models: _ls(j['models']),
    );
  }
}

/// Log line — tolerates both `{"line":"..."}` and raw strings or rich objects.
class LogLine {
  final String text;
  final String level;
  final String ts;
  final String tool;
  final String status;

  const LogLine({
    required this.text,
    this.level = '',
    this.ts = '',
    this.tool = '',
    this.status = '',
  });

  factory LogLine.fromDynamic(dynamic e) {
    if (e == null) return const LogLine(text: '');
    if (e is String) return LogLine(text: e);
    final j = _m(e);
    // Accept "line", "message", "msg", "text" as the log text field
    final text = _s(j['line']).isNotEmpty
        ? _s(j['line'])
        : _s(j['message']).isNotEmpty
            ? _s(j['message'])
            : _s(j['msg']).isNotEmpty
                ? _s(j['msg'])
                : _s(j['text']).isNotEmpty
                    ? _s(j['text'])
                    : j.toString();
    return LogLine(
      text: text,
      level: _s(j['level']),
      ts: _s(j['ts']),
      tool: _s(j['tool']),
      status: _s(j['status']),
    );
  }

  /// Flat string for display / copy.
  String get display {
    if (ts.isNotEmpty) return '[$ts] $text';
    return text;
  }
}

// ── Service ───────────────────────────────────────────────────────────────────

class ApiService {
  final String baseUrl;
  final Duration timeout;

  ApiService({
    required this.baseUrl,
    this.timeout = const Duration(seconds: 60),
  });

  String get _base =>
      baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };

  // ── HTTP helpers ─────────────────────────────────────────────────────────

  Future<dynamic> _get(String path) async {
    final uri = Uri.parse('$_base$path');
    try {
      final res = await http.get(uri, headers: _headers).timeout(timeout);
      if (res.statusCode >= 400) {
        throw ApiException(_decodeError(res.body), statusCode: res.statusCode);
      }
      return _decodeBody(res.body);
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
        throw ApiException(_decodeError(res.body), statusCode: res.statusCode);
      }
      return _decodeBody(res.body);
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
        throw ApiException(_decodeError(res.body), statusCode: res.statusCode);
      }
      if (res.body.trim().isEmpty) return <String, dynamic>{};
      return _decodeBody(res.body);
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException(e.toString());
    }
  }

  /// Decode JSON body — never throws; returns {} or [] on bad JSON.
  dynamic _decodeBody(String body) {
    if (body.trim().isEmpty) return <String, dynamic>{};
    try {
      return jsonDecode(body);
    } catch (_) {
      return <String, dynamic>{'_raw': body};
    }
  }

  String _decodeError(String body) {
    try {
      final j = jsonDecode(body);
      if (j is Map) return _s(j['detail'] ?? j['error'] ?? j['message'], body);
    } catch (_) {}
    return body.length > 300 ? '${body.substring(0, 300)}…' : body;
  }

  // ── Public API ────────────────────────────────────────────────────────────

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
    return ChatResult.fromJson(d);
  }

  Future<MemoryStats> getMemoryStats() async {
    final d = await _get('/memory');
    return MemoryStats.fromJson(d);
  }

  Future<List<FactEntry>> getFacts({String query = '', int limit = 50}) async {
    final q = Uri.encodeQueryComponent(query);
    final d = await _get('/facts?query=$q&limit=$limit');
    return _l(d).map(FactEntry.fromJson).toList();
  }

  Future<List<NoteEntry>> getNotes({int limit = 50}) async {
    final d = await _get('/notes?limit=$limit');
    return _l(d).map(NoteEntry.fromJson).toList();
  }

  /// Accepts list of strings, list of `{"line":"..."}` objects, or mixed.
  Future<List<LogLine>> getLogs({int lines = 200}) async {
    final d = await _get('/logs?lines=$lines');
    return _l(d).map(LogLine.fromDynamic).toList();
  }

  /// Returns {shell_tools: [...], agent_tools: [...]}.
  /// Tolerates missing keys, non-string elements, or flat list response.
  Future<Map<String, List<String>>> getTools() async {
    final d = await _get('/tools');
    if (d is List) {
      // Flat list of tool name strings
      return {'shell_tools': _ls(d), 'agent_tools': []};
    }
    final j = _m(d);
    return {
      'shell_tools': _ls(j['shell_tools'] ?? j['tools'] ?? []),
      'agent_tools': _ls(j['agent_tools'] ?? []),
    };
  }

  /// POST /execute — 8 allowlisted shell/file/git tools.
  Future<String> executeShellTool(
      String tool, Map<String, dynamic> args) async {
    final d = await _post('/execute', {'tool': tool, 'args': args});
    final j = _m(d);
    if (_s(j['status']) == 'error') {
      throw ApiException(_s(j['result'], 'Unknown error'));
    }
    return _s(j['result']);
  }

  /// POST /tools/execute — legacy Termux agent tools.
  Future<String> executeTool(String tool, Map<String, dynamic> args) async {
    final d = await _post('/tools/execute', {'tool': tool, 'args': args});
    return _s(_m(d)['result']);
  }

  /// POST /build_apk — git add/commit/push → CI trigger.
  Future<Map<String, dynamic>> buildApk({
    required String message,
    List<String> files = const [],
    String remote = 'origin',
    String? branch,
    String repoPath = '.',
  }) async {
    final d = await _post('/build_apk', {
      'message': message,
      'files': files,
      'remote': remote,
      if (branch != null) 'branch': branch,
      'repo_path': repoPath,
    });
    return _m(d);
  }

  Future<Map<String, dynamic>> getSettings() async {
    return _m(await _get('/settings'));
  }

  Future<void> updateSettings(Map<String, dynamic> settings) async {
    await _post('/settings', settings);
  }

  Future<List<ProviderInfo>> getProviders() async {
    final d = await _get('/providers');
    final j = _m(d);
    final list = _l(j['providers'] ?? d);
    return list.map(ProviderInfo.fromJson).toList();
  }

  Future<void> deleteFact(int id) => _delete('/memory/facts/$id');

  Future<void> clearMemory() => _delete('/memory/clear');
}
