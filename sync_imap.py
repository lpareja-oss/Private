"""
sync_imap.py
Sincronización de Gmail via IMAP — sin necesidad de Google Cloud API.
Solo requiere una Contraseña de Aplicación de Gmail.

Uso:
    python sync_imap.py              → sincroniza correos nuevos
    python sync_imap.py --configurar → asistente de configuración
"""

import imaplib
import email
import os
import sys
import re
from email.header import decode_header as _decode_header
from datetime import datetime
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config_sync.txt")

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

ALLOWED_SENDERS = [
    "ext_yovilla@mercadolibre.com.co",
    "ext_santrinc@mercadolibre.com.co",
]
SUBJECT_KEYWORDS = ["Reporte Novedades"]


# ─── Configuración ──────────────────────────────────────────────────────────

def leer_config() -> dict | None:
    """Lee credenciales Gmail desde variables de entorno (cloud) o config_sync.txt (local)."""
    # Primero: variables de entorno (Streamlit Cloud secrets)
    env_user = os.environ.get("GMAIL_USER", "")
    env_pass = os.environ.get("GMAIL_APP_PASSWORD", "")
    if env_user and env_pass:
        return {"GMAIL_USER": env_user, "GMAIL_APP_PASSWORD": env_pass}
    # Segundo: archivo local
    if not os.path.exists(CONFIG_FILE):
        return None
    config = {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip()
    return config if "GMAIL_USER" in config and "GMAIL_APP_PASSWORD" in config else None


def guardar_config(usuario: str, password: str) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write("# Configuración de sincronización Gmail\n")
        f.write("# NO compartir este archivo — contiene tu contraseña de aplicación\n\n")
        f.write(f"GMAIL_USER={usuario}\n")
        f.write(f"GMAIL_APP_PASSWORD={password}\n")
    print(f"\n✅  Configuración guardada en {CONFIG_FILE}")


# ─── Asistente de configuración ─────────────────────────────────────────────

def asistente_configuracion():
    print("=" * 60)
    print("  Configuracion de Sincronizacion Gmail - Novedades MLP")
    print("=" * 60)
    print("""
Para sincronizar automaticamente los correos necesitas una
"Contrasena de Aplicacion" de Google. Es diferente a tu
contrasena normal y solo da acceso de lectura a los correos.

PASOS (2 minutos):
------------------
1. Abre: https://myaccount.google.com/apppasswords
   (inicia sesion con tu cuenta lpareja@clicoh.com)

2. En "Seleccionar aplicacion" elige > "Correo"
   En "Seleccionar dispositivo"   > "Ordenador con Windows"

3. Haz clic en "Generar"

4. Google muestra una clave de 16 letras: xxxx xxxx xxxx xxxx
   Copiala (con o sin espacios, da igual)

5. Vuelve aqui y pegala cuando se pida.

NOTA: Si ves "Las contrasenas de aplicacion no estan disponibles"
      activa primero Verificacion en 2 pasos en:
      https://myaccount.google.com/security

""")
    usuario = input("Tu correo Gmail (ej: lpareja@clicoh.com): ").strip()
    if not usuario:
        print("Correo vacío, cancelado.")
        return

    print("\nAbriendo https://myaccount.google.com/apppasswords en el navegador...")
    import subprocess
    subprocess.Popen(["start", "https://myaccount.google.com/apppasswords"], shell=True)

    password = input("\nPegá la contraseña de aplicación de 16 caracteres: ").strip()
    password = password.replace(" ", "")  # quitar espacios

    if len(password) != 16:
        print(f"⚠️  La clave debería tener 16 caracteres (tiene {len(password)}). Verificá que copiaste bien.")
        confirmar = input("¿Guardar igual? (s/n): ").strip().lower()
        if confirmar != "s":
            return

    # Probar conexión antes de guardar
    print("\nProbando conexión con Gmail...")
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(usuario, password)
        mail.logout()
        print("✅  Conexión exitosa!")
        guardar_config(usuario, password)
        print("\nListo. Ejecutá  python sync_imap.py  para sincronizar.")
    except imaplib.IMAP4.error as e:
        print(f"\n❌  Error de autenticación: {e}")
        print("   Verificá que la contraseña de aplicación sea correcta.")
    except Exception as e:
        print(f"\n❌  Error de conexión: {e}")


# ─── Parser de correos ───────────────────────────────────────────────────────

def _decode_str(value: str) -> str:
    parts = _decode_header(value)
    result = ""
    for part, charset in parts:
        if isinstance(part, bytes):
            result += part.decode(charset or "utf-8", errors="ignore")
        else:
            result += part
    return result


def _normalize_date(raw: str) -> str:
    raw = (raw or "").strip()
    try:
        return dateparser.parse(raw, dayfirst=False).strftime("%Y-%m-%d")
    except Exception:
        return raw


def _parse_html_table(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        return []
    rows = table.find_all("tr")
    if len(rows) < 2:
        return []

    COLUMN_MAP = {
        "fecha": "fecha", "mlp": "mlp", "ciudad": "ciudad", "milla": "milla",
        "operación": "operacion", "operacion": "operacion",
        "infractor": "infractor", "tipo": "tipo", "penalidad": "penalidad",
        "patente": "patente", "driver": "driver", "documento": "documento",
        "observación": "observacion", "observacion": "observacion",
    }
    headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]

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
        if any(row.values()):
            novedades.append(row)
    return novedades


def _get_html_body(msg) -> str | None:
    """Extrae el cuerpo HTML de un mensaje email.message.Message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                charset = part.get_content_charset() or "utf-8"
                return part.get_payload(decode=True).decode(charset, errors="ignore")
    else:
        if msg.get_content_type() == "text/html":
            charset = msg.get_content_charset() or "utf-8"
            return msg.get_payload(decode=True).decode(charset, errors="ignore")
    return None


def _detect_email_type(subject: str) -> str:
    return "SEMANAL" if "SEMANAL" in subject.upper() else "GRAVE_CRITICO"


def _get_thread_root(msg, own_msg_id: str) -> str:
    """
    Devuelve el Message-ID raíz del hilo de conversación.

    Estrategia (de mayor a menor prioridad):
    1. References header → primer ID = raíz del hilo completo.
       Todos los correos de una cadena A→B→C→respuesta comparten la misma raíz.
    2. In-Reply-To → mensaje inmediatamente anterior.
    3. Propio Message-ID → es el correo raíz.

    Esto garantiza que dos novedades del mismo hilo Y la respuesta de ClicOH
    compartan el mismo thread_id aunque la respuesta llegue como Reply al
    mensaje más reciente, no al primero.
    """
    references = msg.get("References", "").strip()
    if references:
        return references.split()[0]   # primer ID de la cadena = raíz
    in_reply_to = msg.get("In-Reply-To", "").strip()
    if in_reply_to:
        return in_reply_to
    return own_msg_id


def _clasificar_respuesta(texto: str) -> str:
    """
    Clasifica el nivel de respuesta de ClicOH a partir del texto del correo.

    Niveles:
      'Resuelto'         → confirma que la novedad fue corregida/subsanada
      'En gestion'       → indica que se está gestionando / escalando
      'Acuse de recibo'  → solo acusa recibo sin comprometerse a acción
    """
    t = texto.lower()

    resuelto_kw = [
        "resuelto", "solucionado", "corregido", "subsanado",
        "ya fue", "ya se realizo", "ya se realizó", "problema solucionado",
        "novedad corregida", "se corrigio", "se corrigió",
    ]
    gestion_kw = [
        "escalamos", "procederemos", "procederá", "se procederá",
        "se procedera", "gestionando", "en proceso", "dar pronta solucion",
        "inhouse", "ya escalamos", "tomaremos", "se tomaran", "se tomarán",
        "se va a corregir", "se realizará", "se realizara",
    ]

    if any(k in t for k in resuelto_kw):
        return "Resuelto"
    if any(k in t for k in gestion_kw):
        return "En gestion"
    return "Acuse de recibo"


def _get_plain_text(msg) -> str:
    """Extrae texto plano de un mensaje (para clasificar respuestas)."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                return part.get_payload(decode=True).decode(charset, errors="ignore")
    else:
        if msg.get_content_type() == "text/plain":
            charset = msg.get_content_charset() or "utf-8"
            return msg.get_payload(decode=True).decode(charset, errors="ignore")
    return ""


# ─── Sincronización principal ────────────────────────────────────────────────

def sync_emails() -> dict:
    """
    Conecta a Gmail via IMAP, descarga correos nuevos (novedades y respuestas).
    Retorna {"emails_processed", "novedades_added", "respuestas_added", "error"}
    """
    from database import (
        get_connection, insert_novedades, insert_respuestas, log_sync
    )

    result = {
        "emails_processed": 0,
        "novedades_added": 0,
        "respuestas_added": 0,
        "error": None,
    }

    config = leer_config()
    if not config:
        result["error"] = (
            "Sincronizacion no configurada. "
            "Ejecuta: python sync_imap.py --configurar"
        )
        return result

    usuario  = config["GMAIL_USER"]
    password = config["GMAIL_APP_PASSWORD"]

    # IDs ya conocidos — compatible con sqlite3 y psycopg2
    def _q(conn, sql):
        try:
            return conn.execute(sql).fetchall()
        except AttributeError:
            cur = conn.cursor()
            cur.execute(sql)
            return cur.fetchall()

    conn = get_connection()
    known_novedad_ids  = {row[0] for row in _q(conn, "SELECT message_id FROM novedades")}
    known_respuesta_ids = {row[0] for row in _q(conn, "SELECT message_id FROM respuestas")}
    thread_dates = {
        row[0]: row[1]
        for row in _q(conn, "SELECT thread_id, MIN(email_date) FROM novedades GROUP BY thread_id")
    }
    conn.close()

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(usuario, password)
        mail.select("INBOX")
    except Exception as e:
        result["error"] = f"Error conectando a Gmail: {e}"
        return result

    # ── 1. Novedades nuevas de ext_yovilla / ext_santrinc ────────────────
    all_uids = set()
    for sender in ALLOWED_SENDERS:
        for keyword in SUBJECT_KEYWORDS:
            _, data = mail.search(None, f'FROM "{sender}" SUBJECT "{keyword}"')
            uids = data[0].split() if data[0] else []
            all_uids.update(uids)

    # ── 2. Respuestas de @clicoh.com con Re: en el asunto ────────────────
    _, reply_data = mail.search(
        None, 'FROM "@clicoh.com" SUBJECT "Re:" SUBJECT "Novedades"'
    )
    reply_uids = reply_data[0].split() if reply_data[0] else []

    new_novedades = []
    new_respuestas = []
    processed = 0

    # ── Procesar novedades ───────────────────────────────────────────────
    for uid in all_uids:
        _, msg_data = mail.fetch(uid, "(RFC822)")
        if not msg_data or not msg_data[0]:
            continue

        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        gmail_msg_id = (msg.get("Message-ID") or uid.decode()).strip()
        if gmail_msg_id in known_novedad_ids:
            continue

        sender_raw = _decode_str(msg.get("From", ""))
        sender_match = re.search(r"[\w.+\-]+@[\w.\-]+", sender_raw)
        if not sender_match:
            continue
        sender_email = sender_match.group(0).lower()
        if sender_email not in ALLOWED_SENDERS:
            continue

        date_raw = msg.get("Date", "")
        try:
            email_date = dateparser.parse(date_raw).strftime("%Y-%m-%d")
        except Exception:
            email_date = datetime.today().strftime("%Y-%m-%d")

        subject    = _decode_str(msg.get("Subject", ""))
        email_type = _detect_email_type(subject)
        thread_id  = _get_thread_root(msg, gmail_msg_id)

        html_body = _get_html_body(msg)
        if not html_body:
            continue

        rows = _parse_html_table(html_body)
        for i, row in enumerate(rows):
            unique_id = gmail_msg_id if len(rows) == 1 else f"{gmail_msg_id}_row{i+1}"
            new_novedades.append({
                "thread_id":   thread_id,
                "message_id":  unique_id,
                "email_date":  email_date,
                "email_type":  email_type,
                "sender":      sender_email.split("@")[0],
                "fecha":       row.get("fecha", ""),
                "mlp":         row.get("mlp", "Logysto"),
                "ciudad":      row.get("ciudad", ""),
                "milla":       row.get("milla", ""),
                "operacion":   row.get("operacion", ""),
                "infractor":   row.get("infractor", ""),
                "tipo":        row.get("tipo", ""),
                "penalidad":   row.get("penalidad", ""),
                "patente":     row.get("patente", ""),
                "driver":      row.get("driver", ""),
                "documento":   row.get("documento", ""),
                "observacion": row.get("observacion", ""),
            })
            # Registrar thread_id → fecha para calcular tiempos de respuesta
            if thread_id not in thread_dates:
                thread_dates[thread_id] = email_date
        processed += 1

    # ── Procesar respuestas de @clicoh.com ───────────────────────────────
    for uid in reply_uids:
        _, msg_data = mail.fetch(uid, "(RFC822)")
        if not msg_data or not msg_data[0]:
            continue

        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        gmail_msg_id = (msg.get("Message-ID") or uid.decode()).strip()
        if gmail_msg_id in known_respuesta_ids:
            continue

        sender_raw = _decode_str(msg.get("From", ""))
        sender_match = re.search(r"[\w.+\-]+@[\w.\-]+", sender_raw)
        if not sender_match:
            continue
        sender_email = sender_match.group(0).lower()
        if "@clicoh.com" not in sender_email:
            continue

        date_raw = msg.get("Date", "")
        try:
            reply_dt   = dateparser.parse(date_raw)
            reply_date = reply_dt.strftime("%Y-%m-%d")
        except Exception:
            reply_dt   = datetime.today()
            reply_date = reply_dt.strftime("%Y-%m-%d")

        # Relacionar con thread original usando la raíz del hilo
        thread_id = _get_thread_root(msg, gmail_msg_id)

        # Calcular tiempo de respuesta
        orig_date_str = thread_dates.get(thread_id)
        tiempo_min = None
        if orig_date_str:
            try:
                orig_dt    = dateparser.parse(orig_date_str)
                delta      = reply_dt - orig_dt
                tiempo_min = int(delta.total_seconds() / 60)
            except Exception:
                pass

        # Extraer texto para clasificar
        texto = _get_plain_text(msg)
        # Quitar el cuerpo citado (líneas que empiezan con >)
        texto_limpio = "\n".join(
            l for l in texto.splitlines() if not l.strip().startswith(">")
        ).strip()

        nivel = _clasificar_respuesta(texto_limpio)

        new_respuestas.append({
            "thread_id":            thread_id,
            "message_id":           gmail_msg_id,
            "reply_date":           reply_date,
            "responder":            sender_email,
            "texto":                texto_limpio[:1000],
            "nivel":                nivel,
            "tiempo_respuesta_min": tiempo_min,
        })

    mail.logout()

    if new_novedades:
        added = insert_novedades(new_novedades)
        result["novedades_added"] = added

    if new_respuestas:
        resp_added = insert_respuestas(new_respuestas)
        result["respuestas_added"] = resp_added

    if new_novedades or new_respuestas:
        log_sync(processed, result["novedades_added"])

    result["emails_processed"] = processed
    return result


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--configurar" in sys.argv:
        asistente_configuracion()
        sys.exit(0)

    from database import init_db
    init_db()

    print("Sincronizando correos desde Gmail...")
    r = sync_emails()

    if r["error"]:
        print(f"\nAviso: {r['error']}")
    else:
        print(
            f"Listo — {r['emails_processed']} correos procesados, "
            f"{r['novedades_added']} novedades nuevas agregadas."
        )
