import requests
import os


def _post(token: str, method: str, **kwargs) -> dict:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/{method}",
            json=kwargs, timeout=10
        )
        return r.json()
    except Exception as e:
        print(f"Telegram {method} error: {e}")
        return {}


def send_telegram(message: str, token: str = None, chat_id: str = None) -> bool:
    token = token or os.getenv("TELEGRAM_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    result = _post(token, "sendMessage",
                   chat_id=chat_id, text=message,
                   parse_mode="HTML", disable_web_page_preview=True)
    return result.get("ok", False)


def send_availability_notification(
    restaurant_name: str,
    check_date: str,
    slots: list,
    restaurant_url: str,
    restaurant_id: str,
    token: str = None,
    chat_id: str = None,
) -> bool:
    """
    Envía notificación con botones inline para confirmar reserva desde Telegram.
    El usuario puede pulsar el botón y el bot intentará reservar en la siguiente ejecución.
    """
    token = token or os.getenv("TELEGRAM_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False

    # Formatear fecha legible
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(check_date)
        days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        fecha_str = f"{days[dt.weekday()]} {dt.day} de {dt.strftime('%B')}"
    except Exception:
        fecha_str = check_date

    slot_list = "  ".join(f"<code>{s['time']}</code>" for s in slots)
    message = (
        f"🟢 <b>{restaurant_name}</b> — hay hueco\n\n"
        f"📅 {fecha_str}\n"
        f"🕐 {slot_list}\n\n"
        f"Pulsa para reservar o <a href='{restaurant_url}'>abre la web</a>"
    )

    # Botones: uno por hora (máx 6), luego Ver web + Ignorar
    keyboard = []
    for slot in slots[:6]:
        cb = f"book|{restaurant_id}|{check_date}|{slot['time']}"
        keyboard.append([{"text": f"✅ Reservar {slot['time']}", "callback_data": cb}])
    keyboard.append([
        {"text": "🌐 Ver reservas", "url": restaurant_url},
        {"text": "❌ Ignorar", "callback_data": "ignore"},
    ])

    result = _post(token, "sendMessage",
                   chat_id=chat_id,
                   text=message,
                   parse_mode="HTML",
                   disable_web_page_preview=True,
                   reply_markup={"inline_keyboard": keyboard})
    return result.get("ok", False)


def get_pending_callbacks(token: str = None) -> list[dict]:
    """
    Devuelve los callbacks pendientes (botones pulsados por el usuario).
    Cada item: {update_id, callback_id, data}
    """
    token = token or os.getenv("TELEGRAM_TOKEN")
    if not token:
        return []
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"timeout": 0, "allowed_updates": ["callback_query"]},
            timeout=10
        )
        callbacks = []
        for update in r.json().get("result", []):
            cq = update.get("callback_query")
            if cq:
                callbacks.append({
                    "update_id": update["update_id"],
                    "callback_id": cq["id"],
                    "chat_id": cq.get("message", {}).get("chat", {}).get("id"),
                    "message_id": cq.get("message", {}).get("message_id"),
                    "data": cq.get("data", ""),
                })
        return callbacks
    except Exception as e:
        print(f"Error getting callbacks: {e}")
        return []


def answer_callback(callback_id: str, text: str, token: str = None):
    """Muestra un toast al usuario cuando pulsa un botón."""
    token = token or os.getenv("TELEGRAM_TOKEN")
    if not token:
        return
    _post(token, "answerCallbackQuery",
          callback_query_id=callback_id, text=text, show_alert=False)


def clear_updates(max_update_id: int, token: str = None):
    """Marca los updates como procesados."""
    token = token or os.getenv("TELEGRAM_TOKEN")
    if not token:
        return
    try:
        requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": max_update_id + 1, "timeout": 0},
            timeout=10
        )
    except Exception:
        pass


def edit_message(chat_id, message_id: int, text: str, token: str = None):
    """Edita un mensaje (para quitar los botones tras actuar)."""
    token = token or os.getenv("TELEGRAM_TOKEN")
    if not token:
        return
    _post(token, "editMessageText",
          chat_id=chat_id, message_id=message_id,
          text=text, parse_mode="HTML",
          reply_markup={"inline_keyboard": []})


def format_availability_message(restaurant_name, date, slots, url):
    slot_list = "\n".join(f"  • {s['time']}" for s in slots)
    return (
        f"🟢 <b>¡Hueco en {restaurant_name}!</b>\n\n"
        f"📅 {date}\n🕐 {slot_list}\n\n"
        f"👉 <a href='{url}'>Reservar</a>"
    )
