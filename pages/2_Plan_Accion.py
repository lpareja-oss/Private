"""
pages/2_Plan_Accion.py
Genera automáticamente un Plan de Acción basado en las métricas de Novedades.
Listo para presentaciones de mejora continua.
"""

import os
import sys
import streamlit as st
import pandas as pd
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Secrets → entorno ─────────────────────────────────────────────────────
try:
    for _k in ("DATABASE_URL", "GROQ_API_KEY", "GEMINI_API_KEY",
               "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = st.secrets[_k]
except Exception:
    pass

from database import get_all_novedades, get_pendientes, init_db

st.set_page_config(
    page_title="Plan de Acción · ClicOH",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_db()

# ── Paleta ClicOH ─────────────────────────────────────────────────────────
BRAND_PURPLE   = "#533FB0"
BRAND_LAVENDER = "#8C9EF7"
BRAND_AQUA     = "#00CCA9"
BRAND_TEAL     = "#3AADA0"

# ── CSS ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.plan-card {
    border-radius: 12px;
    padding: 18px 22px;
    margin: 6px 0 14px 0;
    border-left: 5px solid;
    background: #1e1e2e;
    line-height: 1.7;
    color: #ddd;
    font-size: 14px;
}
.section-title {
    font-size: 16px; font-weight: 600;
    color: #ccc; margin: 22px 0 8px 0;
    border-bottom: 1px solid #333; padding-bottom: 6px;
}
.ctx-item { font-size: 13px; color: #bbb; padding: 2px 0; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📋 Plan de Acción")
    st.divider()
    st.markdown("### 📅 Período de análisis")

    PERIODOS = {
        "Últimos 30 días":   30,
        "Últimos 60 días":   60,
        "Últimos 90 días":   90,
        "Todo el historial": None,
    }
    periodo_sel = st.selectbox("Período", list(PERIODOS.keys()), index=0)
    dias = PERIODOS[periodo_sel]
    st.divider()
    st.caption("El plan se genera con IA en base a las métricas reales del período seleccionado.")


# ── Cargar y filtrar datos ────────────────────────────────────────────────
df_all  = get_all_novedades()
df_pend = get_pendientes()

if dias and not df_all.empty and "email_date" in df_all.columns:
    corte = date.today() - timedelta(days=dias)
    df = df_all[df_all["email_date"].dt.date >= corte].copy()
else:
    df = df_all.copy()

# ── Encabezado ────────────────────────────────────────────────────────────
_logo = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo-clicoh.png")
col_t, col_l = st.columns([5, 1])
with col_t:
    st.markdown("# 📋 Plan de Acción")
    st.caption(f"Generado a partir de métricas reales · {periodo_sel} · {len(df)} novedades")
with col_l:
    if os.path.exists(_logo):
        st.image(_logo, width=120)
st.divider()

if df.empty:
    st.info("No hay datos para el período. Sincronizá los correos desde la pestaña Agente.")
    st.stop()

# ── Calcular métricas ─────────────────────────────────────────────────────
total      = len(df)
graves     = len(df[df["penalidad"].isin(["Critico", "Grave"])])
pct_graves = graves / total * 100 if total > 0 else 0

respondidas = int(df["respuesta_nivel"].notna().sum()) if "respuesta_nivel" in df.columns else 0
pct_resp    = respondidas / total * 100 if total > 0 else 0

pend_urgentes = len(
    df_pend[df_pend["estado_respuesta"] == "PENDIENTE URGENTE"]
) if "estado_respuesta" in df_pend.columns else 0

tiempos  = df["tiempo_respuesta_min"].dropna() if "tiempo_respuesta_min" in df.columns else pd.Series(dtype=float)
t_prom   = f"{tiempos.mean():.0f} min" if len(tiempos) > 0 else "N/D"
t_median = f"{tiempos.median():.0f} min" if len(tiempos) > 0 else "N/D"

tipos_top    = df["tipo"].value_counts().head(6)
ciudades_top = df["ciudad"].value_counts()
infractores  = df["infractor"].fillna("Sin especificar").value_counts()
patentes_top = df["patente"].value_counts().head(5)
penalidades  = df["penalidad"].value_counts()

# ── Mini KPIs ─────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
with c1: st.metric("Novedades totales",    total)
with c2: st.metric("Crítico + Grave",      f"{graves} ({pct_graves:.0f}%)")
with c3: st.metric("Respondidas",          f"{respondidas} ({pct_resp:.0f}%)")
with c4: st.metric("Pendientes urgentes",  pend_urgentes)
with c5: st.metric("Tiempo resp. prom.",   t_prom)

st.divider()

# ── Resumen de datos del período ──────────────────────────────────────────
st.markdown('<div class="section-title">📊 Datos del período que alimentan el plan</div>', unsafe_allow_html=True)
col_a, col_b, col_c = st.columns(3)

with col_a:
    st.markdown("**🔝 Incidentes más frecuentes**")
    for tipo, cnt in tipos_top.items():
        etiqueta = (tipo[:42] + "…") if len(tipo) > 42 else tipo
        st.markdown(f'<div class="ctx-item">• {etiqueta} — <b>{cnt}</b></div>', unsafe_allow_html=True)

with col_b:
    st.markdown("**🏙️ Por ciudad**")
    for ciudad, cnt in ciudades_top.items():
        pct = cnt / total * 100
        st.markdown(f'<div class="ctx-item">• {ciudad}: <b>{cnt}</b> ({pct:.0f}%)</div>', unsafe_allow_html=True)
    st.markdown("**👤 Por tipo de infractor**")
    for inf, cnt in infractores.items():
        pct = cnt / total * 100
        st.markdown(f'<div class="ctx-item">• {inf}: <b>{cnt}</b> ({pct:.0f}%)</div>', unsafe_allow_html=True)

with col_c:
    st.markdown("**🚗 Vehículos más reportados**")
    for pat, cnt in patentes_top.items():
        st.markdown(f'<div class="ctx-item">• <code>{pat}</code>: <b>{cnt}</b> novedades</div>', unsafe_allow_html=True)
    st.markdown("**⚠️ Severidad**")
    for pen, cnt in penalidades.items():
        st.markdown(f'<div class="ctx-item">• {pen}: <b>{cnt}</b></div>', unsafe_allow_html=True)

st.divider()


# ── Prompt y llamada a IA ─────────────────────────────────────────────────
def _construir_contexto() -> str:
    lineas = [
        f"PERÍODO ANALIZADO: {periodo_sel}",
        f"Total novedades: {total}",
        f"Crítico/Grave: {graves} ({pct_graves:.0f}%)",
        f"Respondidas por ClicOH: {respondidas}/{total} ({pct_resp:.0f}%)",
        f"Pendientes urgentes (>24h sin respuesta): {pend_urgentes}",
        f"Tiempo promedio de respuesta ClicOH: {t_prom} | Mediana: {t_median}",
        "",
        "TOP TIPOS DE INCIDENTE:",
    ]
    for tipo, cnt in tipos_top.items():
        lineas.append(f"  {cnt}x  {tipo}  ({cnt/total*100:.0f}%)")

    lineas += ["", "DISTRIBUCIÓN POR CIUDAD:"]
    for ciudad, cnt in ciudades_top.items():
        lineas.append(f"  {ciudad}: {cnt} ({cnt/total*100:.0f}%)")

    lineas += ["", "TIPO DE INFRACTOR:"]
    for inf, cnt in infractores.items():
        lineas.append(f"  {inf}: {cnt} ({cnt/total*100:.0f}%)")

    lineas += ["", "TOP VEHÍCULOS CON MÁS INCIDENTES:"]
    for pat, cnt in patentes_top.items():
        lineas.append(f"  {pat}: {cnt} novedades")

    lineas += ["", "DISTRIBUCIÓN POR SEVERIDAD:"]
    for pen, cnt in penalidades.items():
        lineas.append(f"  {pen}: {cnt}")

    return "\n".join(lineas)


PLAN_PROMPT = """Eres un consultor senior de mejora continua en logística de última milla.
Con base en los siguientes datos operacionales reales, genera un Plan de Acción para una \
presentación interna de mejora continua. Debe ser conciso, específico y profesional.

{contexto}

Responde EXACTAMENTE con esta estructura (respeta los delimitadores):

---RESUMEN---
[2-3 oraciones sobre la situación: qué patrón predomina, cuál es el riesgo principal \
y si la respuesta de ClicOH está siendo oportuna]
---FIN RESUMEN---

---INMEDIATAS---
[3 acciones correctivas para esta semana. Por cada una:]
ACCION: [qué hacer, muy específico — menciona el tipo de incidente o patente si aplica]
RESPONSABLE: [quién dentro de ClicOH o el operador]
META: [cómo se mide el éxito]

---FIN INMEDIATAS---

---PREVENTIVAS---
[3 acciones preventivas para los próximos 30 días. Mismo formato ACCION/RESPONSABLE/META.]
---FIN PREVENTIVAS---

---KPIS---
[4 indicadores para monitorear semana a semana. Formato:]
KPI: [nombre del indicador] | OBJETIVO: [valor concreto]

---FIN KPIS---

Sé muy específico con los datos reales del reporte. Sin introducción ni cierre adicional."""


def _llamar_ia(contexto: str) -> str:
    """Intenta generar el plan con el primer proveedor disponible."""
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config_agente.txt")

    def _get_key(env_name: str) -> str:
        key = os.environ.get(env_name, "")
        if not key and os.path.exists(cfg_path):
            try:
                with open(cfg_path) as f:
                    for line in f:
                        if "=" in line and env_name in line:
                            key = line.split("=", 1)[1].strip()
                            break
            except Exception:
                pass
        return key

    prompt = PLAN_PROMPT.format(contexto=contexto)
    msgs   = [{"role": "user", "content": prompt}]

    # ── Groq ──────────────────────────────────────────────────────────────
    groq_key = _get_key("GROQ_API_KEY")
    if groq_key:
        try:
            from groq import Groq, RateLimitError
            client = Groq(api_key=groq_key)
            for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
                try:
                    r = client.chat.completions.create(
                        model=model, messages=msgs, max_tokens=1400, temperature=0.3)
                    return r.choices[0].message.content or ""
                except RateLimitError:
                    continue
        except Exception as e:
            st.warning(f"Groq no disponible: {e}. Intentando siguiente proveedor…")

    # ── OpenRouter ────────────────────────────────────────────────────────
    or_key = _get_key("OPENROUTER_API_KEY")
    if or_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=or_key, base_url="https://openrouter.ai/api/v1")
            for model in ["deepseek/deepseek-v4-flash:free", "google/gemma-4-31b-it:free"]:
                try:
                    r = client.chat.completions.create(
                        model=model, messages=msgs, max_tokens=1400, temperature=0.3)
                    return r.choices[0].message.content or ""
                except Exception as e:
                    if "404" in str(e) or "No endpoints" in str(e):
                        continue
                    raise
        except Exception as e:
            st.warning(f"OpenRouter no disponible: {e}. Intentando siguiente proveedor…")

    # ── Gemini ────────────────────────────────────────────────────────────
    gem_key = _get_key("GEMINI_API_KEY")
    if gem_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gem_key)
            m = genai.GenerativeModel("gemini-2.0-flash")
            r = m.generate_content(prompt)
            return r.text or ""
        except Exception as e:
            st.warning(f"Gemini no disponible: {e}. Intentando siguiente proveedor…")

    # ── Anthropic ─────────────────────────────────────────────────────────
    ant_key = _get_key("ANTHROPIC_API_KEY")
    if ant_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ant_key)
            r = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=1400,
                messages=msgs)
            return r.content[0].text or ""
        except Exception as e:
            st.warning(f"Anthropic no disponible: {e}.")

    return ""


# ── Parsear y renderizar el plan ──────────────────────────────────────────
def _seccion(texto: str, inicio: str, fin: str) -> str:
    try:
        return texto.split(inicio)[1].split(fin)[0].strip()
    except Exception:
        return ""


def _render_plan(texto: str):
    resumen     = _seccion(texto, "---RESUMEN---",     "---FIN RESUMEN---")
    inmediatas  = _seccion(texto, "---INMEDIATAS---",  "---FIN INMEDIATAS---")
    preventivas = _seccion(texto, "---PREVENTIVAS---", "---FIN PREVENTIVAS---")
    kpis        = _seccion(texto, "---KPIS---",        "---FIN KPIS---")

    if not any([resumen, inmediatas, preventivas, kpis]):
        # La IA no respetó el formato; mostrar texto limpio
        st.markdown(texto)
        return

    if resumen:
        st.markdown(
            f'<div class="plan-card" style="border-color:{BRAND_LAVENDER}">'
            f'<b style="color:{BRAND_LAVENDER}">📊 Situación actual</b><br><br>'
            f'{resumen.replace(chr(10), "<br>")}</div>',
            unsafe_allow_html=True,
        )

    col_i, col_p = st.columns(2)
    with col_i:
        if inmediatas:
            # Resaltar campos clave
            html = inmediatas
            for tag, color in [("ACCION:", f"color:{BRAND_PURPLE};font-weight:700"),
                                ("RESPONSABLE:", "color:#aaa;font-style:italic"),
                                ("META:", f"color:{BRAND_AQUA}")]:
                html = html.replace(tag, f'<span style="{color}">{tag}</span>')
            st.markdown(
                f'<div class="plan-card" style="border-color:{BRAND_PURPLE}">'
                f'<b style="color:{BRAND_PURPLE}">🚨 Acciones inmediatas — esta semana</b><br><br>'
                f'{html.replace(chr(10), "<br>")}</div>',
                unsafe_allow_html=True,
            )
    with col_p:
        if preventivas:
            html = preventivas
            for tag, color in [("ACCION:", f"color:{BRAND_AQUA};font-weight:700"),
                                ("RESPONSABLE:", "color:#aaa;font-style:italic"),
                                ("META:", f"color:{BRAND_TEAL}")]:
                html = html.replace(tag, f'<span style="{color}">{tag}</span>')
            st.markdown(
                f'<div class="plan-card" style="border-color:{BRAND_AQUA}">'
                f'<b style="color:{BRAND_AQUA}">🛡️ Acciones preventivas — 30 días</b><br><br>'
                f'{html.replace(chr(10), "<br>")}</div>',
                unsafe_allow_html=True,
            )

    if kpis:
        html = kpis.replace("KPI:", f'<span style="color:{BRAND_TEAL};font-weight:700">📈</span> <b>')
        html = html.replace("| OBJETIVO:", "</b> &nbsp;·&nbsp; Objetivo:")
        st.markdown(
            f'<div class="plan-card" style="border-color:{BRAND_TEAL}">'
            f'<b style="color:{BRAND_TEAL}">📈 Indicadores de seguimiento semanal</b><br><br>'
            f'{html.replace(chr(10), "<br>")}</div>',
            unsafe_allow_html=True,
        )

    # Descarga como texto plano
    plan_md = (
        f"PLAN DE ACCIÓN — {periodo_sel} — Generado el {date.today()}\n"
        f"{'='*60}\n\n"
        f"SITUACIÓN ACTUAL\n{resumen}\n\n"
        f"ACCIONES INMEDIATAS (esta semana)\n{inmediatas}\n\n"
        f"ACCIONES PREVENTIVAS (30 días)\n{preventivas}\n\n"
        f"INDICADORES DE SEGUIMIENTO\n{kpis}\n"
    )
    st.download_button(
        "⬇️ Descargar plan (.txt)",
        data=plan_md,
        file_name=f"plan_accion_{date.today()}.txt",
        mime="text/plain",
        use_container_width=False,
    )


# ── Botón principal ───────────────────────────────────────────────────────
col_btn, col_hint = st.columns([1, 3])
with col_btn:
    generar = st.button(
        "🤖 Generar Plan de Acción",
        type="primary",
        use_container_width=True,
    )
with col_hint:
    st.markdown("")
    st.caption(
        "La IA analiza los patrones reales y genera acciones concretas. "
        "Tarda ~10 segundos. Podés regenerar cuantas veces quieras."
    )

if generar:
    with st.spinner("Analizando métricas y generando plan de acción…"):
        ctx   = _construir_contexto()
        texto = _llamar_ia(ctx)
    if texto:
        st.session_state["plan_texto"]   = texto
        st.session_state["plan_periodo"] = periodo_sel
        st.rerun()
    else:
        st.error(
            "No se encontró ninguna API Key configurada. "
            "Configurá al menos una en la pestaña **Agente**."
        )

# ── Mostrar plan guardado ─────────────────────────────────────────────────
if st.session_state.get("plan_texto"):
    guardado_en = st.session_state.get("plan_periodo", "")
    if guardado_en and guardado_en != periodo_sel:
        st.info(
            f"ℹ️ El plan fue generado para **{guardado_en}**. "
            "Hacé clic en **Generar** para actualizarlo al período actual."
        )
    st.markdown('<div class="section-title">📋 Plan de Acción generado</div>', unsafe_allow_html=True)
    _render_plan(st.session_state["plan_texto"])


# ── Footer ────────────────────────────────────────────────────────────────
st.divider()
st.caption(f"Plan de Acción — ClicOH · Novedades MLP · Generado el {date.today()}")
