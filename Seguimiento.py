"""
Seguimiento.py
Tablero en vivo — Novedades operacionales
Ejecutar con: streamlit run Seguimiento.py
"""

import os
import threading
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta, datetime

# ── Inyectar secrets de Streamlit Cloud en variables de entorno ───────────
try:
    for _k in ("DATABASE_URL", "GMAIL_USER", "GMAIL_APP_PASSWORD"):
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = st.secrets[_k]
except Exception:
    pass

from streamlit_autorefresh import st_autorefresh
from database import init_db, get_all_novedades, get_last_sync, get_pendientes

# ── Configuración de página ───────────────────────────────────────────────
st.set_page_config(
    page_title="Novedades · ClicOH",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Paleta ClicOH ────────────────────────────────────────────────────────
BRAND_PURPLE   = "#533FB0"   # Principal — Critico / urgente
BRAND_LAVENDER = "#8C9EF7"   # Secundario — Grave
BRAND_AQUA     = "#00CCA9"   # Acento verde-azul — Moderada / positivo
BRAND_TEAL     = "#3AADA0"   # Derivado aqua — Leve
BRAND_SOFT     = "#9E8FE0"   # Derivado púrpura claro — gráficos adicionales
BRAND_BLACK    = "#222329"   # Fondo oscuro

# Secuencia para gráficos sin categoría de severidad
CHART_SEQ = [BRAND_PURPLE, BRAND_LAVENDER, BRAND_AQUA, BRAND_TEAL, BRAND_SOFT,
             "#7BA7DC", "#5BC4A8", "#B8AEFF", "#4ECDC4", "#6B8FBF"]

PENALIDAD_COLORS = {
    "Critico":  BRAND_PURPLE,
    "Grave":    BRAND_LAVENDER,
    "Moderada": BRAND_AQUA,
    "Leve":     BRAND_TEAL,
}
PENALIDAD_ORDER = ["Critico", "Grave", "Moderada", "Leve"]

# ── CSS personalizado ─────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .kpi-card {
        background: #1e1e2e;
        border-radius: 12px;
        padding: 18px 22px;
        margin: 4px;
        border-left: 5px solid;
    }
    .kpi-label { font-size: 13px; color: #aaa; margin-bottom: 4px; }
    .kpi-value { font-size: 32px; font-weight: 700; color: #fff; line-height: 1.1; }
    .kpi-delta { font-size: 13px; color: #aaa; margin-top: 4px; }
    .section-title {
        font-size: 16px; font-weight: 600;
        color: #ccc; margin: 20px 0 8px 0;
        border-bottom: 1px solid #333; padding-bottom: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Inicializar DB (seed si está vacía) ───────────────────────────────────
init_db()

# ── Sync programado: 10 AM y 3 PM hora Colombia (UTC-5) ──────────────────
_HORAS_SYNC = {10, 15}   # 10 AM y 3 PM
_sync_lock  = threading.Lock()

def _auto_sync():
    """Corre sync solo en las horas programadas; ignora si ya sincronizó en esa ventana."""
    # Convertir hora actual UTC → Colombia (UTC-5)
    hora_col = (datetime.utcnow().hour - 5) % 24
    if hora_col not in _HORAS_SYNC:
        return  # No es hora de sincronizar

    if not _sync_lock.acquire(blocking=False):
        return  # Otro sync ya está corriendo
    try:
        last = get_last_sync()
        if last != "Nunca":
            try:
                ts = datetime.strptime(last.split("  ")[0], "%Y-%m-%d %H:%M")
                # Si ya sincronizamos en la última hora, no volver a hacerlo
                if (datetime.utcnow() - ts).total_seconds() < 3600:
                    return
            except Exception:
                pass
        from sync_imap import sync_emails
        sync_emails()
    except Exception:
        pass
    finally:
        _sync_lock.release()

threading.Thread(target=_auto_sync, daemon=True).start()

# Refrescar la página cada 15 minutos para no perderse las ventanas de sync
st_autorefresh(interval=900_000, key="autorefresh")


# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚨 Novedades\n**Tablero operacional · ClicOH**")
    st.divider()

    # Estado de sincronización (solo lectura — sync automático cada 10 min)
    ultimo = get_last_sync()
    st.caption(f"🔄 Última actualización: {ultimo}")
    st.divider()

    # Filtros globales
    st.markdown("### 🔽 Filtros")

    df_all = get_all_novedades()

    # Rango de fechas — filtrar por email_date (cuándo llegó el correo)
    min_date = df_all["email_date"].min()
    max_date = df_all["email_date"].max()
    if pd.isna(min_date):
        min_date = date.today() - timedelta(days=90)
        max_date = date.today()

    st.caption("📧 Filtra por fecha de recepción del correo")
    date_from = st.date_input(
        "Desde",
        value=min_date.date() if hasattr(min_date, "date") else min_date,
        min_value=min_date.date() if hasattr(min_date, "date") else min_date,
        max_value=max_date.date() if hasattr(max_date, "date") else max_date,
    )
    date_to = st.date_input(
        "Hasta",
        value=max_date.date() if hasattr(max_date, "date") else max_date,
        min_value=min_date.date() if hasattr(min_date, "date") else min_date,
        max_value=max_date.date() if hasattr(max_date, "date") else max_date,
    )

    ciudades_opts = ["Todas"] + sorted(df_all["ciudad"].dropna().unique().tolist())
    ciudad_sel = st.selectbox("Ciudad", ciudades_opts)

    penalidades_opts = ["Todas"] + [p for p in PENALIDAD_ORDER if p in df_all["penalidad"].values]
    penalidad_sel = st.selectbox("Penalidad", penalidades_opts)

    infractores_opts = ["Todos"] + sorted(df_all["infractor"].dropna().unique().tolist())
    infractor_sel = st.selectbox("Infractor", infractores_opts)

    tipo_email_opts = ["Todos", "GRAVE_CRITICO", "SEMANAL"]
    tipo_email_sel = st.selectbox("Tipo de reporte", tipo_email_opts)


# ── Aplicar filtros ───────────────────────────────────────────────────────
df = df_all.copy()
df = df[df["email_date"].notna()]
df = df[df["email_date"].dt.date >= date_from]
df = df[df["email_date"].dt.date <= date_to]
if ciudad_sel != "Todas":
    df = df[df["ciudad"] == ciudad_sel]
if penalidad_sel != "Todas":
    df = df[df["penalidad"] == penalidad_sel]
if infractor_sel != "Todos":
    df = df[df["infractor"] == infractor_sel]
if tipo_email_sel != "Todos":
    df = df[df["email_type"] == tipo_email_sel]


# ── Encabezado con logo ───────────────────────────────────────────────────
_logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo-clicoh.png")
col_titulo, col_logo = st.columns([5, 1])
with col_titulo:
    st.markdown("# 🚨 Novedades")
    st.caption(
        f"Correos recibidos: **{date_from}** → **{date_to}** · "
        f"{len(df)} novedades encontradas"
    )
with col_logo:
    if os.path.exists(_logo_path):
        st.image(_logo_path, width=120)

st.divider()

# ── Variables de pendientes (usadas más abajo) ────────────────────────────
df_pendientes_all   = get_pendientes()
pendientes_urgentes = df_pendientes_all[df_pendientes_all["penalidad"].isin(["Critico", "Grave"])]
pendientes_total    = len(df_pendientes_all)
urgentes_total      = len(pendientes_urgentes)


# ── KPIs ──────────────────────────────────────────────────────────────────
total = len(df)
graves = len(df[df["penalidad"].isin(["Critico", "Grave"])])
pct_graves = f"{graves/total*100:.0f}%" if total > 0 else "—"

tipo_top = (
    df["tipo"].value_counts().idxmax() if total > 0 else "—"
)
ciudad_top = (
    df["ciudad"].value_counts().idxmax() if total > 0 else "—"
)
patente_top = (
    df["patente"].value_counts().idxmax() if total > 0 else "—"
)

col1, col2, col3, col4, col5 = st.columns(5)

def kpi_html(label, value, delta="", color="#4fc3f7"):
    return f"""
    <div class="kpi-card" style="border-color:{color}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-delta">{delta}</div>
    </div>
    """

# Métricas de respuesta
respondidas    = df["respuesta_nivel"].notna().sum()   if "respuesta_nivel" in df.columns else 0
pct_resp       = f"{respondidas/total*100:.0f}%" if total > 0 else "—"
tiempos_validos = df["tiempo_respuesta_min"].dropna() if "tiempo_respuesta_min" in df.columns else pd.Series(dtype=float)
tiempo_prom    = f"{tiempos_validos.mean():.0f} min" if len(tiempos_validos) > 0 else "—"

with col1:
    st.markdown(
        kpi_html("Total Novedades", total, "en el período seleccionado", BRAND_LAVENDER),
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        kpi_html("Crítico + Grave", graves, f"{pct_graves} del total", BRAND_PURPLE),
        unsafe_allow_html=True,
    )
with col3:
    pendientes_kpi = total - respondidas
    color_pend = BRAND_PURPLE if pendientes_kpi > 0 else BRAND_AQUA
    st.markdown(
        kpi_html("Sin respuesta ClicOH", pendientes_kpi, f"{pct_resp} respondidas", color_pend),
        unsafe_allow_html=True,
    )
with col4:
    tipo_top_short = tipo_top[:28] + "…" if len(str(tipo_top)) > 28 else tipo_top
    st.markdown(
        kpi_html("Tipo más frecuente", tipo_top_short, "error más recurrente", BRAND_AQUA),
        unsafe_allow_html=True,
    )
with col5:
    st.markdown(
        kpi_html("Vehículo más reportado", patente_top, "", BRAND_TEAL),
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)


# ── Tendencia histórica ───────────────────────────────────────────────────
st.markdown('<div class="section-title">📈 Tendencia histórica de novedades</div>', unsafe_allow_html=True)

if not df.empty:
    df_trend = df.copy()
    # Agrupar por semana del correo recibido (no del incidente)
    df_trend["semana"] = df_trend["email_date"].dt.to_period("W").apply(lambda p: p.start_time)
    df_weekly = (
        df_trend.groupby(["semana", "penalidad"])
        .size()
        .reset_index(name="count")
    )
    # Ordenar penalidades
    df_weekly["penalidad"] = pd.Categorical(
        df_weekly["penalidad"], categories=PENALIDAD_ORDER, ordered=True
    )
    df_weekly = df_weekly.sort_values(["semana", "penalidad"])

    fig_trend = px.bar(
        df_weekly,
        x="semana",
        y="count",
        color="penalidad",
        color_discrete_map=PENALIDAD_COLORS,
        category_orders={"penalidad": PENALIDAD_ORDER},
        labels={"semana": "Semana", "count": "Novedades", "penalidad": "Penalidad"},
        barmode="stack",
    )
    fig_trend.update_layout(
        height=280,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#ccc",
        xaxis=dict(gridcolor="#333"),
        yaxis=dict(gridcolor="#333"),
    )
    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info("Sin datos para el período seleccionado.")


# ── Distribución + Errores persistentes ──────────────────────────────────
col_pie, col_bar = st.columns([1, 2])

with col_pie:
    st.markdown('<div class="section-title">🥧 Distribución por penalidad</div>', unsafe_allow_html=True)
    if not df.empty:
        pen_counts = (
            df["penalidad"]
            .value_counts()
            .reindex(PENALIDAD_ORDER, fill_value=0)
            .reset_index()
        )
        pen_counts.columns = ["penalidad", "count"]
        pen_counts = pen_counts[pen_counts["count"] > 0]

        fig_pie = go.Figure(
            go.Pie(
                labels=pen_counts["penalidad"],
                values=pen_counts["count"],
                marker_colors=[PENALIDAD_COLORS.get(p, "#888") for p in pen_counts["penalidad"]],
                hole=0.5,
                textinfo="label+percent",
                textfont_size=12,
            )
        )
        fig_pie.update_layout(
            height=280,
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc",
        )
        st.plotly_chart(fig_pie, use_container_width=True)

with col_bar:
    st.markdown('<div class="section-title">🔁 Errores más persistentes (top 10)</div>', unsafe_allow_html=True)
    if not df.empty:
        tipo_counts = (
            df.groupby("tipo")
            .agg(count=("tipo", "count"), penalidad_principal=("penalidad", lambda x: x.mode()[0]))
            .sort_values("count", ascending=True)
            .tail(10)
            .reset_index()
        )
        tipo_counts["color"] = tipo_counts["penalidad_principal"].map(
            lambda p: PENALIDAD_COLORS.get(p, "#888")
        )

        fig_tipos = go.Figure(
            go.Bar(
                y=tipo_counts["tipo"],
                x=tipo_counts["count"],
                orientation="h",
                marker_color=tipo_counts["color"],
                text=tipo_counts["count"],
                textposition="outside",
            )
        )
        fig_tipos.update_layout(
            height=280,
            margin=dict(l=10, r=10, t=10, b=10),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc",
            xaxis=dict(gridcolor="#333", title="Ocurrencias"),
            yaxis=dict(gridcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(fig_tipos, use_container_width=True)


# ── Por ciudad + Por infractor ────────────────────────────────────────────
col_ciudad, col_inf = st.columns(2)

with col_ciudad:
    st.markdown('<div class="section-title">🌆 Novedades por ciudad</div>', unsafe_allow_html=True)
    if not df.empty:
        ciudad_counts = (
            df.groupby(["ciudad", "penalidad"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        fig_ciudad = px.bar(
            ciudad_counts,
            x="ciudad",
            y="count",
            color="penalidad",
            color_discrete_map=PENALIDAD_COLORS,
            category_orders={"penalidad": PENALIDAD_ORDER},
            labels={"ciudad": "Ciudad", "count": "Novedades", "penalidad": "Penalidad"},
        )
        fig_ciudad.update_layout(
            height=280,
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc",
            xaxis=dict(gridcolor="rgba(0,0,0,0)"),
            yaxis=dict(gridcolor="#333"),
        )
        st.plotly_chart(fig_ciudad, use_container_width=True)

with col_inf:
    st.markdown('<div class="section-title">👤 Por tipo de infractor</div>', unsafe_allow_html=True)
    if not df.empty:
        inf_counts = (
            df["infractor"]
            .fillna("Sin especificar")
            .replace("", "Sin especificar")
            .value_counts()
            .reset_index()
        )
        inf_counts.columns = ["infractor", "count"]
        fig_inf = go.Figure(
            go.Pie(
                labels=inf_counts["infractor"],
                values=inf_counts["count"],
                marker_colors=[BRAND_PURPLE, BRAND_AQUA, BRAND_LAVENDER],
                hole=0.4,
                textinfo="label+percent+value",
            )
        )
        fig_inf.update_layout(
            height=280,
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc",
        )
        st.plotly_chart(fig_inf, use_container_width=True)


# ── Última novedad recibida ───────────────────────────────────────────────
st.markdown('<div class="section-title">🔔 Última novedad recibida</div>', unsafe_allow_html=True)

if not df.empty:
    ultima = df.sort_values("email_date", ascending=False).iloc[0]
    pen_color = PENALIDAD_COLORS.get(ultima.get("penalidad", ""), "#888")

    col_a, col_b, col_c = st.columns([1, 2, 2])
    with col_a:
        email_dt_str    = str(ultima.get("email_date", "—"))[:10]
        incidente_str   = str(ultima.get("fecha", "—"))[:10]
        st.markdown(
            f"""
            <div style="background:{pen_color}22;border:1px solid {pen_color};
                        border-radius:10px;padding:16px;text-align:center">
                <div style="font-size:26px;font-weight:700;color:{pen_color}">
                    {ultima.get('penalidad','—').upper()}
                </div>
                <div style="color:#ccc;font-size:12px;margin-top:8px">
                    📧 Correo recibido
                </div>
                <div style="color:#fff;font-size:14px;font-weight:600">
                    {email_dt_str}
                </div>
                <div style="color:#888;font-size:11px;margin-top:6px">
                    📅 Incidente: {incidente_str}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_b:
        st.markdown(f"**🚗 Patente:** `{ultima.get('patente','—')}`")
        st.markdown(f"**👤 Driver:** {ultima.get('driver','—')}")
        st.markdown(f"**🏙️ Ciudad:** {ultima.get('ciudad','—')}  ·  **Milla:** {ultima.get('milla','—')}")
        st.markdown(f"**⚠️ Tipo:** {ultima.get('tipo','—')}")
    with col_c:
        st.markdown(f"**📋 Observación:**")
        st.info(ultima.get("observacion", "—"))


# ── Gráfico de estado de respuestas ──────────────────────────────────────
if not df.empty and "estado_respuesta" in df.columns:
    st.markdown('<div class="section-title">📬 Estado de respuesta ClicOH por novedad</div>', unsafe_allow_html=True)

    col_resp1, col_resp2 = st.columns([1, 2])

    RESP_COLORS = {
        "PENDIENTE URGENTE": BRAND_PURPLE,
        "PENDIENTE":         BRAND_LAVENDER,
        "En gestion":        BRAND_AQUA,
        "Acuse de recibo":   BRAND_SOFT,
        "Resuelto":          BRAND_TEAL,
    }
    RESP_ORDER = ["PENDIENTE URGENTE", "PENDIENTE", "En gestion", "Acuse de recibo", "Resuelto"]
    RESP_LABELS = {
        "PENDIENTE URGENTE": "Pendiente urgente",
        "PENDIENTE":         "Pendiente",
        "En gestion":        "En gestion",
        "Acuse de recibo":   "Acuse de recibo",
        "Resuelto":          "Resuelto",
    }

    with col_resp1:
        resp_counts = (
            df["estado_respuesta"]
            .value_counts()
            .reindex(RESP_ORDER, fill_value=0)
            .reset_index()
        )
        resp_counts.columns = ["estado", "count"]
        resp_counts = resp_counts[resp_counts["count"] > 0]
        resp_counts["label"] = resp_counts["estado"].map(RESP_LABELS).fillna(resp_counts["estado"])

        fig_resp = go.Figure(go.Pie(
            labels=resp_counts["label"],
            values=resp_counts["count"],
            marker_colors=[RESP_COLORS.get(e, "#888") for e in resp_counts["estado"]],
            hole=0.5,
            textinfo="label+value",
            textfont_size=12,
        ))
        fig_resp.update_layout(
            height=280, showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc",
        )
        st.plotly_chart(fig_resp, use_container_width=True)

    with col_resp2:
        # Timeline de respuestas: eje X = fecha novedad, color = estado respuesta
        df_timeline = df[["fecha", "penalidad", "estado_respuesta",
                           "tipo", "ciudad", "patente",
                           "respuesta_responder", "tiempo_respuesta_min"]].copy()
        df_timeline["fecha_str"] = df_timeline["fecha"].dt.strftime("%Y-%m-%d")
        df_timeline["estado_label"] = df_timeline["estado_respuesta"].map(RESP_LABELS).fillna(df_timeline["estado_respuesta"])
        df_timeline["tiempo_str"] = df_timeline["tiempo_respuesta_min"].apply(
            lambda x: f"{int(x)} min" if pd.notna(x) else "—"
        )

        fig_tl = px.scatter(
            df_timeline,
            x="fecha",
            y="penalidad",
            color="estado_label",
            color_discrete_map={v: RESP_COLORS.get(k, "#888") for k, v in RESP_LABELS.items()},
            hover_data={"tipo": True, "ciudad": True, "patente": True,
                        "tiempo_str": True, "fecha_str": True,
                        "fecha": False, "penalidad": False, "estado_label": False},
            labels={"fecha": "Fecha", "penalidad": "Penalidad", "estado_label": "Estado"},
            size_max=14,
        )
        fig_tl.update_traces(marker_size=14)
        fig_tl.update_layout(
            height=280, margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc",
            xaxis=dict(gridcolor="#333"),
            yaxis=dict(gridcolor="#333"),
        )
        st.plotly_chart(fig_tl, use_container_width=True)


# ── Novedades críticas sin respuesta ─────────────────────────────────────
st.divider()
if urgentes_total > 0:
    st.markdown(
        f'<div class="section-title" style="color:#d32f2f">🔴 Novedades CRÍTICAS/GRAVES sin respuesta ClicOH ({urgentes_total})</div>',
        unsafe_allow_html=True,
    )
    NIVEL_COL = {"Critico": BRAND_PURPLE, "Grave": BRAND_LAVENDER, "Moderada": BRAND_AQUA, "Leve": BRAND_TEAL}
    for _, row in pendientes_urgentes.sort_values("email_date").iterrows():
        color = NIVEL_COL.get(row.get("penalidad", ""), "#555")
        dias  = (date.today() - row["email_date"].date()).days if pd.notna(row.get("email_date")) else "?"
        st.markdown(
            f"""<div style="background:#1a1a2e;border-left:5px solid {color};
                border-radius:8px;padding:12px 16px;margin:6px 0;
                display:flex;justify-content:space-between;align-items:center">
              <div>
                <span style="color:{color};font-weight:700;font-size:13px">
                  {row.get('penalidad','').upper()}
                </span>
                <span style="color:#aaa;font-size:12px">
                  &nbsp;·&nbsp;{str(row.get('fecha','—'))[:10]}
                  &nbsp;·&nbsp;{row.get('ciudad','—')}
                </span><br>
                <span style="color:#eee;font-size:14px">{row.get('tipo','—')}</span><br>
                <span style="color:#777;font-size:12px">
                  Patente: <code style="color:#90caf9">{row.get('patente','—')}</code>
                  &nbsp;·&nbsp;{row.get('driver','—')}
                </span>
              </div>
              <div style="text-align:right;color:#ef9a9a;font-size:13px;font-weight:600;min-width:90px">
                {dias} día{'s' if dias != 1 else ''}<br>
                <span style="color:#777;font-size:11px;font-weight:400">sin respuesta</span>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )
elif pendientes_total > 0:
    st.warning(f"📬 **{pendientes_total} novedades pendientes de respuesta** (ninguna crítica/grave).")
else:
    st.success("✅ Todas las novedades tienen respuesta de ClicOH.")

st.divider()

# ── Tabla completa ────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📋 Registro completo de novedades</div>', unsafe_allow_html=True)

# Icono de estado para la tabla
RESP_EMOJI = {
    "PENDIENTE URGENTE": "🔴 Pendiente urgente",
    "PENDIENTE":         "🟡 Pendiente",
    "En gestion":        "🔵 En gestion",
    "Acuse de recibo":   "🟠 Acuse de recibo",
    "Resuelto":          "🟢 Resuelto",
}

if not df.empty:
    cols_base = ["email_date", "fecha", "ciudad", "tipo", "penalidad", "patente", "driver"]
    cols_resp = ["estado_respuesta", "respuesta_responder", "respuesta_fecha",
                 "tiempo_respuesta_min", "respuesta_texto"]
    cols_extra = ["milla", "operacion", "infractor", "documento", "observacion",
                  "email_type", "sender"]

    available = [c for c in cols_base + cols_resp + cols_extra if c in df.columns]
    df_display = df[available].copy()

    if "email_date" in df_display.columns:
        df_display["email_date"] = df_display["email_date"].dt.strftime("%Y-%m-%d")
    df_display["fecha"] = df_display["fecha"].dt.strftime("%Y-%m-%d").fillna("—")
    if "respuesta_fecha" in df_display.columns:
        df_display["respuesta_fecha"] = df_display["respuesta_fecha"].dt.strftime("%Y-%m-%d").fillna("—")
    if "estado_respuesta" in df_display.columns:
        df_display["estado_respuesta"] = df_display["estado_respuesta"].map(RESP_EMOJI).fillna(df_display["estado_respuesta"])
    if "tiempo_respuesta_min" in df_display.columns:
        df_display["tiempo_respuesta_min"] = df_display["tiempo_respuesta_min"].apply(
            lambda x: f"{int(x)} min" if pd.notna(x) else "—"
        )

    def color_penalidad(val):
        colors = {
            "Critico":  f"background-color: {BRAND_PURPLE}; color: #fff",
            "Grave":    f"background-color: {BRAND_LAVENDER}; color: #222",
            "Moderada": f"background-color: {BRAND_AQUA}; color: #222",
            "Leve":     f"background-color: {BRAND_TEAL}; color: #fff",
        }
        return colors.get(val, "")

    styled = df_display.style.map(color_penalidad, subset=["penalidad"])

    col_cfg = {
        "email_date":          st.column_config.TextColumn("📧 Fecha correo", width="small"),
        "fecha":               st.column_config.TextColumn("📅 Fecha incidente", width="small"),
        "ciudad":              st.column_config.TextColumn("Ciudad", width="small"),
        "tipo":                st.column_config.TextColumn("Tipo de novedad", width="large"),
        "penalidad":           st.column_config.TextColumn("Penalidad", width="small"),
        "patente":             st.column_config.TextColumn("Patente", width="small"),
        "driver":              st.column_config.TextColumn("Driver", width="medium"),
        "estado_respuesta":    st.column_config.TextColumn("Estado respuesta", width="medium"),
        "respuesta_responder": st.column_config.TextColumn("Respondio", width="medium"),
        "respuesta_fecha":     st.column_config.TextColumn("Fecha respuesta", width="small"),
        "tiempo_respuesta_min":st.column_config.TextColumn("Tiempo resp.", width="small"),
        "respuesta_texto":     st.column_config.TextColumn("Texto respuesta", width="large"),
        "milla":               st.column_config.TextColumn("Milla", width="small"),
        "operacion":           st.column_config.TextColumn("Op.", width="small"),
        "infractor":           st.column_config.TextColumn("Infractor", width="small"),
        "documento":           st.column_config.TextColumn("Doc.", width="small"),
        "observacion":         st.column_config.TextColumn("Observacion", width="large"),
        "email_type":          st.column_config.TextColumn("Reporte", width="small"),
        "sender":              st.column_config.TextColumn("Enviado por", width="small"),
    }

    st.dataframe(styled, use_container_width=True, height=420, column_config=col_cfg)

    csv = df_display.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="Descargar CSV",
        data=csv,
        file_name=f"novedades_mlp_{date.today()}.csv",
        mime="text/csv",
    )
else:
    st.info("No hay novedades para el período y filtros seleccionados.")


# ── Footer ────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Novedades operacionales — ClicOH · "
    "Datos actualizados desde Gmail · "
    f"Generado el {date.today()}"
)
