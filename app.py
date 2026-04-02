"""
Bot de Reservas — Interfaz principal
Ejecutar con:  python -m streamlit run app.py
"""

import json
import os
import subprocess
from datetime import datetime, date, timedelta

import streamlit as st

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

st.set_page_config(
    page_title="Bot de Reservas",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CONFIG_FILE = "config.json"
ENV_FILE = ".env"

# ──────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .main-title {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0;
        padding-bottom: 0;
    }
    .main-subtitle {
        color: #888;
        font-size: 0.95rem;
        margin-top: 0;
    }

    .status-ok  { color: #00c853; font-weight: 600; }
    .status-warn { color: #ff9800; font-weight: 600; }

    .block-container { padding-top: 1.5rem; }

    .stTextInput label, .stNumberInput label, .stDateInput label,
    .stTimeInput label, .stSelectbox label, .stTextArea label,
    .stRadio label {
        font-size: 0.85rem !important;
        color: #aaa !important;
    }
    /* date chip buttons */
    .chip-btn button { font-size: 0.75rem !important; padding: 2px 8px !important; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"restaurants": []}


def save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_env() -> dict:
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def save_env_values(values: dict):
    current = load_env()
    current.update(values)
    with open(ENV_FILE, "w") as f:
        for k, v in current.items():
            if v:
                f.write(f"{k}={v}\n")


def sync_to_github() -> tuple[bool, str]:
    try:
        subprocess.run(["git", "add", "config.json", "state.json"], check=True, capture_output=True)
        result = subprocess.run(["git", "diff", "--staged", "--quiet"], capture_output=True)
        if result.returncode == 0:
            return True, "Sin cambios nuevos."
        subprocess.run(["git", "commit", "-m", "Update monitors"], check=True, capture_output=True)
        subprocess.run(["git", "push"], check=True, capture_output=True)
        return True, "Subido correctamente."
    except subprocess.CalledProcessError as e:
        return False, e.stderr.decode()[:150] if e.stderr else str(e)[:150]


# ──────────────────────────────────────────────
# SIDEBAR — Config (colapsable)
# ──────────────────────────────────────────────

env = load_env()
tg_ok   = bool(env.get("TELEGRAM_TOKEN")) and bool(env.get("TELEGRAM_CHAT_ID"))
groq_ok = bool(env.get("GROQ_API_KEY"))

with st.sidebar:
    st.markdown("### ⚙️ Configuración")

    tg_label = "📱 Telegram  ✅" if tg_ok else "📱 Telegram  ⚠️ Sin configurar"
    with st.expander(tg_label, expanded=not tg_ok):
        tg_token = st.text_input("Bot Token", value=env.get("TELEGRAM_TOKEN", ""),
                                  type="password", placeholder="Pega el token de @BotFather")
        tg_chat  = st.text_input("Chat ID", value=env.get("TELEGRAM_CHAT_ID", ""),
                                  placeholder="Tu ID numérico de @userinfobot")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Guardar", key="save_tg", use_container_width=True):
                save_env_values({"TELEGRAM_TOKEN": tg_token, "TELEGRAM_CHAT_ID": tg_chat})
                st.success("OK")
                st.rerun()
        with c2:
            if st.button("Probar", key="test_tg", use_container_width=True):
                os.environ["TELEGRAM_TOKEN"]  = tg_token
                os.environ["TELEGRAM_CHAT_ID"] = tg_chat
                from notifier import send_telegram
                if send_telegram("🧪 Test — Bot de reservas OK ✅"):
                    st.success("Enviado ✅")
                else:
                    st.error("Error")

    groq_label = "🤖 Groq IA  ✅" if groq_ok else "🤖 Groq IA  ⚠️ Sin configurar"
    with st.expander(groq_label, expanded=not groq_ok):
        st.caption("Gratis — regístrate en console.groq.com")
        groq_key = st.text_input("API Key", value=env.get("GROQ_API_KEY", ""),
                                  type="password", placeholder="gsk_...")
        if st.button("Guardar", key="save_groq", use_container_width=True):
            save_env_values({"GROQ_API_KEY": groq_key})
            st.success("OK")
            st.rerun()

    st.divider()
    if st.button("☁️ Sincronizar con GitHub", use_container_width=True,
                  help="Sube config.json para que GitHub Actions monitorice 24/7"):
        ok, msg = sync_to_github()
        st.success(msg) if ok else st.error(msg)


# ──────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────

col_title, col_status = st.columns([4, 1])
with col_title:
    st.markdown('<p class="main-title">🍽️ Bot de Reservas</p>', unsafe_allow_html=True)
    st.markdown('<p class="main-subtitle">Monitoriza restaurantes y recibe alertas cuando haya hueco</p>',
                unsafe_allow_html=True)
with col_status:
    st.markdown("")
    parts = []
    parts.append('<span class="status-ok">● Telegram</span>' if tg_ok
                 else '<span class="status-warn">○ Telegram</span>')
    parts.append('<span class="status-ok">● IA</span>' if groq_ok
                 else '<span class="status-warn">○ IA</span>')
    st.markdown("&nbsp;&nbsp;".join(parts), unsafe_allow_html=True)

st.markdown("")

# ──────────────────────────────────────────────
# TABS
# ──────────────────────────────────────────────

tab1, tab2 = st.tabs(["📋 Monitorizar", "✨ Recomendaciones IA"])

# ══════════════════════════════════════════════
# TAB 1 — MONITORIZAR
# ══════════════════════════════════════════════

with tab1:
    config = load_config()
    restaurants = config.get("restaurants", [])

    # ── Tarjetas de restaurantes monitorizados ──
    if restaurants:
        for i, r in enumerate(restaurants):
            is_active = r.get("active", True)
            with st.container(border=True):
                c_info, c_actions = st.columns([6, 2])
                with c_info:
                    icon = "🟢" if is_active else "⏸️"
                    auto_tag = " · 🤖 auto" if r.get("auto_book") else ""
                    zone_tag = f" · 🪑 {r['preferred_zone']}" if r.get("preferred_zone") else ""

                    days_map = {"L": "Lun", "M": "Mar", "X": "Mié",
                                "J": "Jue", "V": "Vie", "S": "Sáb", "D": "Dom"}
                    weekdays = r.get("weekdays", [])
                    days_line = ""
                    if weekdays and len(weekdays) < 7:
                        days_line = " · 📆 " + " ".join(days_map.get(d, d) for d in weekdays)

                    if r.get("specific_dates"):
                        date_line = "📌 " + ", ".join(r["specific_dates"][:4])
                        if len(r["specific_dates"]) > 4:
                            date_line += f" (+{len(r['specific_dates'])-4})"
                    else:
                        date_line = f"📅 {r.get('date_from', '')} → {r.get('date_to', '')}"

                    st.markdown(
                        f"**{icon} {r['name']}**{auto_tag}{zone_tag}  \n"
                        f"👥 {r.get('party_size', 2)} · "
                        f"🕐 {r.get('time_from', '?')} – {r.get('time_to', '?')} · "
                        f"{date_line}{days_line}"
                    )
                with c_actions:
                    ac1, ac2, ac3 = st.columns(3)
                    with ac1:
                        if st.button("⏯", key=f"t_{i}", help="Pausar / Activar"):
                            config["restaurants"][i]["active"] = not is_active
                            save_config(config)
                            st.rerun()
                    with ac2:
                        if st.button("🧪", key=f"test_{i}", help="Probar ahora"):
                            st.session_state[f"testing_{i}"] = True
                    with ac3:
                        if st.button("🗑️", key=f"d_{i}", help="Eliminar"):
                            config["restaurants"].pop(i)
                            save_config(config)
                            st.rerun()

                if st.session_state.get(f"testing_{i}"):
                    with st.spinner(f"Abriendo página de {r['name']} con Chrome... (puede tardar 15-20s)"):
                        try:
                            from scrapers.covermanager import test_url
                            result = test_url(r["url"])
                            if result.get("screenshot"):
                                st.image(result["screenshot"], caption="Captura del navegador")
                            if result["ok"]:
                                st.success(result["message"])
                            else:
                                st.warning(result["message"])
                                if result["details"]:
                                    st.caption(str(result["details"]))
                        except Exception as e:
                            st.error(f"Error: {e}")
                    st.session_state[f"testing_{i}"] = False

    # ══════════════════════════════════════════
    # FORMULARIO — Añadir restaurante
    # Sin st.form() para que los widgets sean reactivos
    # ══════════════════════════════════════════

    st.markdown("### Añadir restaurante")

    # Versión del formulario — incrementar limpia todos los campos
    if "form_ver" not in st.session_state:
        st.session_state.form_ver = 0
    v = st.session_state.form_ver

    with st.container(border=True):

        # ── Fila 1: nombre, URL, zona ──
        col_a, col_b = st.columns(2)

        with col_a:
            new_name = st.text_input(
                "Restaurante", key=f"nn_{v}",
                placeholder="Nombre del restaurante"
            )
            new_url = st.text_input(
                "URL de reservas", key=f"nu_{v}",
                placeholder="https://www.covermanager.com/reservation/module_restaurant/..."
            )
            zone_opts = ["Automático", "Sala", "Interior", "Terraza", "Bar / Barra"]
            new_zone = st.selectbox("Sección preferida", zone_opts, key=f"nz_{v}",
                                    help="El bot elegirá esta sección si el restaurante la ofrece")

        with col_b:
            new_party = st.number_input(
                "Personas", min_value=1, max_value=20, value=2, key=f"np_{v}"
            )
            tc1, tc2 = st.columns(2)
            with tc1:
                new_time_from = st.time_input(
                    "Hora mínima",
                    datetime.strptime("20:00", "%H:%M").time(),
                    key=f"ntf_{v}"
                )
            with tc2:
                new_time_to = st.time_input(
                    "Hora máxima",
                    datetime.strptime("22:30", "%H:%M").time(),
                    key=f"ntt_{v}"
                )

        # ── Fechas ──
        st.caption("¿Cuándo buscas mesa?")
        date_mode = st.radio(
            "Modo de fechas", ["📅 Rango de fechas", "📌 Días exactos"],
            horizontal=True, key=f"dm_{v}", label_visibility="collapsed"
        )

        if date_mode == "📅 Rango de fechas":
            dc1, dc2 = st.columns(2)
            with dc1:
                new_date_from = st.date_input(
                    "Desde", date.today() + timedelta(days=1), key=f"ndf_{v}"
                )
            with dc2:
                new_date_to = st.date_input(
                    "Hasta", date.today() + timedelta(days=30), key=f"ndt_{v}"
                )
            specific_dates_final = []

        else:
            # Modo fechas exactas: el usuario añade una a una
            new_date_from = date.today() + timedelta(days=1)
            new_date_to   = date.today() + timedelta(days=365)

            sdl_key = f"sdl_{v}"
            if sdl_key not in st.session_state:
                st.session_state[sdl_key] = []

            pk1, pk2 = st.columns([3, 1])
            with pk1:
                pick_d = st.date_input(
                    "Selecciona una fecha", date.today() + timedelta(days=1),
                    min_value=date.today(), key=f"pd_{v}"
                )
            with pk2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("➕ Añadir", key=f"adf_{v}", use_container_width=True):
                    ds = pick_d.isoformat()
                    if ds not in st.session_state[sdl_key]:
                        st.session_state[sdl_key].append(ds)
                        st.session_state[sdl_key].sort()

            # Mostrar fechas seleccionadas como chips con ✕
            if st.session_state[sdl_key]:
                st.caption("Fechas añadidas (pulsa para quitar):")
                chip_cols = st.columns(min(len(st.session_state[sdl_key]), 6))
                for ci, ds in enumerate(list(st.session_state[sdl_key])):
                    with chip_cols[ci % len(chip_cols)]:
                        if st.button(f"✕ {ds}", key=f"rm_{v}_{ci}", use_container_width=True):
                            st.session_state[sdl_key].remove(ds)
                            st.rerun()
            else:
                st.caption("Ninguna fecha añadida todavía.")

            specific_dates_final = list(st.session_state.get(sdl_key, []))

        # ── Días de la semana ──
        st.caption("¿Qué días de la semana te interesan?")
        day_cols   = st.columns(7)
        day_labels = ["L", "M", "X", "J", "V", "S", "D"]
        day_names  = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        selected_days = []
        for col, label, full in zip(day_cols, day_labels, day_names):
            with col:
                if st.checkbox(label, value=True, key=f"nd_{v}_{label}", help=full):
                    selected_days.append(label)

        # ── Auto-reserva ──────────────────────────────────────────
        # Fuera de st.form() → el cambio en este checkbox
        # redibuja la página inmediatamente y muestra los campos
        # ─────────────────────────────────────────────────────────
        st.divider()
        auto_book = st.checkbox(
            "🤖 Reservar automáticamente cuando aparezca hueco",
            key=f"nab_{v}"
        )

        if auto_book:
            st.caption("Tus datos para la reserva (guardados solo en tu equipo)")
            gc1, gc2 = st.columns(2)
            with gc1:
                guest_name  = st.text_input("Nombre completo", placeholder="Tu nombre", key=f"ngn_{v}")
                guest_email = st.text_input("Email", placeholder="email@ejemplo.com", key=f"nge_{v}")
            with gc2:
                guest_phone = st.text_input("Teléfono", placeholder="612345678", key=f"ngp_{v}")
                guest_notes = st.text_area("Notas", placeholder="Alergias, celebración...",
                                           height=68, key=f"ngnt_{v}")

        # ── Botón submit ──
        st.markdown("")
        if st.button("✅ Añadir a monitorización", use_container_width=True,
                     type="primary", key=f"sub_{v}"):

            # Validación
            errors = []
            if not new_name:
                errors.append("Falta el nombre")
            if not new_url:
                errors.append("Falta la URL")
            if date_mode == "📅 Rango de fechas" and new_date_from > new_date_to:
                errors.append("La fecha de inicio debe ser anterior a la de fin")
            if date_mode == "📌 Días exactos" and not specific_dates_final:
                errors.append("Añade al menos una fecha")
            if new_time_from >= new_time_to:
                errors.append("La hora mínima debe ser anterior a la máxima")
            if auto_book:
                gn = st.session_state.get(f"ngn_{v}", "")
                ge = st.session_state.get(f"nge_{v}", "")
                gp = st.session_state.get(f"ngp_{v}", "")
                if not (gn and ge and gp):
                    errors.append("Para reserva automática necesitas nombre, email y teléfono")

            if errors:
                st.error("  ·  ".join(errors))
            else:
                zone_map = {
                    "Automático": "", "Sala": "sala", "Interior": "interior",
                    "Terraza": "terraza", "Bar / Barra": "barra",
                }
                entry = {
                    "id":           new_name.lower().replace(" ", "_"),
                    "name":         new_name,
                    "url":          new_url,
                    "party_size":   int(new_party),
                    "time_from":    new_time_from.strftime("%H:%M"),
                    "time_to":      new_time_to.strftime("%H:%M"),
                    "date_from":    new_date_from.isoformat(),
                    "date_to":      new_date_to.isoformat(),
                    "weekdays":     selected_days,
                    "preferred_zone": zone_map.get(new_zone, ""),
                    "active":       True,
                    "auto_book":    auto_book,
                }
                if date_mode == "📌 Días exactos":
                    entry["specific_dates"] = specific_dates_final
                if auto_book:
                    entry["guest"] = {
                        "name":  st.session_state.get(f"ngn_{v}", ""),
                        "email": st.session_state.get(f"nge_{v}", ""),
                        "phone": st.session_state.get(f"ngp_{v}", ""),
                        "notes": st.session_state.get(f"ngnt_{v}", ""),
                    }

                config["restaurants"].append(entry)
                save_config(config)
                st.success(f"✅ {new_name} añadido. Pulsa '☁️ Sincronizar con GitHub' para activar.")
                # Limpiar formulario incrementando la versión
                st.session_state.form_ver += 1
                st.rerun()


# ══════════════════════════════════════════════
# TAB 2 — RECOMENDACIONES IA
# ══════════════════════════════════════════════

with tab2:
    from recommender import SPAIN_CITIES

    st.markdown("### ¿Dónde quieres comer?")
    st.caption("Describe lo que buscas y la IA te recomienda restaurantes reales en España.")

    if not groq_ok:
        st.info(
            "Necesitas una API key de **Groq** (gratis). "
            "Regístrate en [console.groq.com](https://console.groq.com) → API Keys → Create. "
            "Luego pégala en ⚙️ Configuración (sidebar)."
        )

    with st.form("reco_form"):
        description = st.text_area(
            "¿Qué buscas?",
            placeholder=(
                "Ej: Algo tipo Quinqué o Cokima — cocina con personalidad, "
                "producto de calidad, buen ambiente. Para una cena especial."
            ),
            height=90,
        )

        rc1, rc2, rc3, rc4 = st.columns(4)
        with rc1:
            city = st.selectbox("Ciudad", SPAIN_CITIES)
        with rc2:
            n_people = st.number_input("Personas", min_value=1, max_value=30, value=2)
        with rc3:
            budget = st.selectbox(
                "Presupuesto /persona",
                ["Sin límite", "Hasta 30€", "30 – 60€", "60 – 100€", "Más de 100€"],
                index=2,
            )
        with rc4:
            n_results = st.number_input("Resultados", min_value=3, max_value=12, value=6)

        search = st.form_submit_button("✨ Buscar", use_container_width=True, type="primary")

    if search:
        key = load_env().get("GROQ_API_KEY", "")
        if not key:
            st.error("Añade la API key de Groq en ⚙️ Configuración (sidebar izquierdo).")
        elif not description.strip():
            st.error("Escribe qué tipo de restaurante buscas.")
        else:
            with st.spinner(f"Buscando en {city}..."):
                try:
                    from recommender import get_recommendations
                    results = get_recommendations(
                        description=description, city=city, n_people=n_people,
                        budget=budget, limit=int(n_results), api_key=key,
                    )
                except Exception as e:
                    results = []
                    st.error(f"Error: {e}")

            if results:
                for r in results:
                    with st.container(border=True):
                        ri, rl = st.columns([5, 1])
                        with ri:
                            meta = " · ".join(filter(None, [
                                r.get("cuisine"), r.get("price_range"), r.get("neighborhood")]))
                            st.markdown(f"**{r['name']}**")
                            if meta:
                                st.caption(meta)
                            if r.get("description"):
                                st.write(r["description"])
                            if r.get("why_matches"):
                                st.info(f"💡 {r['why_matches']}")
                        with rl:
                            if r.get("maps_url"):
                                st.link_button("📍 Maps", r["maps_url"], use_container_width=True)
                            if r.get("thefork_url"):
                                st.link_button("🍴 TheFork", r["thefork_url"], use_container_width=True)
            elif description:
                st.warning("Sin resultados. Prueba con otra descripción o ciudad.")
