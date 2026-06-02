"""
database.py
Gestión de la base de datos para Novedades MLP - Logysto.
Soporta SQLite (local/dev) y PostgreSQL (Supabase/cloud).
Detecta automáticamente el backend según la variable DATABASE_URL.
"""

import os
import sqlite3
import pandas as pd

# ── Detección de backend ──────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "novedades.db")


def _is_pg() -> bool:
    return bool(os.environ.get("DATABASE_URL", ""))


def _get_db_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    # Supabase a veces entrega "postgres://" — psycopg2 requiere "postgresql://"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    # Asegurar SSL para conexiones en la nube (requerido por Supabase)
    if url and "sslmode" not in url:
        sep = "&" if "?" in url else "?"
        url += f"{sep}sslmode=require"
    return url


def _conn():
    if _is_pg():
        import psycopg2
        return psycopg2.connect(_get_db_url())
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _select_df(conn, query: str) -> pd.DataFrame:
    """Ejecuta un SELECT y retorna DataFrame — compatible con ambos backends."""
    if _is_pg():
        import psycopg2.extras
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()
            if not rows:
                return pd.DataFrame()
            return pd.DataFrame([dict(r) for r in rows])
    return pd.read_sql_query(query, conn)


def _insert_q(table: str, fields: list, conflict_col: str = "message_id") -> str:
    """Genera la sentencia INSERT adecuada para el backend activo."""
    cols = ", ".join(fields)
    if _is_pg():
        vals = ", ".join(f"%({f})s" for f in fields)
        return (
            f"INSERT INTO {table} ({cols}) VALUES ({vals}) "
            f"ON CONFLICT ({conflict_col}) DO NOTHING"
        )
    vals = ", ".join(f":{f}" for f in fields)
    return f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({vals})"


# ── DDL ───────────────────────────────────────────────────────────────────

_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS novedades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id     TEXT    NOT NULL,
    message_id    TEXT    NOT NULL UNIQUE,
    email_date    TEXT    NOT NULL,
    email_type    TEXT    NOT NULL,
    sender        TEXT    NOT NULL,
    fecha         TEXT,
    mlp           TEXT,
    ciudad        TEXT,
    milla         TEXT,
    operacion     TEXT,
    infractor     TEXT,
    tipo          TEXT,
    penalidad     TEXT,
    patente       TEXT,
    driver        TEXT,
    documento     TEXT,
    observacion   TEXT,
    created_at    TEXT    DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS respuestas (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id            TEXT    NOT NULL,
    message_id           TEXT    NOT NULL UNIQUE,
    reply_date           TEXT    NOT NULL,
    responder            TEXT    NOT NULL,
    texto                TEXT,
    nivel                TEXT    NOT NULL,
    tiempo_respuesta_min INTEGER,
    created_at           TEXT    DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sync_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    synced_at        TEXT    DEFAULT CURRENT_TIMESTAMP,
    emails_processed INTEGER DEFAULT 0,
    novedades_added  INTEGER DEFAULT 0
);
"""

_DDL_PG = [
    """CREATE TABLE IF NOT EXISTS novedades (
        id            SERIAL PRIMARY KEY,
        thread_id     TEXT    NOT NULL,
        message_id    TEXT    NOT NULL UNIQUE,
        email_date    TEXT    NOT NULL,
        email_type    TEXT    NOT NULL,
        sender        TEXT    NOT NULL,
        fecha         TEXT,
        mlp           TEXT,
        ciudad        TEXT,
        milla         TEXT,
        operacion     TEXT,
        infractor     TEXT,
        tipo          TEXT,
        penalidad     TEXT,
        patente       TEXT,
        driver        TEXT,
        documento     TEXT,
        observacion   TEXT,
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS respuestas (
        id                   SERIAL PRIMARY KEY,
        thread_id            TEXT    NOT NULL,
        message_id           TEXT    NOT NULL UNIQUE,
        reply_date           TEXT    NOT NULL,
        responder            TEXT    NOT NULL,
        texto                TEXT,
        nivel                TEXT    NOT NULL,
        tiempo_respuesta_min INTEGER,
        created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS sync_log (
        id               SERIAL PRIMARY KEY,
        synced_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        emails_processed INTEGER DEFAULT 0,
        novedades_added  INTEGER DEFAULT 0
    )""",
]


# ── Seed: datos históricos recopilados desde Gmail ─────────────────────────

SEED_NOVEDADES = [
    {
        "thread_id": "19e660890b5633a7", "message_id": "19e660890b5633a7",
        "email_date": "2026-05-26", "email_type": "GRAVE_CRITICO", "sender": "ext_yovilla",
        "fecha": "2026-05-26", "mlp": "Logysto", "ciudad": "Bogota", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Vehiculos",
        "tipo": "Manipulación de paquetería por personal no programado",
        "penalidad": "Grave", "patente": "VEZ662", "driver": "Carlos Andrés Puerta Rojas",
        "documento": "",
        "observacion": "El vehículo no tiene auxiliar programado; sin embargo, el conductor se encuentra acompañado y ambas personas están manipulando la paquetería.",
    },
    {
        "thread_id": "19e5fc7450751872", "message_id": "19e5fc7450751872",
        "email_date": "2026-05-25", "email_type": "GRAVE_CRITICO", "sender": "ext_yovilla",
        "fecha": "2026-05-25", "mlp": "Logysto", "ciudad": "Pereira", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Vehiculos", "tipo": "Con daño estructural",
        "penalidad": "Grave", "patente": "VFC069", "driver": "Nobey Giraldo Diaz",
        "documento": "79891460",
        "observacion": "Se evidencia daño estructural en el vehículo.",
    },
    {
        "thread_id": "19e4b4f4049be064", "message_id": "19e4b4f4049be064",
        "email_date": "2026-05-21", "email_type": "GRAVE_CRITICO", "sender": "ext_yovilla",
        "fecha": "2026-05-20", "mlp": "Logysto", "ciudad": "Bogota", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Vehiculos", "tipo": "Vehículo varado en la nave",
        "penalidad": "Critico", "patente": "WMM355", "driver": "Johan Steven Mendoza Herrera",
        "documento": "1019091144",
        "observacion": "Vehículo no ingresa; al encontrarse en el patio, presenta falla mecánica y queda varado.",
    },
    {
        "thread_id": "19e1d2f338bae527", "message_id": "19e1d2f338bae527",
        "email_date": "2026-05-12", "email_type": "GRAVE_CRITICO", "sender": "ext_yovilla",
        "fecha": "2026-05-12", "mlp": "Logysto", "ciudad": "Barranquilla", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Vehiculos", "tipo": "Vehículo varado en la nave",
        "penalidad": "Grave", "patente": "SWS212", "driver": "Alvaro Marco Abello Arroyo",
        "documento": "19131531",
        "observacion": "La unidad de carga realiza proceso de cargue de mercancía; sin embargo, al momento de realizar la salida el vehículo no enciende. Fue retirado (empujado) y la ruta despachada en otro vehículo.",
    },
    {
        "thread_id": "19e2c1eb44fac7e1", "message_id": "19e2c1eb44fac7e1",
        "email_date": "2026-05-15", "email_type": "SEMANAL", "sender": "ext_yovilla",
        "fecha": "2026-05-08", "mlp": "Logysto", "ciudad": "Bogota", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Driver", "tipo": "Sin QR ARL",
        "penalidad": "Leve", "patente": "WFL608", "driver": "Javier Cajamarca Lopez",
        "documento": "79569768",
        "observacion": "Se realiza validación manual y se permite el ingreso.",
    },
    {
        "thread_id": "19e0890e457f8c81", "message_id": "19e0890e457f8c81",
        "email_date": "2026-05-08", "email_type": "GRAVE_CRITICO", "sender": "ext_yovilla",
        "fecha": "2026-05-07", "mlp": "Logysto", "ciudad": "Bogota", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Vehiculos",
        "tipo": "Vehículo sin auxiliar con servicio programado con auxiliar",
        "penalidad": "Critico", "patente": "UFY864", "driver": "Jhon Esneider Misas Lopez",
        "documento": "1152203039",
        "observacion": "Se reporta que el vehículo no lleva auxiliar y está programado con servicio que requiere auxiliar.",
    },
    {
        "thread_id": "19e03b0e0027c0c2", "message_id": "19e03b0e0027c0c2",
        "email_date": "2026-05-07", "email_type": "GRAVE_CRITICO", "sender": "ext_yovilla",
        "fecha": "2026-05-06", "mlp": "Logysto", "ciudad": "Medellin", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Vehiculos",
        "tipo": "Vehículo sin auxiliar con servicio programado con auxiliar",
        "penalidad": "Critico", "patente": "SNR801", "driver": "Jhon Edwin Hernandez Velez",
        "documento": "1035430720",
        "observacion": "Se reporta que el vehículo no lleva auxiliar y está programado con servicio que requiere auxiliar.",
    },
    {
        "thread_id": "19df3edc61f2cc4d", "message_id": "19df3edc61f2cc4d",
        "email_date": "2026-05-04", "email_type": "GRAVE_CRITICO", "sender": "ext_yovilla",
        "fecha": "2026-05-04", "mlp": "Logysto", "ciudad": "Medellin", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Vehiculos",
        "tipo": "Puertas no ajustan de manera correcta",
        "penalidad": "Grave", "patente": "WEX620", "driver": "Yeison Galeano",
        "documento": "1037612238",
        "observacion": "No se permite el ingreso, hasta realizar las correcciones.",
    },
    {
        "thread_id": "19de3f17f3b8e74c", "message_id": "19de3f17f3b8e74c_row1",
        "email_date": "2026-05-01", "email_type": "SEMANAL", "sender": "ext_yovilla",
        "fecha": "2026-04-27", "mlp": "Logysto", "ciudad": "Bogota", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Vehiculos", "tipo": "Actos inseguros detectados",
        "penalidad": "Leve", "patente": "WCX421",
        "driver": "Jeisson Steven Salamanca Castañeda", "documento": "",
        "observacion": "Se reporta acto inseguro: vehículo ingresa en contravía sobre la carrera 39 para realizar la entrega de devoluciones.",
    },
    {
        "thread_id": "19de3f17f3b8e74c", "message_id": "19de3f17f3b8e74c_row2",
        "email_date": "2026-05-01", "email_type": "SEMANAL", "sender": "ext_yovilla",
        "fecha": "2026-04-23", "mlp": "Logysto", "ciudad": "Cali", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Vehiculos", "tipo": "Estacionarias dañadas",
        "penalidad": "Moderada", "patente": "TGX985",
        "driver": "James Orlando Hernandez Anacona", "documento": "94285507",
        "observacion": "Vehículo con luces estacionarias dañadas. LP autoriza el despacho con el compromiso de realizar la reparación el día de hoy.",
    },
    {
        "thread_id": "19db595f40f5d517", "message_id": "19db595f40f5d517",
        "email_date": "2026-04-22", "email_type": "GRAVE_CRITICO", "sender": "ext_santrinc",
        "fecha": "2026-04-22", "mlp": "Logysto", "ciudad": "Bogota", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Vehiculos",
        "tipo": "Puerta posterior con vidrio sin película de seguridad",
        "penalidad": "Critico", "patente": "THX000",
        "driver": "Cristian Camilo Tovar Jaimes", "documento": "1010211100",
        "observacion": "Riesgo: Alta exposición visual de la mercancía ante terceros. Recomendación: instalación de película de seguridad oscurecida.",
    },
    {
        "thread_id": "19dbfe50a6c8ffc2", "message_id": "19dbfe50a6c8ffc2",
        "email_date": "2026-04-24", "email_type": "SEMANAL", "sender": "ext_yovilla",
        "fecha": "2026-04-21", "mlp": "Logysto", "ciudad": "Bogota", "milla": "Last Mile",
        "operacion": "AMT", "infractor": "Vehiculos", "tipo": "Vidrios sin polarizado",
        "penalidad": "Leve", "patente": "WER710",
        "driver": "Miguel Angel Vargas Montoya", "documento": "1017261179",
        "observacion": "Riesgo: Alta exposición visual de la mercancía ante terceros. Recomendación: instalación de película de seguridad oscurecida.",
    },
    {
        "thread_id": "19db03ca010d0ae7", "message_id": "19db03ca010d0ae7",
        "email_date": "2026-04-21", "email_type": "GRAVE_CRITICO", "sender": "ext_yovilla",
        "fecha": "2026-04-21", "mlp": "Logysto", "ciudad": "Bogota", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Driver", "tipo": "Sin documentos físicos",
        "penalidad": "Critico", "patente": "UFZ870",
        "driver": "Manuel Dario Wiches Bejarano", "documento": "10005222210",
        "observacion": "Driver se presenta sin documento de identidad (cédula) y sin licencia de conducción.",
    },
    {
        "thread_id": "19d9bd8758430389", "message_id": "19d9bd8758430389_row1",
        "email_date": "2026-04-17", "email_type": "SEMANAL", "sender": "ext_yovilla",
        "fecha": "2026-04-10", "mlp": "Logysto", "ciudad": "Bogota", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Vehiculos",
        "tipo": "Mal estado físico del vehículo",
        "penalidad": "Leve", "patente": "TTT395",
        "driver": "Luis David Caicedo Sinisterra", "documento": "1005877028",
        "observacion": "Se reporta vehículo en estado físico deteriorado. Se evidencia que la tapa del tanque no se encuentra.",
    },
    {
        "thread_id": "19d9bd8758430389", "message_id": "19d9bd8758430389_row2",
        "email_date": "2026-04-17", "email_type": "SEMANAL", "sender": "ext_yovilla",
        "fecha": "2026-04-13", "mlp": "Logysto", "ciudad": "Bogota", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Vehiculos",
        "tipo": "Novedad soporte espejo",
        "penalidad": "Leve", "patente": "WMM355",
        "driver": "Joan Sebastian Alvarez Urbano", "documento": "1004440237",
        "observacion": "Unidad de carga ingresa con soporte de espejo lateral asegurado con cinta, evidenciando posible daño o reparación provisional.",
    },
    {
        "thread_id": "19d92529ec2897e3", "message_id": "19d92529ec2897e3",
        "email_date": "2026-04-15", "email_type": "GRAVE_CRITICO", "sender": "ext_santrinc",
        "fecha": "2026-04-13", "mlp": "Logysto", "ciudad": "Cali", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Vehiculos",
        "tipo": "Puerta posterior con vidrio sin película de seguridad",
        "penalidad": "Grave", "patente": "VCZ365",
        "driver": "Maria Ofelia Gómez Castillo", "documento": "31533419",
        "observacion": "Riesgo: Alta exposición visual de la mercancía ante terceros. Recomendación: instalación de película de seguridad oscurecida.",
    },
    {
        "thread_id": "19d92529ec2897e3", "message_id": "19d92538a4cd2315",
        "email_date": "2026-04-15", "email_type": "GRAVE_CRITICO", "sender": "ext_santrinc",
        "fecha": "2026-04-13", "mlp": "Logysto", "ciudad": "Bogota", "milla": "Last Mile",
        "operacion": "SVC", "infractor": "Vehiculos", "tipo": "Vehículo pinchado",
        "penalidad": "Critico", "patente": "SPS860",
        "driver": "Andres Sebastian Muñoz Rodriguez", "documento": "1073688520",
        "observacion": "Vehículo presenta una llanta pinchada, por lo cual no se permite su ingreso hasta que se solucione la novedad.",
    },
]

SEED_RESPUESTAS = [
    {
        "thread_id": "19d9bd8758430389",
        "message_id": "19d9bfac65d9286b",
        "reply_date": "2026-04-17",
        "responder": "jorozco@clicoh.com",
        "texto": "Buen dia. Gracias por la informacion el TTT395 es de la ciudad de cali, ya escalamos con los inhouse de las operaciones y poder dar pronta solucion a esta novedades.",
        "nivel": "En gestion",
        "tiempo_respuesta_min": 37,
    },
    {
        "thread_id": "19d92529ec2897e3",
        "message_id": "19d925c15f57ecfd",
        "reply_date": "2026-04-15",
        "responder": "jorozco@clicoh.com",
        "texto": "Buena tarde. Recibido el mensaje y se procedera a subsanar la novedad.",
        "nivel": "En gestion",
        "tiempo_respuesta_min": 9,
    },
]

_NOV_FIELDS = [
    "thread_id", "message_id", "email_date", "email_type", "sender",
    "fecha", "mlp", "ciudad", "milla", "operacion", "infractor", "tipo",
    "penalidad", "patente", "driver", "documento", "observacion",
]

_RESP_FIELDS = [
    "thread_id", "message_id", "reply_date", "responder",
    "texto", "nivel", "tiempo_respuesta_min",
]


# ── Funciones públicas ─────────────────────────────────────────────────────

def get_connection():
    """Compatibilidad con sync_imap.py y código externo."""
    return _conn()


def init_db() -> None:
    """Crea tablas y hace seed si la base de datos está vacía."""
    conn = _conn()
    try:
        if _is_pg():
            cur = conn.cursor()
            for stmt in _DDL_PG:
                cur.execute(stmt)
            conn.commit()
            cur.execute("SELECT COUNT(*) FROM novedades")
            count = cur.fetchone()[0]
        else:
            conn.executescript(_DDL_SQLITE)
            conn.commit()
            count = conn.execute("SELECT COUNT(*) FROM novedades").fetchone()[0]

        # Seed desactivado — los datos vienen del sync IMAP real.
        # El seed manual causaba duplicados porque usaba thread_id como message_id
        # mientras el sync IMAP usa el Message-ID real del correo (<CA...@mail.gmail.com>).
        conn.commit()
    finally:
        conn.close()


def insert_novedades(rows: list, conn=None) -> int:
    """Inserta novedades ignorando duplicados por message_id."""
    close_after = conn is None
    if conn is None:
        conn = _conn()

    q = _insert_q("novedades", _NOV_FIELDS)
    inserted = 0

    if _is_pg():
        cur = conn.cursor()
        for row in rows:
            try:
                cur.execute(q, {f: row.get(f, "") for f in _NOV_FIELDS})
                inserted += cur.rowcount
            except Exception as e:
                print(f"[DB] Error insertando {row.get('message_id')}: {e}")
    else:
        for row in rows:
            try:
                conn.execute(q, row)
                inserted += conn.execute("SELECT changes()").fetchone()[0]
            except Exception as e:
                print(f"[DB] Error insertando {row.get('message_id')}: {e}")

    if close_after:
        conn.commit()
        conn.close()
    return inserted


def insert_respuestas(rows: list, conn=None) -> int:
    """Inserta respuestas de ClicOH ignorando duplicados por message_id."""
    close_after = conn is None
    if conn is None:
        conn = _conn()

    q = _insert_q("respuestas", _RESP_FIELDS)
    inserted = 0

    if _is_pg():
        cur = conn.cursor()
        for row in rows:
            try:
                cur.execute(q, {f: row.get(f) for f in _RESP_FIELDS})
                inserted += cur.rowcount
            except Exception as e:
                print(f"[DB] Error insertando respuesta {row.get('message_id')}: {e}")
    else:
        for row in rows:
            try:
                conn.execute(q, row)
                inserted += conn.execute("SELECT changes()").fetchone()[0]
            except Exception as e:
                print(f"[DB] Error insertando respuesta {row.get('message_id')}: {e}")

    if close_after:
        conn.commit()
        conn.close()
    return inserted


def log_sync(emails_processed: int, novedades_added: int) -> None:
    conn = _conn()
    if _is_pg():
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO sync_log (emails_processed, novedades_added) VALUES (%s, %s)",
            (emails_processed, novedades_added),
        )
    else:
        conn.execute(
            "INSERT INTO sync_log (emails_processed, novedades_added) VALUES (?,?)",
            (emails_processed, novedades_added),
        )
    conn.commit()
    conn.close()


def get_last_sync() -> str:
    conn = _conn()
    try:
        if _is_pg():
            cur = conn.cursor()
            cur.execute(
                "SELECT synced_at, novedades_added FROM sync_log ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
            if row:
                ts = str(row[0])[:16].replace("T", " ")
                return f"{ts}  (+{row[1]} novedades)"
        else:
            row = conn.execute(
                "SELECT synced_at, novedades_added FROM sync_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                return f"{row['synced_at'][:16].replace('T', ' ')}  (+{row['novedades_added']} novedades)"
    finally:
        conn.close()
    return "Nunca"


_SELECT_NOVEDADES = """
SELECT
    n.*,
    r.nivel           AS respuesta_nivel,
    r.responder       AS respuesta_responder,
    r.reply_date      AS respuesta_fecha,
    r.texto           AS respuesta_texto,
    r.tiempo_respuesta_min
FROM novedades n
LEFT JOIN (
    SELECT thread_id, nivel, responder, reply_date, texto, tiempo_respuesta_min
    FROM respuestas
    WHERE id IN (
        SELECT MAX(id) FROM respuestas GROUP BY thread_id
    )
) r ON n.thread_id = r.thread_id
ORDER BY n.email_date DESC, n.fecha DESC
"""


def get_all_novedades() -> pd.DataFrame:
    """Retorna todas las novedades con su estado de respuesta de ClicOH."""
    conn = _conn()
    try:
        df = _select_df(conn, _SELECT_NOVEDADES)
    finally:
        conn.close()

    if df.empty:
        return df

    df["fecha"]           = pd.to_datetime(df["fecha"], errors="coerce")
    df["email_date"]      = pd.to_datetime(df["email_date"], errors="coerce")
    df["respuesta_fecha"] = pd.to_datetime(df["respuesta_fecha"], errors="coerce")
    df["penalidad"]       = df["penalidad"].str.strip().str.capitalize()

    def _estado(row):
        if pd.isna(row.get("respuesta_nivel")) or row.get("respuesta_nivel") == "":
            pen = row.get("penalidad", "")
            return "PENDIENTE URGENTE" if pen in ("Critico", "Grave") else "PENDIENTE"
        return row["respuesta_nivel"]

    df["estado_respuesta"] = df.apply(_estado, axis=1)
    return df


def get_pendientes() -> pd.DataFrame:
    """Novedades sin respuesta de ClicOH, ordenadas por urgencia."""
    df = get_all_novedades()
    if df.empty:
        return df
    pendientes = df[df["respuesta_nivel"].isna()].copy()
    orden = {"Critico": 0, "Grave": 1, "Moderada": 2, "Leve": 3}
    pendientes["_orden"] = pendientes["penalidad"].map(orden).fillna(9)
    return pendientes.sort_values(["_orden", "email_date"]).drop(columns=["_orden"])
