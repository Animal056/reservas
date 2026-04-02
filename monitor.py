"""
Script principal de monitorización (Motor Universal con auto-apagado y selección inteligente de hora).
"""

import json
import os
import time
from datetime import datetime, date, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

from scrapers.covermanager import check_availability as cm_check, auto_book as cm_book
from notifier import send_telegram, format_availability_message

def load_config() -> dict:
    try:
        with open("config.json") as f:
            return json.load(f)
    except Exception:
        return {"restaurants": []}

def save_config(config: dict):
    """Guarda los cambios de vuelta al archivo para poder desactivar restaurantes."""
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def load_state() -> dict:
    try:
        with open("state.json") as f:
            return json.load(f)
    except Exception:
        return {"notified": {}}

def save_state(state: dict):
    with open("state.json", "w") as f:
        json.dump(state, f, indent=2)

def was_recently_notified(state: dict, restaurant_id: str, check_date: str, slot_time: str, cooldown_hours: float = 1.0) -> bool:
    key = f"{restaurant_id}_{check_date}_{slot_time}"
    last_str = state.get("notified", {}).get(key)
    if not last_str: return False
    last = datetime.fromisoformat(last_str)
    return (datetime.now(timezone.utc) - last).total_seconds() / 3600 < cooldown_hours

def mark_notified(state: dict, restaurant_id: str, check_date: str, slot_time: str):
    state.setdefault("notified", {})[f"{restaurant_id}_{check_date}_{slot_time}"] = datetime.now(timezone.utc).isoformat()

def dates_to_check(date_from: str, date_to: str) -> list[str]:
    start = max(date.fromisoformat(date_from), date.today())
    end = date.fromisoformat(date_to)
    result = []
    current = start
    while current <= end:
        result.append(current.isoformat())
        current += timedelta(days=1)
    return result

def get_best_slot(slots_list: list) -> str:
    """
    Selecciona lógicamente la mejor hora disponible en lugar de la primera.
    Comidas -> Objetivo 14:30. Cenas -> Objetivo 21:30.
    """
    def time_diff(slot_str):
        h, m = map(int, slot_str.split(':'))
        mins = h * 60 + m
        # Separación entre comida y cena: las 17:00 (1020 minutos)
        if mins < 1020:
            target = 14 * 60 + 30  # 14:30
        else:
            target = 21 * 60 + 30  # 21:30
        return abs(mins - target)

    # Ordena la lista basándose en la menor diferencia matemática al objetivo
    best = sorted(slots_list, key=lambda x: time_diff(x["time"]))
    return best[0]["time"]

def get_scraper_engine(url: str):
    if "covermanager.com" in url:
        return cm_check, cm_book
    return None, None

def run_cycle():
    config = load_config()
    state = load_state()
    restaurants = config.get("restaurants", [])

    if not restaurants:
        print("No hay restaurantes configurados o activos en config.json.")
        return

    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando monitorización...")
    state_changed = False
    config_changed = False

    for restaurant in restaurants:
        if not restaurant.get("active", True):
            continue

        name = restaurant["name"]
        url = restaurant["url"]
        preferred_zone = restaurant.get("preferred_zone", "")
        
        check_func, book_func = get_scraper_engine(url)
        if not check_func:
            print(f"  [!] Arquitectura no soportada para: {name} ({url})")
            continue

        rid = restaurant.get("id", name.lower().replace(" ", "_"))
        party_size = restaurant.get("party_size", 2)
        time_from = restaurant.get("time_from", "20:00")
        time_to = restaurant.get("time_to", "23:00")
        date_from = restaurant.get("date_from", date.today().isoformat())
        date_to = restaurant.get("date_to", date_from)

        dates = restaurant.get("specific_dates", dates_to_check(date_from, date_to))

        for check_date in dates:
            print(f"  > Analizando {name} | {check_date} | {party_size}p | {time_from}-{time_to} | Zona: '{preferred_zone}'")

            try:
                if "covermanager.com" in url:
                    slots = check_func(url, check_date, party_size, time_from, time_to, preferred_zone=preferred_zone)
                else:
                    slots = check_func(url, check_date, party_size, time_from, time_to)
            except Exception as e:
                print(f"  Error técnico en el scraper: {e}")
                continue

            if not slots:
                print(f"    - Sin disponibilidad")
                continue

            print(f"    - Huecos detectados: {[s['time'] for s in slots]}")

            new_slots = [s for s in slots if not was_recently_notified(state, rid, check_date, s["time"])]

            if not new_slots:
                print(f"    - Huecos omitidos (ya notificados recientemente).")
                continue

            msg = format_availability_message(name, check_date, new_slots, url)
            if send_telegram(msg):
                print(f"    -> Alerta de Telegram enviada con éxito.")
                for slot in new_slots:
                    mark_notified(state, rid, check_date, slot["time"])
                state_changed = True

            if restaurant.get("auto_book") and new_slots and book_func:
                guest = restaurant.get("guest", {})
                if guest.get("name") and guest.get("email") and guest.get("phone"):
                    
                    target_slot = get_best_slot(new_slots)
                    print(f"    -> Forzando reserva automática para la hora óptima: {target_slot}...")
                    
                    ok = book_func(
                        url, check_date, target_slot, party_size,
                        guest["name"], guest["email"], guest["phone"], 
                        guest.get("notes", ""), preferred_zone
                    )
                    
                    if ok:
                        result_msg = (f"✅ <b>¡RESERVA COMPLETADA en {name}!</b>\n"
                                      f"📅 {check_date} a las {target_slot}\n"
                                      f"👥 {party_size} personas\n\n"
                                      f"⏸️ Monitorización desactivada para este restaurante.")
                        send_telegram(result_msg)
                        
                        print(f"    -> Reserva lograda. Desactivando '{name}' para evitar bucles.")
                        restaurant["active"] = False
                        config_changed = True
                        break  # Rompe el bucle de fechas (ya tiene mesa)
                    else:
                        result_msg = f"⚠️ Fallo en la reserva automática en {name} ({check_date} {target_slot}). Intenta acceder manualmente."
                        send_telegram(result_msg)

    if state_changed:
        save_state(state)
        print("Estado de notificaciones actualizado.")
        
    if config_changed:
        save_config(config)
        print("Configuración actualizada (restaurante desactivado tras éxito).")

def main():
    interval_seconds = 300 
    while True:
        try:
            run_cycle()
            print(f"Ciclo completado. Esperando {interval_seconds // 60} minutos para el siguiente...")
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\nMonitorización detenida manualmente por el usuario.")
            break
        except Exception as e:
            print(f"\nError fatal en el ciclo principal: {e}")
            print("Reintentando en 60 segundos...")
            time.sleep(60)

if __name__ == "__main__":
    main()