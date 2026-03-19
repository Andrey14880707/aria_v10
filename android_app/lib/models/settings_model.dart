// lib/models/settings_model.dart
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SettingsModel extends ChangeNotifier {
  static const _keyBackendUrl = 'backend_url';
  static const _keyProvider = 'provider';
  static const _keyModel = 'model';
  static const _keyOwnerName = 'owner_name';
  static const _keyAnthropicKey = 'anthropic_api_key';
  static const _keyOpenaiKey = 'openai_api_key';
  static const _keyGeminiKey = 'gemini_api_key';

  String _backendUrl = 'http://localhost:8000';
  String _provider = 'anthropic';
  String _model = 'claude-sonnet-4-20250514';
  String _ownerName = 'User';
  String _anthropicKey = '';
  String _openaiKey = '';
  String _geminiKey = '';

  String get backendUrl => _backendUrl;
  String get provider => _provider;
  String get model => _model;
  String get ownerName => _ownerName;
  String get anthropicKey => _anthropicKey;
  String get openaiKey => _openaiKey;
  String get geminiKey => _geminiKey;

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    _backendUrl = prefs.getString(_keyBackendUrl) ?? 'http://localhost:8000';
    _provider = prefs.getString(_keyProvider) ?? 'anthropic';
    _model = prefs.getString(_keyModel) ?? 'claude-sonnet-4-20250514';
    _ownerName = prefs.getString(_keyOwnerName) ?? 'User';
    _anthropicKey = prefs.getString(_keyAnthropicKey) ?? '';
    _openaiKey = prefs.getString(_keyOpenaiKey) ?? '';
    _geminiKey = prefs.getString(_keyGeminiKey) ?? '';
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
    final prefs = await SharedPreferences.getInstance();

    if (backendUrl != null) {
      _backendUrl = backendUrl;
      await prefs.setString(_keyBackendUrl, backendUrl);
    }
    if (provider != null) {
      _provider = provider;
      await prefs.setString(_keyProvider, provider);
    }
    if (model != null) {
      _model = model;
      await prefs.setString(_keyModel, model);
    }
    if (ownerName != null) {
      _ownerName = ownerName;
      await prefs.setString(_keyOwnerName, ownerName);
    }
    if (anthropicKey != null) {
      _anthropicKey = anthropicKey;
      await prefs.setString(_keyAnthropicKey, anthropicKey);
    }
    if (openaiKey != null) {
      _openaiKey = openaiKey;
      await prefs.setString(_keyOpenaiKey, openaiKey);
    }
    if (geminiKey != null) {
      _geminiKey = geminiKey;
      await prefs.setString(_keyGeminiKey, geminiKey);
    }

    notifyListeners();
  }

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

  List<String> get availableModels => providerModels[_provider] ?? [];

  void setProvider(String p) {
    _provider = p;
    final models = providerModels[p] ?? [];
    if (models.isNotEmpty) _model = models.first;
    notifyListeners();
  }
}
