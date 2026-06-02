# 🚨 Novedades MLP — Dashboard en vivo

Tablero interactivo para monitorear las novedades GRAVE/CRÍTICO de la operación **MLP - Logysto**.

---

## 🚀 Inicio rápido

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Lanzar el dashboard

```bash
streamlit run dashboard.py
```

El tablero se abre en tu navegador en `http://localhost:8501`.

**Ya viene precargado con todos los históricos** recopilados automáticamente desde Gmail (desde el 10/04/2026 en adelante). No necesitás configurar nada para ver los datos.

---

## 📊 ¿Qué muestra el tablero?

| Sección | Descripción |
|---|---|
| **KPIs** | Total novedades · Crítico+Grave · Tipo más frecuente · Ciudad más afectada · Patente más reportada |
| **Tendencia semanal** | Evolución en el tiempo apilada por penalidad (Crítico/Grave/Moderada/Leve) |
| **Distribución** | Donut con el desglose porcentual por tipo de penalidad |
| **Errores persistentes** | Top 10 tipos de novedad por frecuencia (coloreados por la penalidad más común) |
| **Por ciudad** | Barras apiladas por ciudad |
| **Por infractor** | Donut Driver vs Vehículos |
| **Última novedad** | Tarjeta con detalle del reporte más reciente |
| **Tabla completa** | Filtrable, con descarga CSV |

---

## 🔄 Sincronización automática con Gmail

### Opción A — Desde el dashboard (recomendado)

Una vez configurado el acceso a Gmail, usá el botón **"Sincronizar ahora"** en el sidebar para importar emails nuevos.

### Opción B — Desde la terminal

```bash
python gmail_sync.py
```

### Configurar acceso a Gmail (una sola vez)

```bash
python gmail_sync.py --setup
```

Esto muestra las instrucciones paso a paso para crear las credenciales de Gmail API.

**Resumen:**
1. Ir a [Google Cloud Console](https://console.cloud.google.com/)
2. Crear proyecto → habilitar **Gmail API**
3. Crear credenciales OAuth 2.0 (tipo: escritorio)
4. Descargar el JSON y guardarlo como `credentials/credentials.json`
5. Ejecutar `python gmail_sync.py` → se abre el navegador para autorizar
6. El token queda guardado automáticamente en `credentials/token.json`

### Automatizar la sync (opcional)

**Windows — Programador de tareas:**
```
Acción: python "C:\ruta\al\proyecto\gmail_sync.py"
Disparador: Cada 1 hora
```

---

## 📁 Estructura del proyecto

```
Novedades MELI/
├── dashboard.py          # 🖥️  Tablero Streamlit
├── database.py           # 🗃️  Base de datos SQLite + seed histórico
├── gmail_sync.py         # 📧  Sincronización Gmail API
├── requirements.txt      # 📦  Dependencias Python
├── README.md             # 📖  Este archivo
│
├── data/
│   └── novedades.db      # ← se crea automáticamente al primer arranque
│
└── credentials/          # ← crear esta carpeta para Gmail API
    ├── credentials.json  # ← descargar desde Google Cloud Console
    └── token.json        # ← se genera automáticamente al autenticar
```

---

## 🏗️ Datos en la base de datos

Cada registro de novedad contiene:

| Campo | Descripción |
|---|---|
| `fecha` | Fecha del incidente |
| `ciudad` | Ciudad donde ocurrió |
| `milla` | Last Mile / First Mile |
| `operacion` | SVC / AMT |
| `infractor` | Vehiculos / Driver |
| `tipo` | Descripción del tipo de novedad |
| `penalidad` | Critico / Grave / Moderada / Leve |
| `patente` | Placa del vehículo |
| `driver` | Nombre del conductor |
| `observacion` | Detalle completo |
| `email_type` | GRAVE_CRITICO / SEMANAL |
| `sender` | Remitente del reporte |

---

## ❓ Preguntas frecuentes

**¿Puedo agregar novedades manualmente?**
Sí. Podés conectarte a la base de datos SQLite (`data/novedades.db`) con cualquier herramienta (DB Browser for SQLite, DBeaver) y agregar registros directamente.

**¿Qué pasa si llega un email con múltiples filas en la tabla?**
El sync las procesa como registros individuales, cada uno con su propia fila en la BD.

**¿Cómo comparte el tablero con el equipo?**
Podés deployar el dashboard en [Streamlit Community Cloud](https://streamlit.io/cloud) de forma gratuita, o usar ngrok para exponer el servidor local temporalmente.
