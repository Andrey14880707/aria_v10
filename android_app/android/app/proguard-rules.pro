# Flutter-specific ProGuard rules
-keep class io.flutter.** { *; }
-keep class io.flutter.embedding.** { *; }
-dontwarn io.flutter.**

# Kotlin
-keep class kotlin.** { *; }
-dontwarn kotlin.**

# HTTP client
-keep class okhttp3.** { *; }
-dontwarn okhttp3.**
