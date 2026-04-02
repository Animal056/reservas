"""
Interfaz web del bot de reservas — ejecutar con: streamlit run app.py
"""

import json
import os
import subprocess
from datetime import datetime, date, timedelta

import streamlit as st

st.set_page_config(
    page_title="Bot de Reservas | Madrid",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

CONFIG_FILE = "config.json"
ENV_FILE = ".env"

# ──────────────────────────────────────────────
# Helpers
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


def save_env(token: str, chat_id: str):
    with open(ENV_FILE, "w") as f:
        f.write(f"TELEGRAM_TOKEN={token}\n")
        f.write(f"TELEGRAM_CHAT_ID={chat_id}\n")


def sync_to_github() -> tuple[bool, str]:
    try:
        subprocess.run(["git", "add", "config.json", "state.json"], check=True, capture_output=True)
        result = subprocess.run(
            ["git", "diff", "--staged", "--quiet"], capture_output=True
        )
        if result.returncode == 0:
            return True, "Sin cambios nuevos que subir."
        subprocess.run(
            ["git", "commit", "-m", "Update restaurant monitors"],
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "push"], check=True, capture_output=True)
        return True, "Configuracion subida a GitHub correctamente."
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode() if e.stderr else str(e)
        return False, f"Error: {err}"


# ──────────────────────────────────────────────
# Sidebar — Telegram + GitHub
# ──────────────────────────────────────────────

with st.sidebar:
    st.title("🍽️ Bot Reservas")
    st.caption("Madrid")
    st.divider()

    st.subheader("📱 Telegram")
    env = load_env()

    token = st.text_input(
        "Bot Token",
        value=env.get("TELEGRAM_TOKEN", ""),
        type="password",
        help="Habla con @BotFather en Telegram → /newbot",
    )
    chat_id = st.text_input(
        "Tu Chat ID",
        value=env.get("TELEGRAM_CHAT_ID", ""),
        help="Habla con @userinfobot para obtener tu ID",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Guardar", use_container_width=True):
            if token and chat_id:
                save_env(token, chat_id)
                st.success("Guardado")
            else:
                st.error("Rellena los dos campos")
    with col_b:
        if st.button("Probar", use_container_width=True):
            if token and chat_id:
                os.environ["TELEGRAM_TOKEN"] = token
                os.environ["TELEGRAM_CHAT_ID"] = chat_id
                from notifier import send_telegram
                ok = send_telegram("🧪 Test del bot — todo correcto ✅")
                st.success("Enviado ✅") if ok else st.error("Error — revisa token y chat ID")
            else:
                st.warning("Guarda primero el token y chat ID")

    st.divider()
    st.subheader("☁️ GitHub Actions")
    st.caption("Sube la configuración para activar el bot en la nube (24/7)")
    if st.button("⬆️ Subir configuración", use_container_width=True):
        ok, msg = sync_to_github()
        st.success(msg) if ok else st.error(msg)


# ──────────────────────────────────────────────
# Main tabs
# ──────────────────────────────────────────────

tab1, tab2 = st.tabs(["🔍 Monitorizar restaurante", "⭐ Recomendaciones"])

# ══════════════════════════════════════════════
# TAB 1 — MONITORIZAR
# ══════════════════════════════════════════════

with tab1:
    config = load_config()
    restaurants = config.get("restaurants", [])

    # Lista de activos
    active = [r for r in restaurants if r.get("active", True)]
    paused = [r for r in restaurants if not r.get("active", True)]

    if restaurants:
        st.subheader(f"Activos ({len(active)})   Pausados ({len(paused)})")

        for i, r in enumerate(restaurants):
            with st.container(border=True):
                col1, col2, col3 = st.columns([5, 1, 1])
                with col1:
                    badge = "🟢" if r.get("active", True) else "⏸️"
                    auto = " · 🤖 reserva auto" if r.get("auto_book") else ""
                    st.markdown(
                        f"**{badge} {r['name']}**{auto}  \n"
                        f"👥 {r.get('party_size', 2)} personas &nbsp;&nbsp; "
                        f"🕐 {r.get('time_from', '20:00')} – {r.get('time_to', '23:00')} &nbsp;&nbsp; "
                        f"📅 {r.get('date_from', '')} → {r.get('date_to', '')}"
                    )
                with col2:
                    label = "Pausar" if r.get("active", True) else "Activar"
                    if st.button(label, key=f"toggle_{i}", use_container_width=True):
                        config["restaurants"][i]["active"] = not r.get("active", True)
                        save_config(config)
                        st.rerun()
                with col3:
                    if st.button("🗑️ Borrar", key=f"del_{i}", use_container_width=True):
                        config["restaurants"].pop(i)
                        save_config(config)
                        st.rerun()
    else:
        st.info("Aún no hay restaurantes. Añade uno abajo.")

    st.divider()

    # Formulario para añadir
    st.subheader("➕ Añadir restaurante")

    with st.form("add_restaurant", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Nombre del restaurante *", placeholder="1911")
            url = st.text_input(
                "URL del widget de reservas *",
                placeholder="https://www.covermanager.com/reservation/module_restaurant/...",
                help=(
                    "Ve a la web del restaurante → abre el formulario de reserva → "
                    "copia la URL que aparece en el iframe o ventana de CoverManager"
                ),
            )
            party_size = st.number_input("Número de personas *", min_value=1, max_value=20, value=2)

        with col2:
            date_from = st.date_input("Buscar desde *", date.today() + timedelta(days=1))
            date_to = st.date_input("Buscar hasta *", date.today() + timedelta(days=30))
            time_from = st.time_input(
                "Hora mínima *", datetime.strptime("20:00", "%H:%M").time()
            )
            time_to = st.time_input(
                "Hora máxima *", datetime.strptime("22:30", "%H:%M").time()
            )

        st.divider()
        auto_book_enabled = st.checkbox(
            "🤖 Reservar automáticamente cuando encuentre un hueco",
            help="El bot rellenará y enviará el formulario de reserva solo",
        )

        guest_name = guest_email = guest_phone = guest_notes = ""
        if auto_book_enabled:
            st.caption("Datos para la reserva automática (se guardan solo en local, no se suben a GitHub)")
            c1, c2 = st.columns(2)
            with c1:
                guest_name = st.text_input("Tu nombre completo")
                guest_email = st.text_input("Email")
            with c2:
                guest_phone = st.text_input("Teléfono")
                guest_notes = st.text_area("Nota especial (alergias, etc.)", height=68)

        submitted = st.form_submit_button(
            "➕ Añadir a monitorización", use_container_width=True, type="primary"
        )

        if submitted:
            errors = []
            if not name:
                errors.append("El nombre es obligatorio")
            if not url:
                errors.append("La URL es obligatoria")
            if date_from > date_to:
                errors.append("La fecha de inicio debe ser anterior a la de fin")
            if time_from >= time_to:
                errors.append("La hora mínima debe ser anterior a la máxima")
            if auto_book_enabled and not (guest_name and guest_email and guest_phone):
                errors.append("Para la reserva automática necesitas nombre, email y teléfono")

            if errors:
                for err in errors:
                    st.error(err)
            else:
                new_entry = {
                    "id": name.lower().replace(" ", "_"),
                    "name": name,
                    "url": url,
                    "party_size": int(party_size),
                    "time_from": time_from.strftime("%H:%M"),
                    "time_to": time_to.strftime("%H:%M"),
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                    "active": True,
                    "auto_book": auto_book_enabled,
                }
                if auto_book_enabled:
                    new_entry["guest"] = {
                        "name": guest_name,
                        "email": guest_email,
                        "phone": guest_phone,
                        "notes": guest_notes,
                    }
                config["restaurants"].append(new_entry)
                save_config(config)
                st.success(
                    f"✅ {name} añadido. "
                    "Pulsa **⬆️ Subir configuración** en el panel izquierdo para que "
                    "GitHub Actions empiece a monitorizarlo."
                )
                st.rerun()

# ══════════════════════════════════════════════
# TAB 2 — RECOMENDACIONES
# ══════════════════════════════════════════════

with tab2:
    st.subheader("Buscar restaurantes alternativos en Madrid")
    st.caption(
        "Si el restaurante que quieres está lleno, encuentra opciones similares "
        "con los criterios que prefieras."
    )

    with st.form("search_form"):
        col1, col2, col3 = st.columns(3)

        with col1:
            cuisine = st.selectbox(
                "Tipo de cocina",
                [
                    "Cualquiera",
                    "Española",
                    "Italiana",
                    "Japonesa",
                    "Mediterránea",
                    "Francesa",
                    "Americana",
                    "Asiática",
                    "Internacional",
                    "Contemporánea / Fusión",
                    "Vasca",
                    "Mariscos / Pescados",
                    "Carnes / Parrilla",
                ],
            )

        with col2:
            min_rating = st.slider("Valoración mínima (sobre 10)", 7.0, 10.0, 9.0, 0.1)
            price_range = st.multiselect(
                "Precio por persona",
                ["€ (menos de 15€)", "€€ (15 – 30€)", "€€€ (30 – 50€)", "€€€€ (más de 50€)"],
                default=["€€ (15 – 30€)", "€€€ (30 – 50€)"],
            )

        with col3:
            zone = st.selectbox(
                "Zona de Madrid",
                [
                    "Toda Madrid",
                    "Centro",
                    "Salamanca",
                    "Malasaña / Chueca",
                    "Chamberí",
                    "Retiro",
                    "Chamartín",
                    "Lavapiés",
                    "La Latina",
                ],
            )
            n_results = st.number_input("Nº de resultados", min_value=3, max_value=20, value=8)

        search_btn = st.form_submit_button(
            "🔍 Buscar alternativas", use_container_width=True, type="primary"
        )

    if search_btn:
        cuisine_filter = None if cuisine == "Cualquiera" else cuisine
        zone_filter = None if zone == "Toda Madrid" else zone

        with st.spinner("Buscando en TheFork... (puede tardar 20-30 segundos)"):
            try:
                from scrapers.thefork import search_restaurants
                results = search_restaurants(
                    cuisine=cuisine_filter,
                    min_rating=min_rating,
                    zone=zone_filter,
                    limit=int(n_results),
                )
            except Exception as e:
                results = []
                st.error(f"Error al buscar: {e}")

        if results:
            st.success(f"Se encontraron {len(results)} restaurantes:")
            for r in results:
                with st.container(border=True):
                    col_info, col_btn = st.columns([5, 1])
                    with col_info:
                        rating_bar = "█" * int(r["rating"]) + "░" * (10 - int(r["rating"]))
                        details = " · ".join(
                            filter(None, [r.get("cuisine"), r.get("price")])
                        )
                        st.markdown(
                            f"**{r['name']}**  \n"
                            f"⭐ {r['rating']:.1f}  `{rating_bar}`  \n"
                            f"{details}"
                        )
                        if r.get("address"):
                            st.caption(f"📍 {r['address']}")
                    with col_btn:
                        if r.get("url"):
                            st.link_button("Ver →", r["url"], use_container_width=True)

                        # Botón para añadir directamente a monitorización
                        if st.button("+ Vigilar", key=f"watch_{r['name']}", use_container_width=True):
                            st.session_state["prefill_name"] = r["name"]
                            st.session_state["prefill_url"] = r.get("url", "")
                            st.success(f"Ve a la pestaña 'Monitorizar' para configurar {r['name']}")
        else:
            st.warning(
                "No se encontraron resultados. "
                "Prueba con criterios menos restrictivos o cambia la zona."
            )
