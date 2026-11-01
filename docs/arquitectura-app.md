# Arquitectura del MVP web

## Componentes

- **Interfaz:** dashboard responsivo en `cloudflare/public/`, servido junto con la API desde el mismo Worker.
- **Backend:** Python Worker en `cloudflare/src/`. El navegador no llama directamente a los proveedores y no recibe sus credenciales.
- **Análisis compartido:** el Worker y el CLI utilizan `appuesta-core` desde `backend/app/`; el bundle del Worker se prepara como un wheel puro de Python.
- **Persistencia:** Cloudflare D1 guarda ejecuciones, cachés de estadísticas y picks inmutables con sus momios y resultados.
- **Proveedores:** API-Sports aporta estadísticas históricas; The Odds API aporta partidos, momios y resultados.
- **Acceso:** Cloudflare Access protege el custom hostname. `workers_dev` y las preview URLs están desactivados.

## Flujo de análisis

1. El usuario solicita una búsqueda desde el dashboard.
2. `POST /api/analyze` consulta partidos/cuotas y resuelve equipos contra el catálogo de Liga MX.
3. Las estadísticas históricas se recuperan de D1 o API-Sports, respetando el máximo de consultas por búsqueda.
4. El modelo compartido calcula probabilidades y edge; las líneas enteras conservan por separado la probabilidad de push.
5. Se guardan hasta cinco selecciones nuevas, con unicidad por evento, mercado, resultado y línea.
6. El dashboard muestra cuotas, probabilidades, edge, EV y el origen experimental de los datos.

## Historial y resultados

El Cron diario y `POST /api/sync` consultan resultados finalizados de The Odds API. Cada selección se liquida como ganada, perdida, push o anulada; un cambio de estado solo se permite desde `pending`. El porcentaje histórico es `ganadas / (ganadas + perdidas)`, y la interfaz muestra también el tamaño de muestra.

## Límites del MVP

- La configuración inicial utiliza estadísticas de la temporada 2024 y momios de la región US; no son datos actuales de forma ni momios mexicanos.
- El modelo es experimental y no constituye una recomendación ni garantiza resultados.
- El MVP es de un solo usuario; antes del despliegue hay que configurar D1, secretos de proveedores, custom hostname y política de Cloudflare Access.
- Android queda fuera de alcance por ahora. Una aplicación móvil futura podría consumir la API del mismo Worker detrás de Access.

Las instrucciones de desarrollo y despliegue están en [cloudflare/README.md](../cloudflare/README.md).
