# Android app (propuesta inicial)

Se recomienda usar Kotlin con Jetpack Compose por su velocidad y claridad para una app personal que solo consume un JSON del backend Python.

## Dependencias sugeridas

- Jetpack Compose
- ViewModel
- Navigation Compose
- Retrofit / Ktor
- Gson / Moshi
- Material3

## Flujo sugerido

1. El backend genera un JSON con el Top 5.
2. Android realiza una petición GET a un endpoint local o a un servicio.
3. La UI renderiza tarjetas con el Top 5.
4. El usuario puede seleccionar 3 opciones para armar un parlay.

## Estructura inicial

```text
android/
├── app/
│   ├── src/main/java/com/appuesta/
│   │   ├── data/
│   │   ├── domain/
│   │   ├── ui/
│   │   └── App.kt
│   └── build.gradle.kts
├── build.gradle.kts
├── settings.gradle.kts
└── gradle.properties
```

## Ejemplo de modelo de datos para Android

```kotlin
data class TopValuePick(
    val fixtureId: Int,
    val homeTeam: String,
    val awayTeam: String,
    val marketName: String,
    val selection: String,
    val bookmaker: String,
    val odds: Double,
    val modelProbability: Double,
    val impliedProbability: Double,
    val edge: Double,
    val expectedValue: Double,
    val confidence: Double
)
```
