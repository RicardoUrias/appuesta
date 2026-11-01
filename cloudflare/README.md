# APPuesta web en Cloudflare

El dashboard usa un Python Worker para las llamadas server-side a API-Sports y The Odds API, assets estáticos para la interfaz y D1 para picks e historial. La página muestra explícitamente que las estadísticas son históricas (temporada 2024 por defecto), las cuotas vienen de la región US y el modelo es experimental.

## Desarrollo local

Requisitos: Python 3.13+, Node.js 22+ y `uv`.

Desde la raíz del repositorio, instala el proyecto y crea los secretos locales:

```powershell
$env:SOURCE_DATE_EPOCH = "315532800"
uv build --project backend --wheel --out-dir backend/dist
uv lock --project cloudflare
uv sync --project cloudflare --locked
Copy-Item cloudflare/.dev.vars.example cloudflare/.dev.vars
Set-Location cloudflare
```

Completa `cloudflare/.dev.vars` con las claves reales. Ese archivo está excluido de Git.
Aplica la migración local e inicia el Worker:

```powershell
npx --yes --package=node@22 --package=wrangler@4 -- wrangler d1 migrations apply appuesta-db --local --config wrangler.toml
npx --yes --package=node@22 --package=wrangler@4 -- cmd /c "uv run pywrangler dev --config wrangler.toml"
```

Abre la URL local que imprime Pywrangler. La búsqueda consulta los proveedores reales; el historial y D1 local son independientes de producción.

## Preparar Cloudflare privado

1. Crea una base D1 llamada `appuesta-db` y copia su ID.
2. Agrega el ID como secreto `CLOUDFLARE_D1_DATABASE_ID` en GitHub. Configura también `CLOUDFLARE_ACCOUNT_ID` y `CLOUDFLARE_API_TOKEN`; el token necesita permisos para Workers Scripts y D1.
3. En Cloudflare, crea un custom domain o route para el Worker. No habilites `workers.dev`.
4. Protege el hostname con Cloudflare Access y verifica la política iniciando sesión en una ventana privada antes de compartir el enlace.
5. Guarda `API_SPORTS_KEY` y `ODDS_API_KEY` como secretos del Worker en Cloudflare. No los agregues a GitHub Pages, variables públicas ni al código del navegador.
6. Ejecuta el workflow **Deploy APPuesta web** desde GitHub o publica cambios en `main`. El workflow aplica las migraciones D1 remotas y despliega el Worker.

La configuración desactiva `workers.dev` y las preview URLs. No despliegues en producción hasta contar con el ID D1 real, el hostname protegido por Access y los secretos de proveedor configurados.

## Endpoints

- `GET /api/health`: comprueba que el Worker puede consultar D1.
- `GET /api/dashboard`: resumen, Top 5 de picks pendientes e historial.
- `POST /api/analyze`: consulta cuotas y, dentro del límite configurado, estadísticas históricas en caché; guarda hasta cinco picks nuevos.
- `POST /api/sync`: sincroniza y liquida picks con resultados finalizados.

El Cron diario ejecuta la misma sincronización de resultados. La tasa de acierto es `ganadas / (ganadas + perdidas)`; pendientes, pushes y anuladas se excluyen y el dashboard muestra el tamaño de muestra. Cada búsqueda limita las estadísticas nuevas a ocho equipos y separa sus solicitudes al ritmo configurado para respetar el plan gratuito.

## Pruebas

Desde la raíz del repositorio:

```powershell
$env:PYTHONPATH = "cloudflare;backend"
uv run --project cloudflare python -m unittest discover -s cloudflare/tests -v
Set-Location backend
& .\.venv\Scripts\python.exe -m unittest discover -s .\tests -v
```
