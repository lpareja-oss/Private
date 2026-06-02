"""
gmail_sync.py
Sincronización automática de Gmail → SQLite.
Parsea los emails de Novedades MLP - Logysto y guarda los datos en la BD.

Uso:
    python gmail_sync.py           # sincroniza y sale
    python gmail_sync.py --setup   # muestra instrucciones de configuración
"""

import os
import re
import sys
import json
from datetime import datetime, date
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

# ── Rutas de credenciales ──────────────────────────────────────────────────
CREDS_DIR   = os.path.join(os.path.dirname(__file__), "credentials")
CREDS_FILE  = os.path.join(CREDS_DIR, "credentials.json")
TOKEN_FILE  = os.path.join(CREDS_DIR, "token.json")

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Remitentes autorizados
ALLOWED_SENDERS = [
    "ext_yovilla@mercadolibre.com.co",
    "ext_santrinc@mercadolibre.com.co",
]
SUBJECT_FILTER = "subject:Reporte Novedades"


# ---------------------------------------------------------------------------
# Autenticación Gmail
# ---------------------------------------------------------------------------

def get_gmail_service():
    """
    Devuelve un servicio autenticado de Gmail API.
    Lanza RuntimeError si las credenciales no están configuradas.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError(
            "Dependencias de Google no instaladas. Ejecuta:\n"
            "  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )

    if not os.path.exists(CREDS_FILE):
        raise RuntimeError(
            f"Archivo de credenciales no encontrado: {CREDS_FILE}\n"
            "Ejecuta `python gmail_sync.py --setup` para ver instrucciones."
        )

    os.makedirs(CREDS_DIR, exist_ok=True)
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# ---------------------------------------------------------------------------
# Parseo de emails
# ---------------------------------------------------------------------------

def _normalize_date(raw: str) -> str:
    """Convierte fechas como '5/26/2026' o '26/5/2026' a 'YYYY-MM-DD'."""
    raw = raw.strip()
    try:
        # dateutil.parser maneja la mayoría de formatos
        dt = dateparser.parse(raw, dayfirst=False)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return raw


def _parse_html_table(html: str) -> list[dict]:
    """Extrae filas de la tabla HTML de novedades."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")
    if len(rows) < 2:
        return []

    # Cabeceras
    headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]

    COLUMN_MAP = {
        "fecha": "fecha",
        "mlp": "mlp",
        "ciudad": "ciudad",
        "milla": "milla",
        "operación": "operacion",
        "operacion": "operacion",
        "infractor": "infractor",
        "tipo": "tipo",
        "penalidad": "penalidad",
        "patente": "patente",
        "driver": "driver",
        "documento": "documento",
        "observación": "observacion",
        "observacion": "observacion",
    }

    novedades = []
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if not cells:
            continue
        row = {}
        for i, cell in enumerate(cells):
            if i < len(headers):
                key = COLUMN_MAP.get(headers[i], headers[i])
                row[key] = cell.get_text(separator=" ", strip=True)
        if row.get("fecha"):
            row["fecha"] = _normalize_date(row["fecha"])
        novedades.append(row)

    return novedades


def _detect_email_type(subject: str) -> str:
    s = subject.upper()
    if "SEMANAL" in s:
        return "SEMANAL"
    return "GRAVE_CRITICO"


def _extract_sender_alias(email_addr: str) -> str:
    return email_addr.split("@")[0]


# ---------------------------------------------------------------------------
# Sincronización principal
# ---------------------------------------------------------------------------

def sync_emails(max_results: int = 50) -> dict:
    """
    Descarga emails nuevos desde Gmail, los parsea y los guarda en la BD.
    Retorna un dict con {emails_processed, novedades_added, error}.
    """
    from database import get_connection, insert_novedades, log_sync

    result = {"emails_processed": 0, "novedades_added": 0, "error": None}

    try:
        service = get_gmail_service()
    except RuntimeError as e:
        result["error"] = str(e)
        return result

    # ── Obtener threads ya conocidos para no reprocesar ──────────────────
    conn = get_connection()
    known_threads = {
        row[0]
        for row in conn.execute("SELECT DISTINCT thread_id FROM novedades").fetchall()
    }
    conn.close()

    # ── Buscar threads en Gmail ──────────────────────────────────────────
    query = f"{SUBJECT_FILTER} ({' OR '.join(f'from:{s}' for s in ALLOWED_SENDERS)})"
    threads_resp = (
        service.users()
        .threads()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    threads = threads_resp.get("threads", [])

    new_rows = []
    processed = 0

    for t in threads:
        thread_id = t["id"]
        if thread_id in known_threads:
            continue  # ya procesado

        thread_data = (
            service.users()
            .threads()
            .get(userId="me", id=thread_id, format="full")
            .execute()
        )

        for msg in thread_data.get("messages", []):
            msg_id = msg["id"]
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}

            sender_raw = headers.get("From", "")
            sender_email = re.search(r"[\w.+-]+@[\w.+-]+", sender_raw)
            if not sender_email:
                continue
            sender_email = sender_email.group(0).lower()
            if sender_email not in ALLOWED_SENDERS:
                continue  # respuesta de otro remitente → ignorar

            subject = headers.get("Subject", "")
            email_date_raw = headers.get("Date", "")
            try:
                email_date = dateparser.parse(email_date_raw).strftime("%Y-%m-%d")
            except Exception:
                email_date = date.today().isoformat()

            email_type = _detect_email_type(subject)

            # Extraer HTML del cuerpo
            html_body = _get_html_body(msg["payload"])
            if not html_body:
                continue

            rows = _parse_html_table(html_body)
            for i, row in enumerate(rows):
                unique_msg_id = msg_id if len(rows) == 1 else f"{msg_id}_row{i+1}"
                new_rows.append(
                    {
                        "thread_id": thread_id,
                        "message_id": unique_msg_id,
                        "email_date": email_date,
                        "email_type": email_type,
                        "sender": _extract_sender_alias(sender_email),
                        "fecha": row.get("fecha", ""),
                        "mlp": row.get("mlp", "Logysto"),
                        "ciudad": row.get("ciudad", ""),
                        "milla": row.get("milla", ""),
                        "operacion": row.get("operacion", ""),
                        "infractor": row.get("infractor", ""),
                        "tipo": row.get("tipo", ""),
                        "penalidad": row.get("penalidad", ""),
                        "patente": row.get("patente", ""),
                        "driver": row.get("driver", ""),
                        "documento": row.get("documento", ""),
                        "observacion": row.get("observacion", ""),
                    }
                )
            processed += 1

    # ── Insertar en BD ───────────────────────────────────────────────────
    if new_rows:
        added = insert_novedades(new_rows)
        result["novedades_added"] = added

    result["emails_processed"] = processed
    if processed > 0 or len(new_rows) > 0:
        log_sync(processed, result["novedades_added"])

    return result


def _get_html_body(payload: dict) -> str | None:
    """Extrae el cuerpo HTML de un mensaje de Gmail (recursivo)."""
    import base64

    mime = payload.get("mimeType", "")
    if mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")

    for part in payload.get("parts", []):
        result = _get_html_body(part)
        if result:
            return result

    return None


# ---------------------------------------------------------------------------
# Instrucciones de setup
# ---------------------------------------------------------------------------

SETUP_INSTRUCTIONS = """
╔══════════════════════════════════════════════════════════════════════════╗
║          CONFIGURACIÓN DE GMAIL API  — Novedades MLP Dashboard          ║
╚══════════════════════════════════════════════════════════════════════════╝

Pasos para activar la sincronización automática de Gmail:

1. Ve a https://console.cloud.google.com/
2. Crea un proyecto nuevo (ej: "novedades-mlp-dashboard")
3. En el menú lateral: APIs y servicios → Biblioteca
   → Busca "Gmail API" → Habilitar

4. APIs y servicios → Pantalla de consentimiento OAuth
   → Tipo: Externo → Completa nombre y correo
   → Agrega tu correo como "usuario de prueba"

5. APIs y servicios → Credenciales
   → + Crear credenciales → ID de cliente OAuth 2.0
   → Tipo: Aplicación de escritorio
   → Descarga el JSON → guárdalo como:

   credentials\\credentials.json
   (dentro de la carpeta del proyecto)

6. Ejecuta por primera vez:
   python gmail_sync.py

   → Se abrirá el navegador para autorizar acceso
   → Después queda guardado automáticamente en credentials\\token.json

7. ¡Listo! El botón "Sincronizar Gmail" en el dashboard funcionará.

💡 También podés programar la sync automática con el Programador de tareas
   de Windows para que corra, por ejemplo, cada hora.
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--setup" in sys.argv:
        print(SETUP_INSTRUCTIONS)
        sys.exit(0)

    # Inicializar BD (seed si está vacía)
    from database import init_db
    init_db()

    print("🔄 Sincronizando emails desde Gmail...")
    result = sync_emails()

    if result["error"]:
        print(f"⚠️  No se pudo conectar a Gmail: {result['error']}")
        print("   Ejecuta `python gmail_sync.py --setup` para configurar.")
    else:
        print(
            f"✅ Listo — {result['emails_processed']} emails procesados, "
            f"{result['novedades_added']} novedades nuevas."
        )
