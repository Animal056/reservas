"""
CoverManager scraper — reescrito con los selectores reales del widget.

Selectores confirmados inspeccionando el DOM en vivo:
  Personas  → select#people-box-select
  Fecha     → jQuery UI datepicker inline (.ui-datepicker-calendar td > a)
  Horas     → select#hour-box-select  (opciones con value="HH:MM")
  Zona      → select#extra-box-select (opción "Sala", "Terraza", etc.)
  Botón ok  → input.reservarButton.step1
  Formulario→ input#user_first_name, input#user_last_name,
              input#user_email, input#prescriber_phone
"""

import re
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ── Driver ────────────────────────────────────────────────────────────────────

def _get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
    except Exception:
        service = Service()
    return webdriver.Chrome(service=service, options=options)


def _wait(driver, css, timeout=8):
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css))
        )
    except Exception:
        return None


def _wait_id(driver, elem_id, timeout=8):
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, elem_id))
        )
    except Exception:
        return None


# ── Personas ──────────────────────────────────────────────────────────────────

def _set_people(driver, party_size: int) -> bool:
    """Selecciona el número de personas. Devuelve True si tuvo éxito."""
    # ID real del widget
    for elem_id in ["people-box-select", "people_search"]:
        try:
            elem = driver.find_element(By.ID, elem_id)
            if elem.is_displayed():
                Select(elem).select_by_value(str(party_size))
                time.sleep(1.5)
                return True
        except Exception:
            pass

    # Fallback genérico: cualquier select visible con opciones numéricas
    for sel in driver.find_elements(By.TAG_NAME, "select"):
        try:
            if not sel.is_displayed():
                continue
            opts = [o.get_attribute("value") for o in sel.find_elements(By.TAG_NAME, "option")]
            if str(party_size) in opts and len(opts) <= 25:
                Select(sel).select_by_value(str(party_size))
                time.sleep(1.5)
                return True
        except Exception:
            pass
    return False


# ── Fecha (jQuery UI datepicker) ──────────────────────────────────────────────

_MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

def _set_date(driver, date_str: str) -> bool:
    target = datetime.strptime(date_str, "%Y-%m-%d")

    # Intentar con input[type='date'] (por si alguna versión lo usa)
    for css in ["input[type='date']", "input[name='date']", "input[id*='date']"]:
        try:
            inp = driver.find_element(By.CSS_SELECTOR, css)
            if inp.is_displayed():
                driver.execute_script(
                    "arguments[0].value=arguments[1];"
                    "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                    inp, date_str,
                )
                time.sleep(2)
                return True
        except Exception:
            pass

    # jQuery UI datepicker (el que usa CoverManager)
    for _ in range(14):  # máx 14 meses hacia adelante
        try:
            month_el = driver.find_element(By.CSS_SELECTOR, ".ui-datepicker-month")
            year_el  = driver.find_element(By.CSS_SELECTOR, ".ui-datepicker-year")
            cur_month = _MONTHS_ES.get(month_el.text.strip().lower(), 0)
            cur_year  = int(year_el.text.strip())

            if cur_month == target.month and cur_year == target.year:
                # Buscar el día
                cells = driver.find_elements(
                    By.CSS_SELECTOR,
                    ".ui-datepicker-calendar td:not(.ui-datepicker-unselectable)"
                    ":not(.ui-datepicker-other-month)"
                )
                for cell in cells:
                    try:
                        # Puede ser <a> o texto directo
                        try:
                            link = cell.find_element(By.TAG_NAME, "a")
                            text = link.text.strip()
                            clickable = link
                        except Exception:
                            text = cell.text.strip()
                            clickable = cell

                        if text == str(target.day):
                            driver.execute_script("arguments[0].click();", clickable)
                            time.sleep(2.5)
                            return True
                    except Exception:
                        pass
                break  # Mes correcto pero no encontramos el día

            # Avanzar al siguiente mes
            next_btn = driver.find_element(By.CSS_SELECTOR, ".ui-datepicker-next")
            driver.execute_script("arguments[0].click();", next_btn)
            time.sleep(0.5)

        except Exception:
            break

    return False


# ── Zona ──────────────────────────────────────────────────────────────────────

# Palabras clave cómodas (de mejor a peor)
_COMFORT_ZONES   = ["sala", "salón", "salon", "interior", "comedor", "dining", "mesa", "restaurante", "room"]
# Zonas a evitar si hay alternativa
_AVOID_ZONES     = ["barra", "bar ", "standing", "de pie", "terraza", "exterior"]


def _select_zone_from_elem(zone_elem, preferred_zone: str) -> bool:
    """
    Elige la mejor zona disponible en un <select> dado.
    Prioridad: preferida → sala/interior → cualquier opción no-barra → primera disponible
    Devuelve True si se seleccionó algo.
    """
    try:
        options = zone_elem.find_elements(By.TAG_NAME, "option")
        # Filtrar opciones reales (excluir "Seleccione la zona" y vacías)
        real_opts = [
            o for o in options
            if (o.get_attribute("value") or "").strip() not in ("-1", "", "0")
            and o.text.strip()
        ]
        if not real_opts:
            return True  # No hay zonas configuradas → no bloquea

        # 1. Zona preferida por el usuario
        if preferred_zone:
            for opt in real_opts:
                if preferred_zone.lower() in opt.text.lower():
                    Select(zone_elem).select_by_visible_text(opt.text)
                    time.sleep(0.5)
                    print(f"  [CM] Zona seleccionada (preferida): {opt.text}")
                    return True

        # 2. Lista de comodidad: sala → interior → comedor → ...
        for kw in _COMFORT_ZONES:
            for opt in real_opts:
                if kw in opt.text.lower():
                    Select(zone_elem).select_by_visible_text(opt.text)
                    time.sleep(0.5)
                    print(f"  [CM] Zona seleccionada (cómoda): {opt.text}")
                    return True

        # 3. Cualquier opción que no sea barra/exterior
        for opt in real_opts:
            if not any(av in opt.text.lower() for av in _AVOID_ZONES):
                Select(zone_elem).select_by_visible_text(opt.text)
                time.sleep(0.5)
                print(f"  [CM] Zona seleccionada (disponible): {opt.text}")
                return True

        # 4. Última opción: lo que sea (barra incluida) — reservar es lo primero
        Select(zone_elem).select_by_visible_text(real_opts[0].text)
        time.sleep(0.5)
        print(f"  [CM] Zona seleccionada (único disponible): {real_opts[0].text}")
        return True

    except Exception as e:
        print(f"  [CM] Error seleccionando zona: {e}")
        return False


def _set_zone(driver, preferred_zone: str = "") -> bool:
    """
    Selecciona la zona más cómoda disponible.
    Siempre intenta seleccionar algo aunque preferred_zone esté vacío,
    porque CoverManager puede requerir zona obligatoria.
    """
    # Selector real de CoverManager
    try:
        elem = driver.find_element(By.ID, "extra-box-select")
        if elem.is_displayed():
            return _select_zone_from_elem(elem, preferred_zone)
    except Exception:
        pass

    # Fallback: cualquier select visible con opciones de zona
    for sel in driver.find_elements(By.TAG_NAME, "select"):
        try:
            if not sel.is_displayed():
                continue
            opts_text = [o.text.lower() for o in sel.find_elements(By.TAG_NAME, "option")]
            if any(kw in " ".join(opts_text) for kw in ["sala", "barra", "terraza", "zona"]):
                return _select_zone_from_elem(sel, preferred_zone)
        except Exception:
            pass

    return True  # No se encontró selector de zona → no es necesario


# ── Extraer huecos ────────────────────────────────────────────────────────────

def _extract_slots(driver, time_from: str, time_to: str) -> list[dict]:
    """Lee los huecos disponibles del select#hour-box-select."""
    slots = []
    seen = set()

    # PRIMARY: select#hour-box-select  (selector real de CoverManager)
    for elem_id in ["hour-box-select", "extra_hour", "extra_hour_group_request"]:
        try:
            elem = driver.find_element(By.ID, elem_id)
            options = elem.find_elements(By.TAG_NAME, "option")
            for opt in options:
                val = (opt.get_attribute("value") or "").strip()
                if not val or val in ("-1", "0", "") or ":" not in val:
                    continue
                try:
                    h, m = val.split(":")[:2]
                    t = f"{int(h):02d}:{m[:2]}"
                    if time_from <= t <= time_to and t not in seen:
                        seen.add(t)
                        slots.append({"time": t})
                except Exception:
                    pass
        except Exception:
            pass

    if slots:
        return sorted(slots, key=lambda x: x["time"])

    # FALLBACK: buscar elementos con tiempo en texto (botones, divs, links)
    time_re = re.compile(r"\b(\d{1,2}:\d{2})\b")
    skip_classes = {"disabled", "full", "closed", "unavailable", "past"}

    for css in [
        "[class*='slot']:not([class*='disabled'])",
        "[class*='hour']:not([class*='disabled'])",
        "button:not([disabled])", "a[data-time]", "[data-time]",
    ]:
        try:
            for elem in driver.find_elements(By.CSS_SELECTOR, css)[:80]:
                try:
                    cls = (elem.get_attribute("class") or "").lower()
                    if any(s in cls for s in skip_classes):
                        continue
                    for src in [elem.text, elem.get_attribute("data-time") or ""]:
                        m = time_re.search(src)
                        if m:
                            h, mn = m.group(1).split(":")
                            t = f"{int(h):02d}:{mn}"
                            if time_from <= t <= time_to and t not in seen:
                                seen.add(t)
                                slots.append({"time": t})
                except Exception:
                    pass
        except Exception:
            pass

    return sorted(slots, key=lambda x: x["time"])


# ── API pública ───────────────────────────────────────────────────────────────

def test_url(url: str) -> dict:
    """
    Verifica que una URL de CoverManager funciona y devuelve los huecos de hoy.
    Útil para probar desde la interfaz.
    """
    result = {"ok": False, "message": "", "details": {}, "screenshot": None}
    driver = None
    try:
        driver = _get_driver()
        driver.get(url)
        time.sleep(5)

        # Screenshot para debug
        try:
            result["screenshot"] = driver.get_screenshot_as_png()
        except Exception:
            pass

        title = driver.title or ""
        page_text = driver.page_source.lower()

        is_cm = any(kw in page_text for kw in [
            "covermanager", "module_restaurant", "people-box-select",
            "hour-box-select", "reservar", "personas", "comensales",
        ])

        # Leer selects relevantes
        slots_found = []
        try:
            elem = driver.find_element(By.ID, "hour-box-select")
            for opt in elem.find_elements(By.TAG_NAME, "option"):
                val = (opt.get_attribute("value") or "").strip()
                if val and val != "-1" and ":" in val:
                    slots_found.append(val)
        except Exception:
            pass

        result["details"] = {
            "title": title[:80],
            "is_covermanager": is_cm,
            "slots_today": slots_found[:12],
        }

        if is_cm:
            result["ok"] = True
            if slots_found:
                result["message"] = f"✅ Página OK · {len(slots_found)} huecos hoy: {', '.join(slots_found[:6])}"
            else:
                result["message"] = "✅ Página OK · Sin huecos hoy (el bot monitorizará los próximos días)"
        else:
            result["message"] = "La página cargó pero no parece un widget de CoverManager."

    except Exception as e:
        result["message"] = f"Error: {str(e)[:120]}"
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
    return result


def check_availability(
    restaurant_url: str,
    date: str,
    party_size: int,
    time_from: str = "00:00",
    time_to: str = "23:59",
    preferred_zone: str = "",
) -> list[dict]:
    """
    Comprueba disponibilidad en CoverManager para una fecha y nº de personas.

    Returns:
        [{"time": "HH:MM"}, ...]
    """
    driver = None
    slots = []
    try:
        driver = _get_driver()
        driver.get(restaurant_url)
        time.sleep(5)

        # 1. Personas
        _set_people(driver, party_size)

        # 2. Zona (antes de la fecha para no perder estado)
        if preferred_zone:
            _set_zone(driver, preferred_zone)

        # 3. Fecha en el calendario
        date_ok = _set_date(driver, date)
        if not date_ok:
            print(f"  [CM] Advertencia: no se pudo seleccionar la fecha {date}")
        else:
            time.sleep(1)

        # 4. Extraer huecos
        slots = _extract_slots(driver, time_from, time_to)
        print(f"  [CM] {date} → {len(slots)} hueco(s): {[s['time'] for s in slots]}")

    except Exception as e:
        print(f"  [CM] Error: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return slots


def _click_reservar(driver) -> bool:
    """Hace clic en el botón Reservar (paso 1). Devuelve True si lo encontró."""
    for css in [
        "input.reservarButton.step1",
        "input[class*='reservarButton'][value*='eservar']",
        "input[class*='reservarButton']",
        "button[class*='reservarButton']",
    ]:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, css)
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(2)
                return True
        except Exception:
            pass
    # Fallback por texto
    for btn in driver.find_elements(By.CSS_SELECTOR, "input[type='button'],input[type='submit'],button"):
        try:
            val = (btn.get_attribute("value") or btn.text or "").lower()
            if "reservar" in val and btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(2)
                return True
        except Exception:
            pass
    return False


def _dismiss_alert(driver) -> str:
    """Si hay un alert de JavaScript, lo cierra y devuelve su texto. '' si no hay."""
    try:
        alert = driver.switch_to.alert
        txt = alert.text or ""
        alert.accept()
        time.sleep(0.8)
        return txt
    except Exception:
        return ""


def auto_book(
    restaurant_url: str,
    date: str,
    slot_time: str,
    party_size: int,
    guest_name: str,
    guest_email: str,
    guest_phone: str,
    guest_notes: str = "",
    preferred_zone: str = "",
) -> bool:
    """
    Realiza la reserva automáticamente.

    Orden correcto:
      1. Personas
      2. Fecha (click en calendario)
      3. Zona — SIEMPRE después de la fecha porque el clic en el calendar
         puede resetear la zona. Se intenta: preferida → sala/salón → cualquiera.
      4. Hora
      5. Reservar (si hay alert de zona, selecciona zona y reintenta)
      6. Datos personales
      7. Confirmar
    """
    from selenium.common.exceptions import UnexpectedAlertPresentException
    driver = None
    try:
        driver = _get_driver()
        driver.get(restaurant_url)
        time.sleep(5)

        # ── 1. Personas ──────────────────────────────────────────────────────
        _set_people(driver, party_size)

        # ── 2. Fecha ─────────────────────────────────────────────────────────
        date_ok = _set_date(driver, date)
        if not date_ok:
            print(f"  [CM] Advertencia: no se pudo seleccionar la fecha {date}")

        # ── 3. Zona — DESPUÉS de la fecha (el calendario puede resetearla) ──
        #    Siempre intentamos, aunque preferred_zone esté vacío,
        #    porque en muchos restaurantes la zona es obligatoria.
        _set_zone(driver, preferred_zone)

        # ── 4. Hora ──────────────────────────────────────────────────────────
        hour_selected = False
        try:
            elem = driver.find_element(By.ID, "hour-box-select")
            Select(elem).select_by_value(slot_time)
            hour_selected = True
            time.sleep(1)
        except Exception:
            pass

        if not hour_selected:
            time_re = re.compile(r"\b" + re.escape(slot_time) + r"\b")
            for css in ["button", "[class*='slot']", "[data-time]", "a", "li"]:
                for elem in driver.find_elements(By.CSS_SELECTOR, css)[:60]:
                    try:
                        if time_re.search(elem.text) and elem.is_displayed():
                            driver.execute_script("arguments[0].click();", elem)
                            hour_selected = True
                            time.sleep(1.5)
                            break
                    except Exception:
                        pass
                if hour_selected:
                    break

        if not hour_selected:
            print(f"  [CM] No se pudo seleccionar el hueco {slot_time}")
            return False

        # ── 5. Reservar ───────────────────────────────────────────────────────
        # Intento 1
        clicked = False
        try:
            clicked = _click_reservar(driver)
        except UnexpectedAlertPresentException:
            _dismiss_alert(driver)

        # Si hay alert de zona, seleccionar zona y reintentar
        alert_txt = _dismiss_alert(driver)
        if alert_txt:
            print(f"  [CM] Alert tras Reservar: '{alert_txt}' — seleccionando zona y reintentando")
            _set_zone(driver, preferred_zone)
            time.sleep(0.5)
            try:
                clicked = _click_reservar(driver)
            except UnexpectedAlertPresentException:
                _dismiss_alert(driver)
            # Un segundo alert indicaría otro problema
            alert_txt2 = _dismiss_alert(driver)
            if alert_txt2:
                print(f"  [CM] Segundo alert: '{alert_txt2}' — abortando")
                return False

        if not clicked:
            print("  [CM] No se encontró el botón Reservar")
            return False

        # ── 6. Datos personales ───────────────────────────────────────────────
        parts = guest_name.strip().split(" ", 1)
        first_name = parts[0]
        last_name  = parts[1] if len(parts) > 1 else ""

        _fill_by_id(driver, "user_first_name", first_name)
        _fill_by_id(driver, "user_last_name",  last_name)
        _fill_by_id(driver, "user_email",      guest_email)
        _fill_by_id(driver, "prescriber_phone", guest_phone)

        if guest_notes:
            for field_id in ["comments", "note", "observations", "notas", "comment"]:
                _fill_by_id(driver, field_id, guest_notes, required=False)

        time.sleep(0.5)

        # ── 7. Confirmar (paso final)
        confirmed = False
        for css in [
            "button.reservarButton.step2",
            "button[class*='reservarButton']",
            "input[class*='reservarButton'][class*='step2']",
        ]:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, css)
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    confirmed = True
                    time.sleep(3)
                    break
            except Exception:
                pass

        page_lower = driver.page_source.lower()
        success = confirmed and any(kw in page_lower for kw in [
            "confirmad", "confirmed", "gracias", "thank", "reserva realizada",
            "booking confirmed", "éxito",
        ])
        return success

    except Exception as e:
        print(f"  [CM] Error auto_book general: {e}")
        return False
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

def _fill_by_id(driver, field_id: str, value: str, required: bool = True):
    """Rellena un input por su ID."""
    try:
        inp = driver.find_element(By.ID, field_id)
        if inp.is_displayed():
            inp.clear()
            inp.send_keys(value)
            return True
    except Exception:
        pass
    if not required:
        return False
    # Fallback por name
    try:
        inp = driver.find_element(By.NAME, field_id)
        if inp.is_displayed():
            inp.clear()
            inp.send_keys(value)
            return True
    except Exception:
        pass
    return False
