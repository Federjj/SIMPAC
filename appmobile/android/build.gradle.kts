// Archivo raiz: solo declara los plugins (las versiones viven en gradle/libs.versions.toml).
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.compose.compiler) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    // Firebase: el plugin se aplica en app/build.gradle.kts SOLO si existe app/google-services.json.
    alias(libs.plugins.google.services) apply false
}
