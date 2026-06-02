"""
pages/1_Agente.py
NOVA — Asistente IA de Novedades MLP · ClicOH
Soporta: Google Gemini (gratis) · Groq (gratis) · Anthropic Claude (pago)
"""

import os
import sys
import json
import streamlit as st
import pandas as pd
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Inyectar DATABASE_URL desde Streamlit secrets (Streamlit Cloud)
try:
    if "DATABASE_URL" in st.secrets and not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = st.secrets["DATABASE_URL"]
except Exception:
    pass

from database import init_db, get_all_novedades, get_pendientes

# ─── Configuración de página ──────────────────────────────────────────────
st.set_page_config(
    page_title="NOVA · Agente IA",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_db()

# ─── CSS ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.nova-header {
    background: linear-gradient(135deg, #1a237e, #283593);
    border-radius: 12px; padding: 18px 24px; margin-bottom: 20px;
}
.nova-title { font-size: 26px; font-weight: 700; color: #fff; margin: 0; }
.nova-sub   { font-size: 13px; color: #90caf9; margin-top: 4px; }
.pend-card  {
    background: #1e1e2e; border-radius: 10px;
    padding: 10px 14px; margin: 5px 0; border-left: 4px solid;
}
.draft-box  {
    background: #0d1b2a; border: 1px solid #1565c0;
    border-radius: 10px; padding: 16px;
    font-family: monospace; font-size: 13px;
    white-space: pre-wrap; color: #e3f2fd;
    margin-bottom: 8px;
}
.provider-badge {
    display: inline-block; padding: 2px 10px; border-radius: 20px;
    font-size: 12px; font-weight: 600; margin-left: 8px;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN: proveedores y API keys
# ═══════════════════════════════════════════════════════════════════════════

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config_agente.txt")

PROVIDERS = {
    "gemini": {
        "label": "Google Gemini 2.0 Flash",
        "badge": "GRATIS",
        "badge_color": "#1b5e20",
        "model": "gemini-2.0-flash",
        "key_prefix": "AIza",
        "key_url": "https://aistudio.google.com/apikey",
        "key_help": "Obtené tu key gratis en aistudio.google.com/apikey (no requiere tarjeta)",
    },
    "groq": {
        "label": "Groq · LLaMA 3.1 8B Instant",
        "badge": "GRATIS",
        "badge_color": "#1b5e20",
        "model": "llama-3.1-8b-instant",
        "key_prefix": "gsk_",
        "key_url": "https://console.groq.com/keys",
        "key_help": "Obtené tu key gratis en console.groq.com (20k tokens/min, límite alto)",
    },
    "openrouter": {
        "label": "OpenRouter · LLaMA 3.1 8B",
        "badge": "GRATIS",
        "badge_color": "#1b5e20",
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "key_prefix": "sk-or-",
        "key_url": "https://openrouter.ai/keys",
        "key_help": "Gratis en openrouter.ai — cualquier email, sin tarjeta. Modelos: LLaMA, Gemma, Mistral y más.",
    },
    "anthropic": {
        "label": "Anthropic Claude Sonnet",
        "badge": "PAGO",
        "badge_color": "#7f1f1f",
        "model": "claude-sonnet-4-6",
        "key_prefix": "sk-ant",
        "key_url": "https://console.anthropic.com",
        "key_help": "Requiere cuenta con crédito en console.anthropic.com",
    },
}


def leer_config() -> dict:
    cfg = {"provider": "gemini"}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip()
    return cfg


def guardar_config(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        for k, v in cfg.items():
            f.write(f"{k}={v}\n")


# ─── Sidebar ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🤖 NOVA · Configuración")
    st.divider()

    cfg = leer_config()

    # Selector de proveedor
    provider_options = list(PROVIDERS.keys())
    provider_labels  = [
        f"{PROVIDERS[p]['label']}  [{PROVIDERS[p]['badge']}]"
        for p in provider_options
    ]
    default_idx = provider_options.index(cfg.get("provider", "gemini"))
    selected_idx = st.selectbox(
        "Proveedor de IA",
        range(len(provider_options)),
        index=default_idx,
        format_func=lambda i: provider_labels[i],
    )
    selected_provider = provider_options[selected_idx]
    pinfo = PROVIDERS[selected_provider]

    if selected_provider != cfg.get("provider"):
        cfg["provider"] = selected_provider
        guardar_config(cfg)

    # API Key del proveedor seleccionado
    key_cfg_name = f"{selected_provider.upper()}_API_KEY"
    current_key  = cfg.get(key_cfg_name, "")

    st.markdown(f"**API Key — {pinfo['label']}**")
    st.caption(pinfo["key_help"])

    if not current_key:
        with st.form(f"form_{selected_provider}"):
            new_key = st.text_input(
                "API Key",
                type="password",
                placeholder=f"{pinfo['key_prefix']}...",
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.form_submit_button("Guardar", use_container_width=True, type="primary"):
                    if new_key:
                        cfg[key_cfg_name] = new_key
                        guardar_config(cfg)
                        st.success("Guardada ✅")
                        st.rerun()
            with c2:
                if st.form_submit_button("Obtener key", use_container_width=True):
                    st.markdown(f"[Abrir →]({pinfo['key_url']})")
    else:
        masked = current_key[:8] + "..." + current_key[-4:]
        st.success(f"Configurada: `{masked}`")
        if st.button("Cambiar key", use_container_width=True):
            cfg.pop(key_cfg_name, None)
            guardar_config(cfg)
            st.rerun()

    st.divider()
    st.markdown("### 📊 Estado actual")
    df_all  = get_all_novedades()
    df_pend = get_pendientes()
    n_urg   = len(df_pend[df_pend["penalidad"].isin(["Critico", "Grave"])])
    st.metric("Novedades totales",      len(df_all))
    st.metric("Pendientes de respuesta", len(df_pend),
              delta=f"{n_urg} urgentes", delta_color="inverse")

    if st.button("🗑️ Limpiar conversación", use_container_width=True):
        st.session_state.messages   = []
        st.session_state.tool_log_all = []
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS (funciones Python que el agente puede llamar)
# ═══════════════════════════════════════════════════════════════════════════

def _fmt_df(df: pd.DataFrame, cols: list) -> list:
    """Convierte DataFrame a lista de dicts con fechas formateadas."""
    available = [c for c in cols if c in df.columns]
    out = df[available].copy()
    for col in out.select_dtypes(include=["datetime64[ns]"]).columns:
        out[col] = out[col].dt.strftime("%Y-%m-%d").fillna("—")
    return out.to_dict("records")


def consultar_novedades(
    solo_pendientes: bool = False,
    penalidad: str = "",
    ciudad: str = "",
    infractor: str = "",
    limit: int = 30,
) -> str:
    """
    Consulta las novedades operacionales de MLP-Logysto.

    Args:
        solo_pendientes: Si True, solo novedades sin respuesta de ClicOH.
        penalidad: Filtrar por nivel (Critico / Grave / Moderada / Leve).
        ciudad: Filtrar por ciudad (Bogota, Medellin, Cali, Pereira, etc.).
        infractor: Filtrar por tipo (Vehiculos / Driver).
        limit: Máximo de registros a retornar (default 30).

    Returns:
        JSON con total y lista de novedades.
    """
    df = get_pendientes() if solo_pendientes else get_all_novedades()
    if penalidad:
        df = df[df["penalidad"].str.lower() == penalidad.lower()]
    if ciudad:
        df = df[df["ciudad"].str.lower() == ciudad.lower()]
    if infractor:
        df = df[df["infractor"].str.lower() == infractor.lower()]
    cols = [
        "thread_id", "fecha", "email_date", "ciudad", "milla", "tipo",
        "penalidad", "patente", "driver", "infractor",
        "estado_respuesta", "respuesta_responder", "respuesta_fecha",
        "tiempo_respuesta_min",
    ]
    records = _fmt_df(df.head(limit), cols)
    return json.dumps({"total": len(df), "registros": records}, ensure_ascii=False)


def get_detalle_novedad(thread_id: str) -> str:
    """
    Devuelve el detalle completo de una novedad específica por su thread_id.

    Args:
        thread_id: ID único del thread del correo de la novedad.

    Returns:
        JSON con todos los campos de la novedad, incluyendo observación y respuesta.
    """
    df = get_all_novedades()
    rows = df[df["thread_id"] == thread_id]
    if rows.empty:
        return json.dumps({"error": f"No se encontró thread_id: {thread_id}"})
    cols = [
        "thread_id", "fecha", "email_date", "email_type",
        "ciudad", "milla", "operacion", "tipo", "penalidad",
        "patente", "driver", "documento", "infractor", "observacion",
        "estado_respuesta", "respuesta_nivel", "respuesta_responder",
        "respuesta_fecha", "respuesta_texto", "tiempo_respuesta_min",
    ]
    return json.dumps({"novedades": _fmt_df(rows, cols)}, ensure_ascii=False)


def resumen_estadisticas() -> str:
    """
    Retorna un resumen estadístico completo de las novedades:
    totales, distribución por penalidad, ciudad, tipo de infractor,
    los 5 tipos de novedad más frecuentes y estado de respuestas ClicOH.

    Returns:
        JSON con las estadísticas.
    """
    df      = get_all_novedades()
    df_pend = get_pendientes()
    return json.dumps({
        "total_novedades":      len(df),
        "pendientes_respuesta": len(df_pend),
        "pendientes_urgentes":  len(df_pend[df_pend["penalidad"].isin(["Critico", "Grave"])]),
        "por_penalidad":        df["penalidad"].value_counts().to_dict(),
        "por_ciudad":           df["ciudad"].value_counts().to_dict(),
        "por_infractor":        df["infractor"].value_counts().to_dict(),
        "tipos_mas_frecuentes": df["tipo"].value_counts().head(5).to_dict(),
        "por_estado_respuesta": df["estado_respuesta"].value_counts().to_dict(),
        "periodo": {
            "desde": str(df["fecha"].min())[:10],
            "hasta": str(df["fecha"].max())[:10],
        },
    }, ensure_ascii=False)


# Mapa nombre → función (para el loop de Anthropic y Groq)
TOOL_FN_MAP = {
    "consultar_novedades": consultar_novedades,
    "get_detalle_novedad":  get_detalle_novedad,
    "resumen_estadisticas": resumen_estadisticas,
}

# Esquema JSON para Anthropic / Groq (OpenAI-compatible)
TOOLS_JSON = [
    {
        "name": "consultar_novedades",
        "description": consultar_novedades.__doc__,
        "input_schema": {
            "type": "object",
            "properties": {
                "solo_pendientes": {"type": "boolean",  "description": "Solo novedades sin respuesta"},
                "penalidad":       {"type": "string",   "description": "Critico / Grave / Moderada / Leve"},
                "ciudad":          {"type": "string",   "description": "Nombre de la ciudad"},
                "infractor":       {"type": "string",   "description": "Vehiculos o Driver"},
                "limit":           {"type": "integer",  "description": "Máximo de resultados"},
            },
        },
    },
    {
        "name": "get_detalle_novedad",
        "description": get_detalle_novedad.__doc__,
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string", "description": "ID del thread"},
            },
            "required": ["thread_id"],
        },
    },
    {
        "name": "resumen_estadisticas",
        "description": resumen_estadisticas.__doc__,
        "input_schema": {"type": "object", "properties": {}},
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Eres NOVA, el asistente de inteligencia operacional de ClicOH para el monitoreo de novedades MLP-Logysto.

CONTEXTO:
- ClicOH es la empresa operadora logística receptora de los reportes
- Los reportes vienen de supervisores de Mercado Libre Colombia (ext_yovilla, ext_santrinc)
- Las novedades son incidentes con vehículos o conductores en Last Mile (LM) y First Mile (FM)
- Severidad: Crítico > Grave > Moderada > Leve
- Destinatarios ClicOH: jorozco@clicoh.com y lpareja@clicoh.com

CUANDO GENERES UN BORRADOR DE CORREO usa EXACTAMENTE este formato (con los delimitadores):

---INICIO DEL BORRADOR---
Asunto: Re: [asunto original]

Hola equipo Logysto,

[Acuse de recibo mencionando fecha, ciudad y tipo de novedad específico]

[Acción concreta según el tipo:
 - Vehículo varado/falla mecánica → coordinación con el operador para reparación o reemplazo de unidad
 - Sin auxiliar programado → revisión inmediata de programación y refuerzo del control de despacho
 - Documentos faltantes / Sin QR → notificación al conductor y seguimiento hasta regularización
 - Daño estructural / puertas → retiro preventivo hasta inspección técnica aprobada
 - Vidrios sin película → instalación coordinada con el operador en plazo de 48 horas
 - Actos inseguros → reporte al supervisor de ruta y capacitación de seguridad vial]

[Compromiso de seguimiento y plazo si aplica]

Quedamos atentos ante cualquier novedad adicional.

Saludos cordiales,
Equipo ClicOH
jorozco@clicoh.com | lpareja@clicoh.com
---FIN DEL BORRADOR---

ESTILO: español formal, conciso, siempre menciona patente/fecha/ciudad para mostrar que leíste el reporte. Sin emojis en los borradores."""


# ═══════════════════════════════════════════════════════════════════════════
# BACKENDS DE IA
# ═══════════════════════════════════════════════════════════════════════════

def _ejecutar_tool(name: str, args: dict) -> str:
    fn = TOOL_FN_MAP.get(name)
    if fn:
        try:
            return fn(**{k: v for k, v in args.items() if v != "" and v is not None})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Herramienta desconocida: {name}"})


# ── Backend Gemini ────────────────────────────────────────────────────────
def _run_gemini(messages: list, api_key: str) -> tuple[str, list]:
    import google.generativeai as genai
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        tools=[consultar_novedades, get_detalle_novedad, resumen_estadisticas],
        system_instruction=SYSTEM_PROMPT,
    )

    # Convertir historial al formato Gemini
    history = []
    for m in messages[:-1]:    # todos menos el último
        role = "user" if m["role"] == "user" else "model"
        history.append({"role": role, "parts": [m["content"]]})

    chat = model.start_chat(
        history=history,
        enable_automatic_function_calling=True,
    )
    response = chat.send_message(messages[-1]["content"])

    # Recolectar tool calls del historial de la sesión
    tool_log = []
    for turn in chat.history:
        for part in turn.parts:
            if fn_call := getattr(part, "function_call", None):
                tool_log.append({"tool": fn_call.name, "input": dict(fn_call.args)})

    return response.text, tool_log


# ── Backend Groq ──────────────────────────────────────────────────────────
# Modelos por orden de preferencia: 8b-instant tiene 20k TPM (vs 6k del 70b)
_GROQ_MODELS = [
    "llama-3.1-8b-instant",       # 20 000 TPM — rápido, cuota alta
    "llama-3.3-70b-versatile",    # 6 000 TPM  — más capaz, fallback si 8b falla
]

def _run_groq(messages: list, api_key: str) -> tuple[str, list]:
    from groq import Groq, RateLimitError as GroqRateLimit

    # Convertir herramientas al formato OpenAI
    tools_openai = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": (t["description"] or "").strip()[:200],
                "parameters": {
                    "type": "object",
                    "properties": t["input_schema"]["properties"],
                    "required": t["input_schema"].get("required", []),
                },
            },
        }
        for t in TOOLS_JSON
    ]

    client   = Groq(api_key=api_key)
    tool_log = []

    for model in _GROQ_MODELS:
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        try:
            for _ in range(6):
                resp = client.chat.completions.create(
                    model=model,
                    messages=msgs,
                    tools=tools_openai,
                    tool_choice="auto",
                    max_tokens=1500,
                )
                choice = resp.choices[0]

                if choice.finish_reason == "tool_calls":
                    tool_calls = choice.message.tool_calls
                    msgs.append({"role": "assistant", "content": None, "tool_calls": [
                        {"id": tc.id, "type": "function",
                         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in tool_calls
                    ]})
                    for tc in tool_calls:
                        args = json.loads(tc.function.arguments or "{}")
                        result = _ejecutar_tool(tc.function.name, args)
                        tool_log.append({"tool": tc.function.name, "input": args})
                        msgs.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                else:
                    return choice.message.content or "", tool_log

            return "No pude completar la respuesta. Intentá con una pregunta más específica.", tool_log

        except GroqRateLimit:
            # Intentar con el siguiente modelo de la lista
            continue
        except Exception:
            raise

    # Todos los modelos agotaron la cuota
    return (
        "⚠️ **Límite de tokens de Groq alcanzado** (la cuota gratuita se resetea cada minuto).\n\n"
        "Opciones:\n"
        "- Esperá **60 segundos** y volvé a intentarlo\n"
        "- Usá **Google Gemini** (1 millón de tokens/día gratis) — configuralo en el sidebar",
        tool_log,
    )


# ── Backend OpenRouter ────────────────────────────────────────────────────
# Modelos gratuitos activos en OpenRouter (actualizados 2026-05)
_OPENROUTER_FREE_MODELS = [
    "deepseek/deepseek-v4-flash:free",      # DeepSeek V4 Flash — rápido, tool calling
    "google/gemma-4-31b-it:free",           # Gemma 4 31B — muy buena calidad
    "google/gemma-4-26b-a4b-it:free",       # Gemma 4 26B — alternativa
    "moonshotai/kimi-k2.6:free",            # Kimi K2.6 — fallback
]

def _run_openrouter(messages: list, api_key: str) -> tuple[str, list]:
    from openai import OpenAI, RateLimitError as OAIRateLimit, NotFoundError as OAINotFound

    tools_openai = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": (t["description"] or "").strip()[:200],
                "parameters": {
                    "type": "object",
                    "properties": t["input_schema"]["properties"],
                    "required": t["input_schema"].get("required", []),
                },
            },
        }
        for t in TOOLS_JSON
    ]

    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    tool_log = []
    tried = []

    for model in _OPENROUTER_FREE_MODELS:
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        tried.append(model.split("/")[-1])
        try:
            for _ in range(6):
                resp = client.chat.completions.create(
                    model=model,
                    messages=msgs,
                    tools=tools_openai,
                    tool_choice="auto",
                    max_tokens=1500,
                )
                choice = resp.choices[0]

                if choice.finish_reason == "tool_calls":
                    tool_calls = choice.message.tool_calls
                    msgs.append({
                        "role": "assistant", "content": None,
                        "tool_calls": [
                            {"id": tc.id, "type": "function",
                             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                            for tc in tool_calls
                        ],
                    })
                    for tc in tool_calls:
                        args = json.loads(tc.function.arguments or "{}")
                        result = _ejecutar_tool(tc.function.name, args)
                        tool_log.append({"tool": tc.function.name, "input": args})
                        msgs.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                else:
                    return choice.message.content or "", tool_log

            return "No pude completar la respuesta. Intentá con una pregunta más específica.", tool_log

        except (OAIRateLimit, OAINotFound):
            continue  # modelo no disponible o cuota agotada → intentar el siguiente
        except Exception as e:
            # Capturar también errores 404 que vengan como APIStatusError
            if "404" in str(e) or "No endpoints" in str(e) or "not found" in str(e).lower():
                continue
            raise

    return (
        f"⚠️ **Ningún modelo gratuito de OpenRouter está disponible ahora mismo.**\n\n"
        f"Modelos intentados: {', '.join(tried)}\n\n"
        "Opciones:\n"
        "- Usá **Groq** desde el selector (tenés la key configurada)\n"
        "- Revisá [openrouter.ai/models](https://openrouter.ai/models) para ver modelos `:free` activos",
        tool_log,
    )


# ── Backend Anthropic ─────────────────────────────────────────────────────
def _run_anthropic(messages: list, api_key: str) -> tuple[str, list]:
    import anthropic
    client   = anthropic.Anthropic(api_key=api_key)
    msgs     = messages.copy()
    tool_log = []

    for _ in range(6):
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=[{
                "name": t["name"],
                "description": (t["description"] or "").strip(),
                "input_schema": t["input_schema"],
            } for t in TOOLS_JSON],
            messages=msgs,
        )
        if resp.stop_reason == "tool_use":
            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    result = _ejecutar_tool(block.name, block.input)
                    tool_log.append({"tool": block.name, "input": block.input})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            msgs.append({"role": "assistant", "content": resp.content})
            msgs.append({"role": "user",      "content": tool_results})
        else:
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            return text, tool_log

    return "No pude completar la respuesta.", tool_log


# ── Dispatcher ────────────────────────────────────────────────────────────
def ejecutar_agente(messages: list) -> tuple[str, list]:
    cfg      = leer_config()
    provider = cfg.get("provider", "gemini")
    key_name = f"{provider.upper()}_API_KEY"
    api_key  = cfg.get(key_name, "")

    if not api_key:
        return (
            f"Configurá la API Key de **{PROVIDERS[provider]['label']}** en el sidebar para activar NOVA.",
            [],
        )
    try:
        if provider == "gemini":
            return _run_gemini(messages, api_key)
        elif provider == "groq":
            return _run_groq(messages, api_key)
        elif provider == "openrouter":
            return _run_openrouter(messages, api_key)
        else:
            return _run_anthropic(messages, api_key)
    except Exception as e:
        err = str(e)
        if "API key" in err or "401" in err or "invalid" in err.lower() or "auth" in err.lower():
            return (
                f"🔑 **API Key inválida** para {PROVIDERS[provider]['label']}.\n"
                f"Verificá o cambiá la key en el sidebar.",
                [],
            )
        if "429" in err or "rate" in err.lower() or "quota" in err.lower():
            return (
                "⚠️ **Límite de solicitudes alcanzado.**\n\n"
                "Esperá 60 segundos y volvé a intentarlo, o cambiá a **Google Gemini** "
                "(1 millón de tokens/día gratis) desde el sidebar.",
                [],
            )
        return f"❌ Error del agente: {err}", []


# ═══════════════════════════════════════════════════════════════════════════
# UI PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

cfg = leer_config()
provider_actual = cfg.get("provider", "gemini")
pinfo_actual    = PROVIDERS[provider_actual]

st.markdown(f"""
<div class="nova-header">
  <div class="nova-title">
    🤖 NOVA — Asistente de Novedades MLP
    <span class="provider-badge" style="background:{pinfo_actual['badge_color']}">
      {pinfo_actual['label']}
    </span>
  </div>
  <div class="nova-sub">
    Consultá datos, analizá patrones y generá respuestas profesionales para correos pendientes
  </div>
</div>
""", unsafe_allow_html=True)


# ── Panel de correos pendientes ───────────────────────────────────────────
df_pend = get_pendientes()
NIVEL_COLOR = {"Critico": "#d32f2f", "Grave": "#f57c00",
               "Moderada": "#f9a825", "Leve": "#388e3c"}

if not df_pend.empty:
    st.markdown("### 📬 Correos pendientes de respuesta")
    st.caption("Clic en **✍️ Sugerir** para que NOVA genere un borrador listo para enviar.")

    threads_vistos = set()
    for _, row in df_pend.iterrows():
        tid = row.get("thread_id", "")
        if tid in threads_vistos:
            continue
        threads_vistos.add(tid)

        pen     = row.get("penalidad", "—")
        color   = NIVEL_COLOR.get(pen, "#555")
        tipo    = row.get("tipo", "—")
        ciudad  = row.get("ciudad", "—")
        fecha   = str(row.get("fecha", "—"))[:10]
        patente = row.get("patente", "—")
        driver  = row.get("driver", "—")

        dias = "—"
        if pd.notna(row.get("email_date")):
            d = (date.today() - row["email_date"].date()).days
            dias = f"{d} día{'s' if d != 1 else ''}"

        col_card, col_btn = st.columns([5, 1])
        with col_card:
            st.markdown(
                f"""<div class="pend-card" style="border-color:{color}">
                <span style="color:{color};font-weight:700;font-size:13px">{pen.upper()}</span>
                <span style="color:#aaa;font-size:12px"> · {fecha} · {ciudad} · {dias} sin respuesta</span><br>
                <span style="color:#eee;font-size:14px">{tipo}</span><br>
                <span style="color:#777;font-size:12px">Patente: {patente} &nbsp;·&nbsp; {driver}</span>
                </div>""",
                unsafe_allow_html=True,
            )
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✍️ Sugerir", key=f"btn_{tid}", use_container_width=True):
                prompt = (
                    f"Generame un borrador de respuesta para el correo de novedad del "
                    f"{fecha} sobre \"{tipo}\" en {ciudad} "
                    f"(patente {patente}, penalidad {pen}). "
                    f"El thread_id es {tid}."
                )
                st.session_state.setdefault("messages", [])
                st.session_state.messages.append({"role": "user", "content": prompt})
                st.session_state["run_agent"] = True
                st.rerun()

    st.divider()
else:
    st.success("✅  No hay correos pendientes de respuesta.")
    st.divider()


# ── Preguntas rápidas ─────────────────────────────────────────────────────
quick_qs = [
    "¿Cuál es el error más persistente?",
    "¿Qué vehículo aparece más veces?",
    "¿Cómo está el nivel de respuesta de ClicOH?",
    "¿Qué ciudad tiene más novedades graves?",
    "Dame un resumen ejecutivo de la operación",
]
cols = st.columns(len(quick_qs))
for i, q in enumerate(quick_qs):
    with cols[i]:
        if st.button(q, key=f"q_{i}", use_container_width=True):
            st.session_state.setdefault("messages", [])
            st.session_state.messages.append({"role": "user", "content": q})
            st.session_state["run_agent"] = True
            st.rerun()

st.divider()


# ── Historial del chat ────────────────────────────────────────────────────
def render_msg(content: str):
    """Renderiza un mensaje: detecta borrador y lo muestra en caja especial."""
    if "---INICIO DEL BORRADOR---" in content:
        partes   = content.split("---INICIO DEL BORRADOR---")
        pre      = partes[0].strip()
        resto    = partes[1].split("---FIN DEL BORRADOR---")
        borrador = resto[0].strip()
        post     = resto[1].strip() if len(resto) > 1 else ""
        if pre:
            st.markdown(pre)
        st.markdown("**📧 Borrador — copialo y envialo directamente:**")
        st.markdown(f'<div class="draft-box">{borrador}</div>', unsafe_allow_html=True)
        st.code(borrador, language=None)
        if post:
            st.markdown(post)
    else:
        st.markdown(content)


if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    if not isinstance(msg.get("content"), str):
        continue
    avatar = "🤖" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        render_msg(msg["content"])

# Input del usuario
user_input = st.chat_input(
    "Preguntame sobre las novedades o pedime que sugiera una respuesta..."
)
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state["run_agent"] = True
    st.rerun()


# ── Ejecutar agente ───────────────────────────────────────────────────────
if st.session_state.get("run_agent"):
    st.session_state["run_agent"] = False

    last = st.session_state.messages[-1]
    with st.chat_message("user", avatar="👤"):
        st.markdown(last["content"])

    # Solo pasar mensajes de texto al agente
    api_msgs = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
        if isinstance(m.get("content"), str)
    ]

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner(f"NOVA ({pinfo_actual['label']}) está analizando..."):
            respuesta, tool_log = ejecutar_agente(api_msgs)

        if tool_log:
            with st.expander(
                f"🔧 {len(tool_log)} consulta{'s' if len(tool_log) > 1 else ''} realizadas",
                expanded=False,
            ):
                for t in tool_log:
                    params = {k: v for k, v in t["input"].items() if v}
                    st.caption(f"**{t['tool']}**({', '.join(f'{k}={v}' for k,v in params.items()) or '—'})")

        render_msg(respuesta)

    st.session_state.messages.append({"role": "assistant", "content": respuesta})
