"""
Script principal de monitorización — ejecutado por GitHub Actions cada 5 minutos.
"""

import json
import os
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

from scrapers.covermanager import check_availability, auto_book
from notifier import send_telegram, format_availability_message


def load_config() -> dict:
    try:
        with open("config.json") as f:
            return json.load(f)
    except Exception:
        return {"restaurants": []}


def load_state() -> dict:
    try:
        with open("state.json") as f:
            return json.load(f)
    except Exception:
        return {"notified": {}}


def save_state(state: dict):
    with open("state.json", "w") as f:
        json.dump(state, f, indent=2)


def was_recently_notified(
    state: dict,
    restaurant_id: str,
    check_date: str,
    slot_time: str,
    cooldown_hours: float = 1.0,
) -> bool:
    key = f"{restaurant_id}_{check_date}_{slot_time}"
    last_str = state.get("notified", {}).get(key)
    if not last_str:
        return False
    last = datetime.fromisoformat(last_str)
    return (datetime.utcnow() - last).total_seconds() / 3600 < cooldown_hours


def mark_notified(state: dict, restaurant_id: str, check_date: str, slot_time: str):
    state.setdefault("notified", {})[
        f"{restaurant_id}_{check_date}_{slot_time}"
    ] = datetime.utcnow().isoformat()


def dates_to_check(date_from: str, date_to: str) -> list[str]:
    start = max(date.fromisoformat(date_from), date.today())
    end = date.fromisoformat(date_to)
    result = []
    current = start
    while current <= end:
        result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def main():
    config = load_config()
    state = load_state()
    restaurants = config.get("restaurants", [])

    if not restaurants:
        print("No hay restaurantes en config.json.")
        return

    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] "
        f"Comprobando {len(restaurants)} restaurante(s)..."
    )

    state_changed = False

    for restaurant in restaurants:
        if not restaurant.get("active", True):
            continue

        name = restaurant["name"]
        url = restaurant["url"]
        rid = restaurant.get("id", name.lower().replace(" ", "_"))
        party_size = restaurant.get("party_size", 2)
        time_from = restaurant.get("time_from", "20:00")
        time_to = restaurant.get("time_to", "23:00")
        date_from = restaurant.get("date_from", date.today().isoformat())
        date_to = restaurant.get("date_to", date_from)

        for check_date in dates_to_check(date_from, date_to):
            print(
                f"  {name} | {check_date} | {party_size}p | {time_from}-{time_to}"
            )

            try:
                slots = check_availability(url, check_date, party_size, time_from, time_to)
            except Exception as e:
                print(f"  Error: {e}")
                continue

            if not slots:
                print(f"  Sin disponibilidad")
                continue

            print(f"  Huecos: {[s['time'] for s in slots]}")

            new_slots = [
                s for s in slots
                if not was_recently_notified(state, rid, check_date, s["time"])
            ]

            if not new_slots:
                print(f"  Ya notificados previamente")
                continue

            msg = format_availability_message(name, check_date, new_slots, url)
            if send_telegram(msg):
                print(f"  Notificacion enviada por Telegram")
                for slot in new_slots:
                    mark_notified(state, rid, check_date, slot["time"])
                state_changed = True

            # Reserva automática (solo si está habilitada y hay hueco preferido)
            if restaurant.get("auto_book") and new_slots:
                guest = restaurant.get("guest", {})
                if guest.get("name") and guest.get("email") and guest.get("phone"):
                    target_slot = new_slots[0]["time"]
                    print(f"  Intentando reserva automática para {target_slot}...")
                    ok = auto_book(
                        url,
                        check_date,
                        target_slot,
                        party_size,
                        guest["name"],
                        guest["email"],
                        guest["phone"],
                        guest.get("notes", ""),
                    )
                    result_msg = (
                        f"✅ <b>Reserva confirmada en {name}</b>\n"
                        f"📅 {check_date} a las {target_slot}\n"
                        f"👥 {party_size} personas"
                        if ok
                        else f"⚠️ No se pudo hacer la reserva automática en {name} ({check_date} {target_slot}). Entra manualmente."
                    )
                    send_telegram(result_msg)

    if state_changed:
        save_state(state)

    print("Comprobacion completada.")


if __name__ == "__main__":
    main()
