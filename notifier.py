import requests
import os


def send_telegram(message: str, token: str = None, chat_id: str = None) -> bool:
    token = token or os.getenv("TELEGRAM_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram no configurado (falta TELEGRAM_TOKEN o TELEGRAM_CHAT_ID)")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"Error enviando Telegram: {e}")
        return False


def format_availability_message(
    restaurant_name: str, date: str, slots: list, restaurant_url: str
) -> str:
    slot_lines = "\n".join(f"  • {s['time']}" for s in slots)
    return (
        f"🟢 <b>¡Hueco disponible en {restaurant_name}!</b>\n\n"
        f"📅 Fecha: <b>{date}</b>\n"
        f"🕐 Horas disponibles:\n{slot_lines}\n\n"
        f"👉 <a href='{restaurant_url}'>Reservar ahora</a>"
    )
