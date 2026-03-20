import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import 'models/settings_model.dart';
import 'screens/main_shell.dart';
import 'services/api_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Portrait + landscape both supported
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
    DeviceOrientation.landscapeLeft,
    DeviceOrientation.landscapeRight,
  ]);

  final settings = SettingsModel();
  await settings.load();

  // Sync stored keys to backend on startup (backend loses them on restart)
  _syncKeysToBackend(settings);

  runApp(
    ChangeNotifierProvider.value(
      value: settings,
      child: const AriaApp(),
    ),
  );
}

void _syncKeysToBackend(SettingsModel s) {
  final body = <String, dynamic>{};
  if (s.anthropicKey.isNotEmpty) body['anthropic_api_key'] = s.anthropicKey;
  if (s.openaiKey.isNotEmpty) body['openai_api_key'] = s.openaiKey;
  if (s.geminiKey.isNotEmpty) body['gemini_api_key'] = s.geminiKey;
  if (body.isEmpty) return;
  ApiService(baseUrl: s.backendUrl).updateSettings(body).catchError((_) {});
}

class AriaApp extends StatelessWidget {
  const AriaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ARIA',
      debugShowCheckedModeBanner: false,
      theme: _theme(Brightness.light),
      darkTheme: _theme(Brightness.dark),
      themeMode: ThemeMode.system,
      home: const MainShell(),
    );
  }

  ThemeData _theme(Brightness brightness) {
    final isDark = brightness == Brightness.dark;
    final seed = const Color(0xFF6366F1); // indigo

    final scheme = ColorScheme.fromSeed(
      seedColor: seed,
      brightness: brightness,
    ).copyWith(
      surface: isDark ? const Color(0xFF0F0F1A) : const Color(0xFFF8F8FF),
      surfaceContainerHighest:
          isDark ? const Color(0xFF1C1C2E) : const Color(0xFFEEEEFF),
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surface,
      appBarTheme: AppBarTheme(
        elevation: 0,
        scrolledUnderElevation: 1,
        backgroundColor: scheme.surface,
        foregroundColor: scheme.onSurface,
        surfaceTintColor: Colors.transparent,
        systemOverlayStyle: isDark
            ? SystemUiOverlayStyle.light
            : SystemUiOverlayStyle.dark,
      ),
      navigationBarTheme: NavigationBarThemeData(
        elevation: 3,
        backgroundColor: scheme.surface,
        surfaceTintColor: Colors.transparent,
        indicatorColor: scheme.primaryContainer,
      ),
      cardTheme: CardTheme(
        elevation: 0,
        color: scheme.surfaceContainerHighest,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(
            color: scheme.outlineVariant.withOpacity(0.5),
            width: 0.5,
          ),
        ),
        margin: EdgeInsets.zero,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerHighest,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: scheme.primary, width: 1.5),
        ),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      ),
      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          padding:
              const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        ),
      ),
    );
  }
}
