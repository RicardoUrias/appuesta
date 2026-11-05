# Arquitectura del MVP web

## Componentes

- **Interfaz:** dashboard responsivo en `cloudflare/public/`, servido junto con la API desde el mismo Worker.
- **Backend:** Python Worker en `cloudflare/src/`. El navegador no llama directamente a los proveedores y no recibe sus credenciales.
- **Análisis compartido:** el Worker y el CLI utilizan `appuesta-core` desde `backend/app/`; el bundle del Worker se prepara como un wheel puro de Python.
- **Persistencia:** Cloudflare D1 guarda ejecuciones, cachés de respuestas y estadísticas, y picks inmutables con sus momios y resultados.
- **Proveedores:** API-Sports aporta posiciones, calendario, resultados recientes y detalle; The Odds API aporta momios y resultados para liquidar los picks.
- **Acceso:** Cloudflare Access protege el custom hostname. `workers_dev` y las preview URLs están desactivados.

## Flujo de análisis

1. El usuario solicita una búsqueda desde el dashboard.
2. `POST /api/analyze` consulta partidos/cuotas y resuelve equipos contra el catálogo de Liga MX.
3. Las estadísticas históricas se recuperan de D1 o API-Sports, respetando el máximo de consultas por búsqueda.
4. El modelo compartido calcula probabilidades y edge; las líneas enteras conservan por separado la probabilidad de push.
5. Se guardan hasta cinco selecciones nuevas, con unicidad por evento, mercado, resultado y línea.
6. El dashboard muestra cuotas, probabilidades, edge, EV y el origen experimental de los datos.

## Widgets de Liga MX y pronóstico

La tabla de posiciones, el calendario y el detalle se presentan con componentes propios del dashboard, pero los datos se consultan desde el Worker. La clave API-Sports permanece como secreto server-side; no se inserta en atributos HTML ni se entrega al JavaScript del navegador.

El pronóstico 1X2 usa el modelo Poisson compartido con goles a favor/en contra de los últimos cinco partidos completados que estén disponibles en la temporada de calendario actual. Si cualquiera de los equipos tiene menos de tres partidos recientes, el dashboard omite el pronóstico en vez de rellenar datos. Es una estimación experimental, no una recomendación.

Las respuestas de posiciones, calendario y forma se guardan en D1 para limitar llamadas repetidas. La tabla se refresca cada hora, el calendario cada 15 minutos, los resultados recientes cada seis horas y el detalle de partido cada cinco minutos.

## Historial y resultados

El Cron diario y `POST /api/sync` consultan resultados finalizados de The Odds API. Cada selección se liquida como ganada, perdida, push o anulada; un cambio de estado solo se permite desde `pending`. El porcentaje histórico es `ganadas / (ganadas + perdidas)`, y la interfaz muestra también el tamaño de muestra.

## Límites del MVP

- El Top 5 de valor todavía utiliza estadísticas de la temporada 2024 y momios de la región US; no son necesariamente datos actuales ni momios mexicanos. El nuevo panel de pronóstico sí usa partidos recientes de la temporada actual.
- El modelo es experimental y no constituye una recomendación ni garantiza resultados.
- El MVP es de un solo usuario; antes del despliegue hay que configurar D1, secretos de proveedores, custom hostname y política de Cloudflare Access.
- Android queda fuera de alcance por ahora. Una aplicación móvil futura podría consumir la API del mismo Worker detrás de Access.

Las instrucciones de desarrollo y despliegue están en [cloudflare/README.md](../cloudflare/README.md).
