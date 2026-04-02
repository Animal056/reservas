"""
CoverManager availability scraper.

Usa Playwright para cargar el widget de reservas, interceptar las llamadas
a la API y extraer los huecos disponibles.
"""

import re
import json
from datetime import datetime
from playwright.sync_api import sync_playwright


def check_availability(
    restaurant_url: str,
    date: str,
    party_size: int,
    time_from: str = "00:00",
    time_to: str = "23:59",
) -> list[dict]:
    """
    Comprueba disponibilidad en una página de CoverManager.

    Args:
        restaurant_url: URL del widget de reservas
        date: Fecha en formato YYYY-MM-DD
        party_size: Número de personas
        time_from: Hora mínima deseada (HH:MM)
        time_to: Hora máxima deseada (HH:MM)

    Returns:
        Lista de huecos: [{'time': 'HH:MM'}, ...]
    """
    available_slots = []
    captured_json = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            locale="es-ES",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # Capturar todas las respuestas JSON
        def on_response(response):
            try:
                if "json" in response.headers.get("content-type", "") and response.status == 200:
                    data = response.json()
                    captured_json.append({"url": response.url, "data": data})
            except Exception:
                pass

        page.on("response", on_response)

        try:
            page.goto(restaurant_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            # Intentar seleccionar número de personas
            for sel in [
                'select[name="people"]',
                "#people",
                'select[id*="person"]',
                'select[id*="guest"]',
                'select[id*="pax"]',
                'select[id*="persona"]',
                'select[id*="comensal"]',
            ]:
                try:
                    elem = page.locator(sel).first
                    if elem.count() > 0 and elem.is_visible(timeout=1000):
                        elem.select_option(str(party_size))
                        page.wait_for_timeout(1000)
                        break
                except Exception:
                    pass

            # Intentar rellenar campo de fecha
            for sel in [
                'input[type="date"]',
                'input[name="date"]',
                'input[id*="date"]',
                'input[id*="fecha"]',
            ]:
                try:
                    elem = page.locator(sel).first
                    if elem.count() > 0 and elem.is_visible(timeout=1000):
                        elem.fill(date)
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(2000)
                        break
                except Exception:
                    pass

            # Esperar a que carguen los huecos
            page.wait_for_timeout(4000)

            # Leer huecos disponibles del DOM
            time_re = re.compile(r"\b(\d{1,2}:\d{2})\b")
            seen = set()

            slot_selectors = [
                "button:not([disabled])",
                "[class*='slot']:not([class*='disabled']):not([class*='full'])",
                "[class*='time']:not([class*='disabled'])",
                "[class*='hour']:not([class*='disabled'])",
                "li[data-time]",
                "[data-time]",
                "a[href*='time']",
            ]

            for sel in slot_selectors:
                try:
                    elements = page.locator(sel).all()
                    for elem in elements[:60]:
                        try:
                            text = elem.inner_text(timeout=500).strip()
                            match = time_re.search(text)
                            if match:
                                t = match.group(1)
                                if time_from <= t <= time_to and t not in seen:
                                    seen.add(t)
                                    available_slots.append({"time": t})
                        except Exception:
                            pass
                    if available_slots:
                        break
                except Exception:
                    pass

        except Exception as e:
            print(f"  Error Playwright: {e}")
        finally:
            browser.close()

    # Fallback: extraer horas de las respuestas API capturadas
    if not available_slots:
        available_slots = _parse_api_responses(captured_json, time_from, time_to)

    return sorted(available_slots, key=lambda x: x["time"])


def _parse_api_responses(responses: list, time_from: str, time_to: str) -> list:
    """Extrae horas disponibles de las respuestas JSON capturadas."""
    time_re = re.compile(r"\b(\d{1,2}:\d{2})\b")
    seen = set()
    slots = []

    for resp in responses:
        raw = json.dumps(resp["data"])
        for t in time_re.findall(raw):
            if time_from <= t <= time_to and t not in seen:
                seen.add(t)
                slots.append({"time": t})

    return sorted(slots, key=lambda x: x["time"])


def auto_book(
    restaurant_url: str,
    date: str,
    slot_time: str,
    party_size: int,
    guest_name: str,
    guest_email: str,
    guest_phone: str,
    guest_notes: str = "",
) -> bool:
    """
    Intenta hacer la reserva automáticamente en CoverManager.
    Devuelve True si parece haber funcionado.
    """
    success = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(locale="es-ES")
        page = context.new_page()

        try:
            page.goto(restaurant_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            # Seleccionar personas
            for sel in ['select[name="people"]', "#people", 'select[id*="person"]']:
                try:
                    e = page.locator(sel).first
                    if e.count() > 0 and e.is_visible(timeout=1000):
                        e.select_option(str(party_size))
                        break
                except Exception:
                    pass

            # Rellenar fecha
            for sel in ['input[type="date"]', 'input[name="date"]']:
                try:
                    e = page.locator(sel).first
                    if e.count() > 0 and e.is_visible(timeout=1000):
                        e.fill(date)
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(2000)
                        break
                except Exception:
                    pass

            page.wait_for_timeout(3000)

            # Hacer clic en el hueco de la hora objetivo
            time_re = re.compile(r"\b" + re.escape(slot_time) + r"\b")
            clicked = False
            for sel in ["button", "li[data-time]", "[data-time]", "[class*='slot']"]:
                try:
                    elements = page.locator(sel).all()
                    for elem in elements[:60]:
                        try:
                            text = elem.inner_text(timeout=300).strip()
                            if time_re.search(text):
                                elem.click()
                                clicked = True
                                page.wait_for_timeout(2000)
                                break
                        except Exception:
                            pass
                    if clicked:
                        break
                except Exception:
                    pass

            if not clicked:
                print("  No se encontró el hueco en el DOM")
                return False

            # Rellenar formulario de datos personales
            field_map = {
                'input[name="name"], input[id*="name"], input[placeholder*="nombre"]': guest_name,
                'input[name="email"], input[type="email"]': guest_email,
                'input[name="phone"], input[type="tel"], input[id*="phone"]': guest_phone,
                'textarea[name="notes"], textarea[id*="notes"], textarea[id*="comment"]': guest_notes,
            }

            for selector_group, value in field_map.items():
                for sel in selector_group.split(", "):
                    try:
                        e = page.locator(sel).first
                        if e.count() > 0 and e.is_visible(timeout=1000):
                            e.fill(value)
                            break
                    except Exception:
                        pass

            # Hacer clic en el botón de confirmar
            for sel in [
                'button[type="submit"]',
                "button:has-text('Confirmar')",
                "button:has-text('Reservar')",
                "button:has-text('Finalizar')",
            ]:
                try:
                    e = page.locator(sel).first
                    if e.count() > 0 and e.is_visible(timeout=1000):
                        e.click()
                        page.wait_for_timeout(3000)
                        success = True
                        break
                except Exception:
                    pass

        except Exception as e:
            print(f"  Error en reserva automática: {e}")
        finally:
            browser.close()

    return success
