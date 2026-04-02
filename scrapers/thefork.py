"""
Scraper de TheFork para buscar restaurantes alternativos en Madrid.
Usa requests + BeautifulSoup con headers de navegador real.
"""

import json
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.thefork.es/",
}

# Palabras clave por zona para filtrar resultados
ZONE_KEYWORDS = {
    "Centro": ["centro", "sol", "gran via", "opera", "mayor", "chueca"],
    "Salamanca": ["salamanca", "serrano", "goya", "velazquez", "castellana"],
    "Malasaña / Chueca": ["malasana", "chueca", "fuencarral", "tribunal"],
    "Chamberí": ["chamberi", "alonso cano", "iglesia", "bilbao"],
    "Retiro": ["retiro", "ibiza", "lista", "principe de vergara"],
    "Chamartín": ["chamartin", "tetuan", "concha espina"],
    "Lavapiés": ["lavapies", "embajadores", "tirso de molina"],
    "La Latina": ["la latina", "cava baja", "rastro"],
}


def search_restaurants(
    cuisine: str = None,
    min_rating: float = 8.0,
    zone: str = None,
    limit: int = 10,
) -> list[dict]:
    """
    Busca restaurantes en TheFork Madrid.
    Devuelve lista de dicts con name, rating, cuisine, price, url, address.
    """
    results = _search_via_requests(cuisine, min_rating, zone, limit)

    if not results:
        results = _search_via_api(cuisine, min_rating, zone, limit)

    return results[:limit]


def _search_via_requests(cuisine, min_rating, zone, limit) -> list:
    """Intenta obtener resultados scrapeando la web de TheFork."""
    try:
        url = "https://www.thefork.es/restaurantes/madrid-c614891?sortBy=RATE_GEO&sortOrder=desc"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        # TheFork incluye datos en JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") not in ("Restaurant", "FoodEstablishment"):
                        continue
                    r = _parse_jsonld(item, cuisine, min_rating, zone)
                    if r:
                        results.append(r)
                        if len(results) >= limit:
                            return results
            except Exception:
                pass

        # Fallback: buscar en el JSON incrustado en la página (Next.js / __NEXT_DATA__)
        next_data = soup.find("script", id="__NEXT_DATA__")
        if next_data:
            try:
                payload = json.loads(next_data.string or "")
                restaurants_raw = _dig(payload, "restaurants") or _dig(payload, "items") or []
                for item in restaurants_raw:
                    r = _parse_generic(item, cuisine, min_rating, zone)
                    if r:
                        results.append(r)
                        if len(results) >= limit:
                            return results
            except Exception:
                pass

        return results

    except Exception as e:
        print(f"TheFork requests error: {e}")
        return []


def _search_via_api(cuisine, min_rating, zone, limit) -> list:
    """Intenta llamar a la API interna de TheFork."""
    try:
        # TheFork tiene una API GraphQL o REST interna
        api_url = "https://www.thefork.es/api/restaurant/search"
        params = {
            "cityId": 614891,
            "cityName": "Madrid",
            "sortBy": "RATE_GEO",
            "limit": limit * 2,
        }
        resp = requests.get(api_url, headers=HEADERS, params=params, timeout=15)
        if resp.status_code != 200:
            return []

        data = resp.json()
        raw_list = (
            data.get("items")
            or data.get("restaurants")
            or data.get("data", {}).get("restaurants")
            or []
        )
        results = []
        for item in raw_list:
            r = _parse_generic(item, cuisine, min_rating, zone)
            if r:
                results.append(r)
        return results

    except Exception as e:
        print(f"TheFork API error: {e}")
        return []


# ── Parsers ────────────────────────────────────────────────────────────────────

def _parse_jsonld(item: dict, cuisine, min_rating, zone) -> dict | None:
    try:
        rating = float(
            item.get("aggregateRating", {}).get("ratingValue", 0) or 0
        )
        if rating < min_rating:
            return None

        name = item.get("name", "")
        url = item.get("url", "")
        cuisine_text = ", ".join(item.get("servesCuisine", [])) if isinstance(
            item.get("servesCuisine"), list
        ) else str(item.get("servesCuisine", ""))
        price = item.get("priceRange", "")
        address = (
            item.get("address", {}).get("streetAddress", "")
            if isinstance(item.get("address"), dict)
            else ""
        )

        if not _passes_filters(name, cuisine_text, address, cuisine, zone):
            return None

        return {
            "name": name,
            "rating": rating,
            "cuisine": cuisine_text,
            "price": price,
            "url": url,
            "address": address,
        }
    except Exception:
        return None


def _parse_generic(item: dict, cuisine, min_rating, zone) -> dict | None:
    """Parsea un dict genérico de la API interna de TheFork."""
    try:
        # Intentar extraer rating de varios campos posibles
        rating = 0.0
        for key in ["ratingValue", "rating", "score", "aggregateRating"]:
            val = item.get(key)
            if isinstance(val, dict):
                val = val.get("ratingValue") or val.get("value")
            if val:
                try:
                    rating = float(str(val).replace(",", "."))
                    break
                except Exception:
                    pass

        if rating < min_rating:
            return None

        name = item.get("name") or item.get("restaurantName") or ""
        if not name:
            return None

        url = item.get("url") or item.get("restaurantUrl") or ""
        if url and not url.startswith("http"):
            url = "https://www.thefork.es" + url

        cuisine_text = item.get("cuisine") or item.get("cuisineType") or ""
        if isinstance(cuisine_text, list):
            cuisine_text = ", ".join(cuisine_text)

        price = item.get("priceRange") or item.get("price") or ""
        address = item.get("address") or item.get("streetAddress") or ""
        if isinstance(address, dict):
            address = address.get("streetAddress") or address.get("street") or ""

        if not _passes_filters(name, cuisine_text, address, cuisine, zone):
            return None

        return {
            "name": str(name),
            "rating": rating,
            "cuisine": str(cuisine_text),
            "price": str(price),
            "url": str(url),
            "address": str(address),
        }
    except Exception:
        return None


def _passes_filters(name, cuisine_text, address, cuisine_filter, zone_filter) -> bool:
    if cuisine_filter:
        combined = (name + " " + cuisine_text).lower()
        if cuisine_filter.lower() not in combined:
            return False
    if zone_filter and zone_filter in ZONE_KEYWORDS:
        combined = (name + " " + address).lower()
        # Normalizar tildes
        combined = combined.replace("á", "a").replace("é", "e").replace(
            "í", "i").replace("ó", "o").replace("ú", "u").replace("ñ", "n")
        if not any(kw in combined for kw in ZONE_KEYWORDS[zone_filter]):
            return False
    return True


def _dig(obj, key: str):
    """Busca recursivamente una clave en un dict/lista anidados."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            result = _dig(v, key)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _dig(item, key)
            if result is not None:
                return result
    return None
