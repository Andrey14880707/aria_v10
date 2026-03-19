// lib/services/native_service.dart
// Flutter platform-channel client for native Android actions.
// Communicates with MainActivity via the "com.aria.app/native" MethodChannel.
import 'package:flutter/services.dart';

class NativeServiceException implements Exception {
  final String code;
  final String? message;
  const NativeServiceException(this.code, [this.message]);

  @override
  String toString() => 'NativeServiceException($code): $message';
}

class NativeService {
  static const _ch = MethodChannel('com.aria.app/native');

  // ── Flashlight ──────────────────────────────────────────────────────────

  /// Turn flashlight on.
  /// Throws [NativeServiceException] if no flash hardware or permission denied.
  static Future<void> flashlightOn() async {
    try {
      await _ch.invokeMethod<void>('flashlight_on');
    } on PlatformException catch (e) {
      throw NativeServiceException(e.code, e.message);
    }
  }

  /// Turn flashlight off.
  static Future<void> flashlightOff() async {
    try {
      await _ch.invokeMethod<void>('flashlight_off');
    } on PlatformException catch (e) {
      throw NativeServiceException(e.code, e.message);
    }
  }

  /// Returns true if this device has a flash/torch.
  static Future<bool> hasFlashlight() async {
    try {
      return await _ch.invokeMethod<bool>('has_flashlight') ?? false;
    } on PlatformException {
      return false;
    }
  }

  // ── Vibration ───────────────────────────────────────────────────────────

  /// Vibrate for [durationMs] milliseconds (1–5000 ms).
  /// [amplitude] is 1–255 or [VibrationEffect.DEFAULT_AMPLITUDE] (−1).
  static Future<void> vibrate({int durationMs = 300, int amplitude = -1}) async {
    try {
      await _ch.invokeMethod<void>('vibrate', {
        'duration_ms': durationMs.clamp(1, 5000),
        'amplitude': amplitude,
      });
    } on PlatformException catch (e) {
      throw NativeServiceException(e.code, e.message);
    }
  }

  // ── App Settings ────────────────────────────────────────────────────────

  /// Open this app's Android Settings page.
  static Future<void> openAppSettings() async {
    try {
      await _ch.invokeMethod<void>('open_app_settings');
    } on PlatformException catch (e) {
      throw NativeServiceException(e.code, e.message);
    }
  }
}
