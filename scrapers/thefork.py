"""
Scraper de TheFork (thefork.es) para buscar restaurantes alternativos en Madrid.
Usa Playwright porque TheFork es una SPA en React.
"""

import re
from playwright.sync_api import sync_playwright

MADRID_SEARCH_URL = (
    "https://www.thefork.es/restaurantes/madrid-c614891"
    "?sortBy=RATE_GEO&sortOrder=desc&cityName=Madrid"
)

ZONE_KEYWORDS = {
    "Centro": ["centro", "sol", "gran vía", "opera", "mayor"],
    "Salamanca": ["salamanca", "serrano", "goya", "velázquez", "castellana"],
    "Malasaña / Chueca": ["malasaña", "chueca", "fuencarral", "tribunal"],
    "Chamberí": ["chamberí", "alonso cano", "iglesia", "bilbao"],
    "Retiro": ["retiro", "ibiza", "lista", "principe de vergara"],
    "Chamartín": ["chamartín", "tetuán", "concha espina"],
    "Lavapiés": ["lavapiés", "embajadores", "tirso de molina"],
    "La Latina": ["la latina", "cava baja", "rastro"],
}


def search_restaurants(
    cuisine: str = None,
    min_rating: float = 8.0,
    zone: str = None,
    limit: int = 10,
) -> list[dict]:
    """
    Busca restaurantes en TheFork Madrid con los criterios dados.

    Args:
        cuisine: Tipo de cocina (ej. "Japonesa"). None = cualquiera.
        min_rating: Valoración mínima (sobre 10).
        zone: Zona de Madrid. None = toda Madrid.
        limit: Máximo de resultados.

    Returns:
        Lista de restaurantes: [{'name', 'rating', 'cuisine', 'price', 'url', 'address'}, ...]
    """
    results = []

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

        try:
            page.goto(MADRID_SEARCH_URL, wait_until="networkidle", timeout=40000)
            page.wait_for_timeout(3000)

            # Intentar hacer scroll para cargar más resultados
            for _ in range(3):
                page.evaluate("window.scrollBy(0, 800)")
                page.wait_for_timeout(1000)

            # Selectores comunes de tarjetas de restaurante en TheFork
            card_selectors = [
                "article",
                "[data-test*='restaurant']",
                "[class*='restaurantCard']",
                "[class*='restaurant-card']",
                "[class*='RestaurantCard']",
            ]

            cards = []
            for sel in card_selectors:
                found = page.locator(sel).all()
                if found:
                    cards = found
                    break

            rating_re = re.compile(r"(\d+[,\.]\d+)")

            for card in cards[: limit * 4]:
                try:
                    # Nombre
                    name = ""
                    for name_sel in ["h2", "h3", "[class*='name']", "[class*='Name']"]:
                        try:
                            name = card.locator(name_sel).first.inner_text(timeout=400).strip()
                            if name:
                                break
                        except Exception:
                            pass

                    if not name:
                        continue

                    # Valoración
                    rating = 0.0
                    for rating_sel in [
                        "[class*='rating']",
                        "[class*='Rating']",
                        "[class*='score']",
                        "[class*='note']",
                    ]:
                        try:
                            rating_text = card.locator(rating_sel).first.inner_text(timeout=400)
                            m = rating_re.search(rating_text)
                            if m:
                                rating = float(m.group(1).replace(",", "."))
                                break
                        except Exception:
                            pass

                    if rating < min_rating:
                        continue

                    # URL
                    url = ""
                    try:
                        href = card.locator("a").first.get_attribute("href", timeout=400)
                        if href:
                            url = href if href.startswith("http") else "https://www.thefork.es" + href
                    except Exception:
                        pass

                    # Cocina
                    cuisine_text = ""
                    for c_sel in ["[class*='cuisine']", "[class*='Cuisine']", "[class*='tipo']", "[class*='tag']"]:
                        try:
                            cuisine_text = card.locator(c_sel).first.inner_text(timeout=400).strip()
                            if cuisine_text:
                                break
                        except Exception:
                            pass

                    # Precio
                    price_text = ""
                    for p_sel in ["[class*='price']", "[class*='Price']", "[class*='precio']"]:
                        try:
                            price_text = card.locator(p_sel).first.inner_text(timeout=400).strip()
                            if price_text:
                                break
                        except Exception:
                            pass

                    # Dirección
                    address_text = ""
                    for a_sel in ["[class*='address']", "[class*='Address']", "[class*='location']"]:
                        try:
                            address_text = card.locator(a_sel).first.inner_text(timeout=400).strip()
                            if address_text:
                                break
                        except Exception:
                            pass

                    # Filtrar por cocina
                    if cuisine:
                        combined = (name + " " + cuisine_text).lower()
                        if cuisine.lower() not in combined:
                            continue

                    # Filtrar por zona
                    if zone and zone in ZONE_KEYWORDS:
                        zone_kw = ZONE_KEYWORDS[zone]
                        combined = (name + " " + address_text + " " + cuisine_text).lower()
                        if not any(kw in combined for kw in zone_kw):
                            continue

                    results.append(
                        {
                            "name": name,
                            "rating": rating,
                            "cuisine": cuisine_text,
                            "price": price_text,
                            "url": url,
                            "address": address_text,
                        }
                    )

                    if len(results) >= limit:
                        break

                except Exception:
                    pass

        except Exception as e:
            print(f"Error buscando en TheFork: {e}")
        finally:
            browser.close()

    return results
