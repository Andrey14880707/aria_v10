package com.aria.app

import android.content.Context
import android.content.Intent
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.net.Uri
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.provider.Settings
import android.util.Log
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {

    companion object {
        private const val TAG = "ARIA/Native"
        private const val CHANNEL = "com.aria.app/native"
    }

    private var torchCameraId: String? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        // Find flash camera id once
        torchCameraId = findFlashCameraId()

        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            CHANNEL
        ).setMethodCallHandler { call, result ->
            Log.d(TAG, "method=${call.method}")
            try {
                when (call.method) {

                    "flashlight_on" -> {
                        setTorch(true, result)
                    }

                    "flashlight_off" -> {
                        setTorch(false, result)
                    }

                    "vibrate" -> {
                        val durationMs = (call.argument<Any>("duration_ms") as? Number)
                            ?.toLong() ?: 300L
                        val amplitude = (call.argument<Any>("amplitude") as? Number)
                            ?.toInt() ?: VibrationEffect.DEFAULT_AMPLITUDE
                        doVibrate(durationMs, amplitude, result)
                    }

                    "open_app_settings" -> {
                        openAppSettings(result)
                    }

                    "has_flashlight" -> {
                        result.success(torchCameraId != null)
                    }

                    else -> result.notImplemented()
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error in ${call.method}", e)
                result.error("NATIVE_ERROR", e.message, e.stackTraceToString())
            }
        }
    }

    // ── Torch ─────────────────────────────────────────────────────────────────

    private fun findFlashCameraId(): String? {
        return try {
            val cm = getSystemService(Context.CAMERA_SERVICE) as CameraManager
            cm.cameraIdList.firstOrNull { id ->
                cm.getCameraCharacteristics(id)
                    .get(CameraCharacteristics.FLASH_INFO_AVAILABLE) == true
            }
        } catch (e: Exception) {
            Log.w(TAG, "Could not enumerate cameras", e)
            null
        }
    }

    private fun setTorch(on: Boolean, result: MethodChannel.Result) {
        val cameraId = torchCameraId
        if (cameraId == null) {
            result.error("NO_FLASH", "No flash/torch hardware found", null)
            return
        }
        try {
            val cm = getSystemService(Context.CAMERA_SERVICE) as CameraManager
            cm.setTorchMode(cameraId, on)
            result.success(null)
        } catch (e: Exception) {
            result.error("TORCH_ERROR", e.message, null)
        }
    }

    // ── Vibration ─────────────────────────────────────────────────────────────

    private fun doVibrate(durationMs: Long, amplitude: Int, result: MethodChannel.Result) {
        val safeDuration = durationMs.coerceIn(1L, 5000L)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            // API 31+ VibratorManager
            val vm = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
            val vib = vm.defaultVibrator
            vib.vibrate(
                VibrationEffect.createOneShot(safeDuration, amplitude)
            )
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            // API 26–30
            @Suppress("DEPRECATION")
            val vib = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
            vib.vibrate(
                VibrationEffect.createOneShot(safeDuration, amplitude)
            )
        } else {
            // API < 26 (legacy)
            @Suppress("DEPRECATION")
            val vib = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
            @Suppress("DEPRECATION")
            vib.vibrate(safeDuration)
        }
        result.success(null)
    }

    // ── App Settings ──────────────────────────────────────────────────────────

    private fun openAppSettings(result: MethodChannel.Result) {
        try {
            val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                data = Uri.fromParts("package", packageName, null)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            startActivity(intent)
            result.success(null)
        } catch (e: Exception) {
            result.error("SETTINGS_ERROR", e.message, null)
        }
    }
}
