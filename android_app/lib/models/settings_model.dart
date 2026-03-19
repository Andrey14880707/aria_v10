import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SettingsModel extends ChangeNotifier {
  // ── preference keys ────────────────────────────────────────────────────────
  static const _kUrl = 'backend_url';
  static const _kProvider = 'provider';
  static const _kModel = 'model';
  static const _kOwner = 'owner_name';
  static const _kAnthropicKey = 'anthropic_api_key';
  static const _kOpenaiKey = 'openai_api_key';
  static const _kGeminiKey = 'gemini_api_key';
  static const _kDarkMode = 'dark_mode_override'; // unused by theme but stored

  // ── defaults ───────────────────────────────────────────────────────────────
  String _backendUrl = 'http://127.0.0.1:8000';
  String _provider = 'anthropic';
  String _model = 'claude-sonnet-4-20250514';
  String _ownerName = 'User';
  String _anthropicKey = '';
  String _openaiKey = '';
  String _geminiKey = '';

  // ── public getters ─────────────────────────────────────────────────────────
  String get backendUrl => _backendUrl;
  String get provider => _provider;
  String get model => _model;
  String get ownerName => _ownerName;
  String get anthropicKey => _anthropicKey;
  String get openaiKey => _openaiKey;
  String get geminiKey => _geminiKey;

  // ── provider → model catalog ───────────────────────────────────────────────
  static const Map<String, List<String>> providerModels = {
    'anthropic': [
      'claude-sonnet-4-20250514',
      'claude-opus-4-20250514',
      'claude-haiku-4-5-20251001',
    ],
    'openai': [
      'gpt-4o',
      'gpt-4o-mini',
      'gpt-4-turbo',
    ],
    'gemini': [
      'gemini-2.0-flash',
      'gemini-1.5-pro',
      'gemini-1.5-flash',
    ],
  };

  static const Map<String, String> providerLabels = {
    'anthropic': 'Claude',
    'openai': 'GPT',
    'gemini': 'Gemini',
  };

  List<String> get availableModels => providerModels[_provider] ?? [];

  // ── load / save ────────────────────────────────────────────────────────────
  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    _backendUrl = p.getString(_kUrl) ?? _backendUrl;
    _provider = p.getString(_kProvider) ?? _provider;
    _model = p.getString(_kModel) ?? _model;
    _ownerName = p.getString(_kOwner) ?? _ownerName;
    _anthropicKey = p.getString(_kAnthropicKey) ?? '';
    _openaiKey = p.getString(_kOpenaiKey) ?? '';
    _geminiKey = p.getString(_kGeminiKey) ?? '';
    notifyListeners();
  }

  Future<void> save({
    String? backendUrl,
    String? provider,
    String? model,
    String? ownerName,
    String? anthropicKey,
    String? openaiKey,
    String? geminiKey,
  }) async {
    final p = await SharedPreferences.getInstance();

    Future<void> set(String key, String? val) async {
      if (val == null) return;
      await p.setString(key, val);
    }

    if (backendUrl != null) _backendUrl = backendUrl;
    if (provider != null) _provider = provider;
    if (model != null) _model = model;
    if (ownerName != null) _ownerName = ownerName;
    if (anthropicKey != null) _anthropicKey = anthropicKey;
    if (openaiKey != null) _openaiKey = openaiKey;
    if (geminiKey != null) _geminiKey = geminiKey;

    await set(_kUrl, backendUrl);
    await set(_kProvider, provider);
    await set(_kModel, model);
    await set(_kOwner, ownerName);
    await set(_kAnthropicKey, anthropicKey);
    await set(_kOpenaiKey, openaiKey);
    await set(_kGeminiKey, geminiKey);

    notifyListeners();
  }

  void setProvider(String p) {
    _provider = p;
    final models = providerModels[p] ?? [];
    if (models.isNotEmpty && !models.contains(_model)) {
      _model = models.first;
    }
    notifyListeners();
    save(provider: p, model: _model);
  }

  void setModel(String m) {
    _model = m;
    notifyListeners();
    save(model: m);
  }
}
