# APPuesta

Aplicación personal para análisis de valor de apuestas en Liga MX.

## Objetivo

- Analizar la próxima jornada de Liga MX.
- Cruzar estadísticas históricas y xG.
- Consultar estadísticas de equipos y cuotas de Liga MX con API-Sports y The Odds API.
- Filtrar solo las mejores oportunidades con valor esperado positivo (+EV).
- Exponer un Top 5 amigable para Android.

## Estructura sugerida

```text
APPuesta/
├── .github/
│   └── agents/
│       ├── planeacion.md
│       ├── desarrollo.md
│       └── qa.md
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── models.py
│   │   ├── analysis/
│   │   │   ├── __init__.py
│   │   │   └── value_model.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── sports_api_client.py
│   │   │   └── odds_api_client.py
│   │   └── utils/
│   │       └── __init__.py
│   ├── .env.example
│   ├── requirements.txt
│   └── run_analysis.py
├── android/
│   └── README.md
└── docs/
    └── arquitectura-app.md
```

## Fase inicial

1. Consumir partidos de la Liga MX y H2H.
2. Estimar probabilidades con modelo simple.
3. Comparar con cuotas de casas mexicanas.
4. Filtrar solo +EV y mostrar Top 5.

## Backend: consulta de estadísticas, cuotas y Top 5

El backend consulta partidos y cuotas actuales de The Odds API (`soccer_mexico_ligamx`) y los cruza con
los promedios de goles históricos por localía de API-Sports. El plan gratuito disponible permite acceder
a la temporada 2024, así que los picks son solo un MVP experimental: comparan cuotas actuales con estadísticas
históricas, no con la forma actual de los equipos. No deben interpretarse como recomendaciones fiables.

The Odds API rechazó la región `mx`; el MVP usa la región `us`, por lo que las casas mostradas no representan
necesariamente operadores mexicanos ni sus momios. Cambia `ODDS_REGION` únicamente por una región admitida
por tu plan y el proveedor.

Las credenciales se configuran únicamente en `backend/.env`; no las compartas ni las agregues a Git.

En PowerShell, desde la raíz del proyecto:

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Completa API_SPORTS_KEY y ODDS_API_KEY en .env
python run_analysis.py
```

`STATS_SEASON` selecciona la temporada histórica que permite consultar tu plan de API-Sports. El Top 5 solo
incluye selecciones que superan `MODEL_EDGE_THRESHOLD`; las probabilidades son estimaciones, no garantías de resultados.
Las estadísticas históricas se guardan en `backend/.cache/` para evitar repetir consultas y continuar tras
los límites del plan gratuito. El intervalo de `API_SPORTS_REQUEST_INTERVAL_SECONDS` ayuda a respetar su
límite de solicitudes; la primera carga puede tardar varios segundos.

## MVP web privado

El dashboard web responsivo y el Worker de Cloudflare están en [cloudflare/README.md](./cloudflare/README.md).
Incluye búsqueda de partidos, hasta cinco selecciones experimentales, persistencia D1, historial de resultados
y tasa de acierto calculada solo sobre selecciones ganadas o perdidas. Antes de desplegar, configura D1,
los secretos de proveedores y un custom hostname protegido con Cloudflare Access.
