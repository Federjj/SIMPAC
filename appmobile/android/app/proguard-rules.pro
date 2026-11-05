# Reglas de R8 para el release de SIMPAC.
# kotlinx.serialization: conserva los serializadores generados de los modelos.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt
-keepclassmembers class kotlinx.serialization.json.** { *** Companion; }
-keepclasseswithmembers class kotlinx.serialization.json.** { kotlinx.serialization.KSerializer serializer(...); }
-keep,includedescriptorclasses class pe.simpac.app.**$$serializer { *; }
-keepclassmembers class pe.simpac.app.** { *** Companion; }
-keepclasseswithmembers class pe.simpac.app.** { kotlinx.serialization.KSerializer serializer(...); }
# OkHttp
-dontwarn okhttp3.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
# osmdroid (mapa nativo)
-dontwarn org.osmdroid.**
