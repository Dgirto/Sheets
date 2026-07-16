# Conector Google Sheets (CON-006)

Conector Ruvic para Google Sheets (cuenta personal o Google Workspace).
Permite leer un rango, escribir/sobrescribir valores en un rango existente
y agregar filas nuevas al final de una tabla, usando OAuth2 con un refresh
token obtenido una única vez durante la configuración.

## Instalación

```bash
pip install git+https://github.com/Dgirto/Sheets.git#subdirectory=lib
```

Python 3.10+. Dependencias: `google-auth` y `google-api-python-client`.

## Obtener credenciales (una sola vez, por cuenta a conectar)

Si ya configuraste el conector Gmail (CON-005) para esta misma cuenta,
puedes **reutilizar el mismo proyecto de Google Cloud y la misma pantalla
de consentimiento OAuth** — solo falta habilitar la Sheets API y crear
(o reusar) un cliente OAuth con el scope de Sheets.

### 1. Proyecto y OAuth consent screen en Google Cloud Console

1. Crea (o reutiliza) un proyecto en [Google Cloud Console](https://console.cloud.google.com/).
2. Habilita la **Google Sheets API** (buscar "Google Sheets API" → Habilitar).
3. Configura la **pantalla de consentimiento OAuth** (APIs y servicios → Pantalla de consentimiento de OAuth) si no existe ya:
   - Tipo de usuario: **Externo** (obligatorio para cuentas personales; también funciona para Workspace).
   - Agrega el correo de la cuenta a conectar como **usuario de prueba**.

### 2. Cliente OAuth (tipo "Aplicación de escritorio")

1. APIs y servicios → **Credenciales** → **Crear credenciales → ID de cliente de OAuth**.
2. Tipo de aplicación: **Aplicación de escritorio**.
3. Anota el **Client ID** y **Client Secret** generados.

### 3. Obtener el refresh token (script incluido)

```bash
pip install google-auth-oauthlib
python get_refresh_token.py --client-id TU_CLIENT_ID --client-secret TU_CLIENT_SECRET
```

Se abre el navegador; inicia sesión con la cuenta dueña (o con acceso a)
las hojas de cálculo a usar y acepta los permisos. El script imprime
`client_id`, `client_secret` y `refresh_token` — esos tres valores van al
formulario del conector en Ruvic (o a las env vars para pruebas locales).

> **Importante:** mientras la app de OAuth esté en estado "Testing" en
> Google Cloud, el refresh token puede expirar a los 7 días de
> inactividad. Para uso productivo continuo, publica la app.

## Variables de entorno (`RUVIC_SHEETS_*`)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `RUVIC_SHEETS_CLIENT_ID` | Sí | Client ID del cliente OAuth de escritorio |
| `RUVIC_SHEETS_CLIENT_SECRET` | Sí | Client Secret del mismo cliente OAuth |
| `RUVIC_SHEETS_REFRESH_TOKEN` | Sí | Refresh token obtenido con `get_refresh_token.py` |
| `RUVIC_SHEETS_REQUEST_TIMEOUT` | No (default `30`) | Timeout de solicitud en segundos |

## Pruebas locales

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ./lib

export RUVIC_SHEETS_CLIENT_ID=xxxxx.apps.googleusercontent.com
export RUVIC_SHEETS_CLIENT_SECRET=xxxxx
export RUVIC_SHEETS_REFRESH_TOKEN=xxxxx

python test_connection.py

# Para validate_local.py se necesita además una hoja de prueba real,
# compartida con (o propiedad de) la cuenta que autorizó el refresh token,
# con una pestaña llamada "Hoja1":
export VALIDATE_SPREADSHEET_ID=<id_de_una_hoja_de_prueba>
python validate_local.py
```

Prueba también los casos de error (refresh token revocado, hoja
inexistente o no compartida con la cuenta, rango inválido) y verifica que
los mensajes sean claros.

## Notas de integración

- **OAuth2 de usuario**: igual que el conector Gmail (CON-005), usa el
  flujo OAuth2 "installed app" con refresh token — funciona con cuentas
  personales y con Google Workspace.
- **Acceso limitado a hojas compartidas**: el conector solo puede leer/escribir
  hojas de cálculo que estén compartidas con la cuenta que autorizó el
  refresh token (o de su propiedad). No tiene acceso a otros archivos de
  Drive ni puede listar hojas por sí solo — el `spreadsheet_id` lo debe
  aportar el usuario (de la URL de la hoja).
- **Alcance mínimo**: solo `https://www.googleapis.com/auth/spreadsheets`
  (lectura y escritura de valores). No puede crear, eliminar ni renombrar
  hojas de cálculo o pestañas, ni cambiar permisos de acceso.
- **`ping()`/`test_connection()`** no requieren una hoja de cálculo
  específica: solo verifican que el refresh token sea válido refrescando
  el access token directamente contra Google OAuth.
- **Expiración del refresh token**: no expira por tiempo si la app OAuth
  está publicada ("In production"); en estado "Testing" puede expirar a
  los 7 días sin uso.
- **Revocación**: si el refresh token se compromete, revócalo desde
  [myaccount.google.com/permissions](https://myaccount.google.com/permissions)
  y genera uno nuevo.
- Los errores HTTP 401/403 de la API se clasifican como `SheetsAuthError`;
  404 como `SheetsDataError`; 429 y 5xx como `SheetsNetworkError` (reintentable).

## Limitaciones conocidas

- Solo puede leer/escribir hojas de cálculo **compartidas con la cuenta
  autorizada** (o de su propiedad) — no puede descubrir ni listar hojas
  por sí solo, el `spreadsheet_id` lo debe aportar el usuario.
- No crea, elimina ni renombra hojas de cálculo o pestañas, ni cambia
  permisos de acceso — solo lee/escribe valores dentro de hojas
  existentes.
- El scope `spreadsheets` no distingue entre hojas específicas: la
  cuenta autorizada tiene el mismo nivel de acceso a **todas** las
  hojas que posee o tiene compartidas, no solo a las que use el agente.
- En modo "Usar credenciales propias" o "Refresh token manual" con una
  app OAuth en estado *Testing*, el refresh token puede expirar a los
  7 días sin uso — para uso continuo, publica la app o usa el modo
  "Autorizar con Google".
