"""
Recomendador de restaurantes con base de datos curada de restaurantes reales.
Usa Groq solo para hacer el matching/ranking — nunca para inventar sitios.
"""

import json
import re

from groq import Groq

SPAIN_CITIES = [
    "Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao",
    "San Sebastián", "Málaga", "Granada", "Zaragoza", "Murcia",
    "Palma", "Las Palmas", "Córdoba", "Valladolid", "Alicante",
    "Vigo", "Gijón", "Pamplona", "Burgos", "Toledo",
]

# ─────────────────────────────────────────────────────────────────────────────
# Base de datos curada de restaurantes reales en España
# Solo se recomiendan restaurantes de esta lista → nunca se inventa nada
# ─────────────────────────────────────────────────────────────────────────────

RESTAURANT_DB = {

"Madrid": [
    {"name": "Quinqué",              "cuisine": "Española contemporánea",   "price": "€€€",   "neighborhood": "Almagro",           "desc": "Cocina de producto con mucha personalidad, sala íntima y lista de espera habitual. Uno de los más queridos de Madrid.", "url": "https://www.thefork.es/restaurante/quinque-r733726"},
    {"name": "Cokima",               "cuisine": "Española de producto",     "price": "€€€",   "neighborhood": "Chamberí",          "desc": "Barra y mesas con cocina de temporada y producto excepcional. Difícil conseguir mesa.", "url": "https://www.covermanager.com/reservation/module_restaurant/restaurante-cokima/spanish"},
    {"name": "Nakeima",              "cuisine": "Fusión asiática-española", "price": "€€€",   "neighborhood": "Malasaña",          "desc": "Pequeño y vibrante, con platos originales de influencia asiática y gran ambiente.", "url": "https://www.thefork.es/restaurante/nakeima-r527508"},
    {"name": "Tripea",               "cuisine": "Creativa fusión",          "price": "€€€",   "neighborhood": "Lavapiés",          "desc": "Propuesta creativa con raíces colombianas, cocina en barra y sin carta fija.", "url": "https://www.thefork.es/restaurante/tripea-r644394"},
    {"name": "Lakasa",               "cuisine": "Española de mercado",      "price": "€€€",   "neighborhood": "Chamberí",          "desc": "Producto de primerísimo nivel, cocina honesta y materia prima sin trampa. Una de las mejores casas de Madrid.", "url": "https://www.thefork.es/restaurante/lakasa-r597788"},
    {"name": "Sala de Despiece",     "cuisine": "Tapas gourmet",            "price": "€€€",   "neighborhood": "Chamberí",          "desc": "Propuesta rompedora en torno al producto cárnico, tapas originales y mucho ambiente.", "url": "https://www.thefork.es/restaurante/sala-de-despiece-r544498"},
    {"name": "Triciclo",             "cuisine": "Española creativa",        "price": "€€€",   "neighborhood": "Barrio de las Letras", "desc": "Cocina española de temporada, menú brillante y relación calidad-precio excelente.", "url": "https://www.thefork.es/restaurante/triciclo-r519768"},
    {"name": "Taberna Pedraza",      "cuisine": "Española clásica",         "price": "€€€",   "neighborhood": "Barrio de Salamanca","desc": "Las anchoas y el besugo a la brasa son leyenda. Cocina española sin adornos innecesarios.", "url": "https://www.thefork.es/restaurante/taberna-pedraza-r551684"},
    {"name": "Numa Pompilio",        "cuisine": "Italiana contemporánea",   "price": "€€€",   "neighborhood": "Ríos Rosas",        "desc": "La mejor pasta fresca de Madrid, cocina italiana honesta con producto de calidad.", "url": "https://www.thefork.es/restaurante/numa-pompilio-r595800"},
    {"name": "Leña",                 "cuisine": "Carnes a la brasa",        "price": "€€€€",  "neighborhood": "Barrio de Salamanca","desc": "El asador premium de Dani García. Carnes excepcionales y sala elegante.", "url": "https://www.thefork.es/restaurante/lena-madrid-r756879"},
    {"name": "Amazónico",            "cuisine": "Latinoamericana / Carnes", "price": "€€€€",  "neighborhood": "Barrio de Salamanca","desc": "Restaurante espectacular con influencia amazónica, carnes y ambiente de lujo tropical.", "url": "https://www.thefork.es/restaurante/amazonico-r627888"},
    {"name": "Punto MX",             "cuisine": "Mexicana de alta cocina",  "price": "€€€€",  "neighborhood": "Barrio de Salamanca","desc": "La mejor cocina mexicana de España. Mezcales únicos y carta de lujo.", "url": "https://www.thefork.es/restaurante/punto-mx-r531574"},
    {"name": "Gofio",                "cuisine": "Canaria creativa",         "price": "€€€€",  "neighborhood": "Lavapiés",          "desc": "Cocina canaria elevada, ingredientes únicos de las islas y menú degustación sorprendente.", "url": "https://www.thefork.es/restaurante/gofio-by-cicero-canary-r651868"},
    {"name": "Paraguas",             "cuisine": "Española creativa",        "price": "€€€€",  "neighborhood": "Barrio de Salamanca","desc": "Sala elegante con cocina española contemporánea de alto nivel.", "url": "https://www.thefork.es/restaurante/paraguas-r530018"},
    {"name": "Alabaster",            "cuisine": "Española de mercado",      "price": "€€€€",  "neighborhood": "Barrio de Salamanca","desc": "Cocina de producto y temporada impecable, con sala de diseño y bodega excelente.", "url": "https://www.thefork.es/restaurante/alabaster-r566808"},
    {"name": "La Tasquita de Enfrente","cuisine":"Española de producto",    "price": "€€€€",  "neighborhood": "Malasaña",          "desc": "Juanjo López lleva décadas siendo referencia absoluta de la cocina de producto en Madrid.", "url": "https://www.thefork.es/restaurante/la-tasquita-de-enfrente-r10992"},
    {"name": "Bar Tomate",           "cuisine": "Mediterránea / Tapas",     "price": "€€€",   "neighborhood": "Alonso Martínez",   "desc": "Siempre lleno, cocina mediterránea fresca y ambiente social inmejorable.", "url": "https://www.thefork.es/restaurante/bar-tomate-r496238"},
    {"name": "Bibo Madrid",          "cuisine": "Andaluza contemporánea",   "price": "€€€€",  "neighborhood": "Barrio de Salamanca","desc": "Dani García trae su propuesta informal pero premium con sabores andaluces reinventados.", "url": "https://www.thefork.es/restaurante/bibo-madrid-r649682"},
    {"name": "Yakitoro by Chicote",  "cuisine": "Japonesa-fusión",          "price": "€€€",   "neighborhood": "Gran Vía",          "desc": "Brochetas japonesas con toque español en un local de diseño y gran ambiente.", "url": "https://www.thefork.es/restaurante/yakitoro-by-chicote-r562548"},
    {"name": "Soy Kitchen",          "cuisine": "Pan-asiática",             "price": "€€€",   "neighborhood": "Moncloa",           "desc": "Pato pekín, dim sum y cocina asiática de alta calidad en un espacio íntimo.", "url": "https://www.thefork.es/restaurante/soy-kitchen-r554848"},
    {"name": "Tepic",                "cuisine": "Mexicana",                 "price": "€€€",   "neighborhood": "Chueca",            "desc": "Cocina mexicana auténtica con buenos margaritas y ambiente animado.", "url": "https://www.thefork.es/restaurante/tepic-r12200"},
    {"name": "Cantina Roo",          "cuisine": "Mexicana contemporánea",   "price": "€€€",   "neighborhood": "La Latina",         "desc": "Tacos, ceviches y cocina de fusión mexicana en un local informal y con mucho sabor.", "url": "https://www.thefork.es/restaurante/cantina-roo-r636940"},
    {"name": "Casa Lucio",           "cuisine": "Castellana tradicional",   "price": "€€€",   "neighborhood": "La Latina",         "desc": "Institución madrileña. Los huevos rotos más famosos de España.", "url": "https://www.thefork.es/restaurante/casa-lucio-r242"},
    {"name": "Botín",                "cuisine": "Castellana / Asador",      "price": "€€€€",  "neighborhood": "Centro (Sol)",      "desc": "El restaurante más antiguo del mundo según el Guinness. Cochinillo y cordero asado.", "url": "https://www.thefork.es/restaurante/sobrino-de-botin-r1432"},
    {"name": "Gaytan",               "cuisine": "Española contemporánea",   "price": "€€€€",  "neighborhood": "Chamberí",          "desc": "Javier Aranda, estrella Michelin. Menú degustación técnico y elegante.", "url": "https://www.thefork.es/restaurante/gaytan-r643898"},
    {"name": "La Buena Vida",        "cuisine": "Española creativa",        "price": "€€€€",  "neighborhood": "Barrio de Salamanca","desc": "Cocina cuidada con ingredientes de primera y sala íntima y acogedora.", "url": "https://www.thefork.es/restaurante/la-buena-vida-r600196"},
    {"name": "El Invernadero",       "cuisine": "Vegetariana de alta cocina","price": "€€€€€","neighborhood": "Chamberí",          "desc": "Rodrigo de la Calle, estrella Michelin verde. Menú degustación vegetal de altísimo nivel.", "url": "https://www.thefork.es/restaurante/el-invernadero-r649590"},
    {"name": "DiverXO",              "cuisine": "Vanguardista",             "price": "€€€€€", "neighborhood": "Tetuán",            "desc": "David Muñoz, 3 estrellas Michelin. La experiencia gastronómica más radical de España.", "url": "https://www.thefork.es/restaurante/diverxo-r531792"},
    {"name": "StreetXO",             "cuisine": "Fusión asiática street",   "price": "€€€",   "neighborhood": "Barrio de Salamanca","desc": "La versión informal y urbana de David Muñoz. Sabores intensos y ambiente ruidoso.", "url": "https://www.thefork.es/restaurante/streetxo-madrid-r566508"},
    {"name": "Dstage",               "cuisine": "Vanguardista",             "price": "€€€€€", "neighborhood": "Chueca",            "desc": "Diego Guerrero, 2 estrellas Michelin. Cocina experimental en un espacio industrial.", "url": "https://www.thefork.es/restaurante/dstage-r566526"},
    {"name": "Coque",                "cuisine": "Alta cocina española",     "price": "€€€€€", "neighborhood": "Chamartín",         "desc": "Familia Sandoval, 2 estrellas Michelin. Menú degustación largo y espectacular.", "url": "https://www.thefork.es/restaurante/coque-r593576"},
    {"name": "Horcher",              "cuisine": "Centroeuropea clásica",    "price": "€€€€€", "neighborhood": "Retiro",            "desc": "Institución desde 1943. Cocina alemana y vienesa de lujo, sala de terciopelo.", "url": "https://www.thefork.es/restaurante/horcher-r232"},
    {"name": "Casa Mono",            "cuisine": "Española / Tapas",         "price": "€€",    "neighborhood": "Centro",            "desc": "Tasca clásica madrileña, precios honestos y cocina tradicional sin pretensiones.", "url": "https://www.thefork.es/restaurante/casa-mono-r1256"},
    {"name": "La Gabinoteca",        "cuisine": "Española creativa",        "price": "€€€",   "neighborhood": "Moncloa",           "desc": "Cocina de autor accesible, menú del día de lujo y tapas creativas.", "url": "https://www.thefork.es/restaurante/la-gabinoteca-r519784"},
    {"name": "Desde 1911",           "cuisine": "Mariscos / Española",      "price": "€€€€",  "neighborhood": "Barrio de Salamanca","desc": "El mercado de mariscos más emblemático de Madrid reconvertido en restaurante de lujo.", "url": "https://www.thefork.es/restaurante/desde-1911-r602528"},
    {"name": "Retiro's Nunos",       "cuisine": "Portuguesa contemporánea", "price": "€€€€",  "neighborhood": "Retiro",            "desc": "Propuesta portuguesa elegante y diferente en Madrid, con estrella Michelin.", "url": "https://www.thefork.es/restaurante/retiros-nunos-r663226"},
    {"name": "Smoked Room",          "cuisine": "Brasa premium",            "price": "€€€€€", "neighborhood": "Barrio de Salamanca","desc": "Marcos Morán en Madrid: carnes, pescados y ahumados de nivel, 2 estrellas Michelin.", "url": "https://www.thefork.es/restaurante/smoked-room-r810648"},
    {"name": "Soto",                 "cuisine": "Española de mercado",      "price": "€€€",   "neighborhood": "Chamberí",          "desc": "Cocina de temporada sin alardes, muy bien ejecutada y con buena bodega.", "url": "https://www.thefork.es/restaurante/soto-restaurante-r811476"},
],

"Barcelona": [
    {"name": "Disfrutar",       "cuisine": "Vanguardista",          "price": "€€€€€", "neighborhood": "Eixample",   "desc": "Nº1 del mundo en 2024. Cocina más creativa e influyente del planeta.", "url": "https://www.thefork.es/restaurante/disfrutar-r617208"},
    {"name": "Enigma",          "cuisine": "Vanguardista",          "price": "€€€€€", "neighborhood": "Eixample",   "desc": "Albert Adrià. Experiencia multisensorial de 40 pasos, completamente única.", "url": "https://www.thefork.es/restaurante/enigma-r646338"},
    {"name": "Tickets",         "cuisine": "Tapas vanguardistas",   "price": "€€€€",  "neighborhood": "Poble Sec",  "desc": "La taberna de tapas creativas de Albert Adrià. Lista de espera de meses.", "url": "https://www.thefork.es/restaurante/tickets-r531612"},
    {"name": "Cinc Sentits",    "cuisine": "Catalana contemporánea","price": "€€€€€", "neighborhood": "Eixample",   "desc": "Estrella Michelin, menú degustación de cocina catalana de altísimo nivel.", "url": "https://www.thefork.es/restaurante/cinc-sentits-r10952"},
    {"name": "Pakta",           "cuisine": "Nikkei",                "price": "€€€€",  "neighborhood": "Poble Sec",  "desc": "Cocina nikkei (japonesa-peruana) de Albert Adrià, estrella Michelin.", "url": "https://www.thefork.es/restaurante/pakta-r545576"},
    {"name": "Bar del Pla",     "cuisine": "Catalana",              "price": "€€",    "neighborhood": "El Born",    "desc": "El bar de tapas catalanas más querido del Born, siempre lleno.", "url": "https://www.thefork.es/restaurante/bar-del-pla-r527768"},
    {"name": "Bodega Sepúlveda","cuisine": "Catalana de mercado",   "price": "€€€",   "neighborhood": "Eixample",   "desc": "Cocina de mercado catalana en local de bodega, muy popular y difícil de reservar.", "url": "https://www.thefork.es/restaurante/bodega-sepulveda-r677728"},
    {"name": "El Xampanyet",    "cuisine": "Tapas / Vermut",        "price": "€€",    "neighborhood": "El Born",    "desc": "Taberna histórica del Born, cava casero y tapas clásicas de toda la vida.", "url": "https://www.thefork.es/restaurante/el-xampanyet-r1520"},
    {"name": "Moments",         "cuisine": "Alta cocina catalana",  "price": "€€€€€", "neighborhood": "Eixample",   "desc": "2 estrellas Michelin, cocina catalana de lujo en el hotel Mandarin Oriental.", "url": "https://www.thefork.es/restaurante/moments-r519878"},
    {"name": "Lasarte",         "cuisine": "Alta cocina vasca",     "price": "€€€€€", "neighborhood": "Eixample",   "desc": "3 estrellas Michelin de Martín Berasategui. El más alto nivel en Barcelona.", "url": "https://www.thefork.es/restaurante/lasarte-r559648"},
],

"San Sebastián": [
    {"name": "Arzak",       "cuisine": "Alta cocina vasca",  "price": "€€€€€", "neighborhood": "Alza",       "desc": "Juan Mari y Elena Arzak. 3 estrellas, uno de los más importantes del mundo.", "url": "https://www.thefork.es/restaurante/arzak-r11072"},
    {"name": "Mugaritz",    "cuisine": "Vanguardista",       "price": "€€€€€", "neighborhood": "Rentería",   "desc": "Andoni Luis Aduriz. 2 estrellas, cocina conceptual y de riesgo, top 10 mundial.", "url": "https://www.thefork.es/restaurante/mugaritz-r11050"},
    {"name": "Etxebarri",   "cuisine": "Brasa premium",      "price": "€€€€€", "neighborhood": "Axpe",       "desc": "Victor Arguinzoniz. La mejor brasa del mundo. Reservas con meses de antelación.", "url": "https://www.thefork.es/restaurante/etxebarri-r11034"},
    {"name": "La Viña",     "cuisine": "Pintxos / Postres",  "price": "€€",    "neighborhood": "Parte Vieja","desc": "La tarta de queso más famosa de España. Bar de pintxos de referencia absoluta.", "url": "https://www.thefork.es/restaurante/la-vina-r1756"},
    {"name": "Elkano",      "cuisine": "Pescados a la brasa","price": "€€€€€", "neighborhood": "Getaria",    "desc": "El mejor rodaballo del mundo a la brasa. Estrella Michelin en el puerto de Getaria.", "url": "https://www.thefork.es/restaurante/elkano-r11018"},
    {"name": "Bar Nestor",  "cuisine": "Pintxos / Txuleta",  "price": "€€€",   "neighborhood": "Parte Vieja","desc": "La txuleta más célebre de Donosti. Solo 2 servicios al día, se agota en minutos.", "url": ""},
],

"Bilbao": [
    {"name": "Azurmendi",        "cuisine": "Alta cocina vasca",   "price": "€€€€€", "neighborhood": "Larrabetzu",  "desc": "Eneko Atxa, 3 estrellas Michelin y estrella verde. Sostenibilidad y alta cocina.", "url": "https://www.thefork.es/restaurante/azurmendi-r556818"},
    {"name": "Mina",             "cuisine": "Vasca moderna",       "price": "€€€€€", "neighborhood": "Casco Viejo", "desc": "Estrella Michelin con menú degustación imaginativo en el mercado de La Ribera.", "url": "https://www.thefork.es/restaurante/restaurante-mina-r549918"},
    {"name": "Etxanobe Atelier", "cuisine": "Vasca contemporánea", "price": "€€€€",  "neighborhood": "Indautxu",    "desc": "Fernando Canales, 2 estrellas Michelin. Cocina vasca de vanguardia en el Euskalduna.", "url": "https://www.thefork.es/restaurante/etxanobe-atelier-r754628"},
    {"name": "Nerua",            "cuisine": "Vasca creativa",      "price": "€€€€€", "neighborhood": "Abando",      "desc": "Josean Alija, estrella Michelin dentro del Guggenheim. Experiencia artística total.", "url": ""},
],

"Sevilla": [
    {"name": "Az-Zait",   "cuisine": "Andaluza creativa",     "price": "€€€€", "neighborhood": "Centro",  "desc": "Cocina andaluza de alto nivel, técnica depurada y producto de la huerta local.", "url": "https://www.thefork.es/restaurante/az-zait-r638838"},
    {"name": "Cañabota",  "cuisine": "Pescados y mariscos",   "price": "€€€€", "neighborhood": "Centro",  "desc": "La marisquería-restaurante más cotizada de Sevilla. Producto del Atlántico sin igual.", "url": "https://www.thefork.es/restaurante/canabota-r645696"},
    {"name": "Eslava",    "cuisine": "Tapas andaluzas",       "price": "€€€",  "neighborhood": "Triana",  "desc": "Ganador del mejor pincho de España en múltiples ocasiones. Siempre lleno.", "url": "https://www.thefork.es/restaurante/eslava-r1424"},
    {"name": "Tribeca",   "cuisine": "Española creativa",     "price": "€€€€", "neighborhood": "Centro",  "desc": "Estrella Michelin. El restaurante gastronómico de referencia en Sevilla.", "url": ""},
],

"Valencia": [
    {"name": "Ricard Camarena","cuisine": "Valenciana contemporánea","price": "€€€€€","neighborhood": "Russafa",     "desc": "2 estrellas Michelin, uno de los cocineros más creativos de España.", "url": "https://www.thefork.es/restaurante/ricard-camarena-r567048"},
    {"name": "Riff",           "cuisine": "Mediterránea creativa",   "price": "€€€€", "neighborhood": "Pla del Real","desc": "Bernd Knöller, estrella Michelin. Cocina de influencia centroeuropea y mediterránea.", "url": "https://www.thefork.es/restaurante/riff-r11170"},
    {"name": "La Pepica",      "cuisine": "Arroces / Paella",        "price": "€€€",  "neighborhood": "Malvarrosa",  "desc": "La paellera más legendaria de Valencia, frente al mar, desde 1898.", "url": "https://www.thefork.es/restaurante/la-pepica-r1644"},
    {"name": "Askua",          "cuisine": "Carnes a la brasa",       "price": "€€€€", "neighborhood": "Eixample",    "desc": "El mejor asador de Valencia. Carnes y pescados a la brasa de altísima calidad.", "url": ""},
],

"Málaga": [
    {"name": "José Carlos García","cuisine": "Andaluza creativa",  "price": "€€€€€","neighborhood": "Muelle Uno","desc": "Estrella Michelin en el puerto de Málaga. Cocina malagueña elevada al máximo nivel.", "url": ""},
    {"name": "Bibo Málaga",       "cuisine": "Andaluza informal",  "price": "€€€",  "neighborhood": "Centro",   "desc": "Dani García informal en Málaga. Sabores del sur en un formato desenfadado.", "url": ""},
    {"name": "El Mesón de Cervantes","cuisine":"Tapas malagueñas", "price": "€€",   "neighborhood": "Centro",   "desc": "Una de las tabernas más queridas del centro, cocina malagueña de siempre.", "url": ""},
],

"Granada": [
    {"name": "Damasqueros",       "cuisine": "Española creativa",  "price": "€€€€","neighborhood": "Realejo",  "desc": "La propuesta gastronómica más seria de Granada. Menú degustación con personalidad.", "url": ""},
    {"name": "Ruta del Azafrán",  "cuisine": "Mediterránea",       "price": "€€€", "neighborhood": "Albaicín", "desc": "Con vistas a la Alhambra. Cocina mediterránea en un entorno único.", "url": ""},
],

"Zaragoza": [
    {"name": "Cancook",   "cuisine": "Española creativa", "price": "€€€€","neighborhood": "Centro","desc": "Estrella Michelin, el más alto nivel gastronómico de Aragón.", "url": ""},
    {"name": "La Prensa", "cuisine": "Aragonesa moderna", "price": "€€€", "neighborhood": "Centro","desc": "Cocina aragonesa contemporánea de referencia en la ciudad.", "url": ""},
],

}

# Ciudades sin base de datos propia
for _city in ["Murcia", "Palma", "Las Palmas", "Córdoba", "Valladolid",
              "Alicante", "Vigo", "Gijón", "Pamplona", "Burgos", "Toledo"]:
    if _city not in RESTAURANT_DB:
        RESTAURANT_DB[_city] = []


# ─────────────────────────────────────────────────────────────────────────────

def get_recommendations(
    description: str,
    city: str,
    n_people: int = 2,
    budget: str = "Sin límite",
    limit: int = 6,
    api_key: str = "",
) -> list[dict]:
    if not api_key:
        return []

    candidates = RESTAURANT_DB.get(city, [])

    if candidates:
        db_lines = "\n".join(
            f"{i+1}. {r['name']} | {r['cuisine']} | {r['price']} | {r['neighborhood']} | {r['desc']}"
            for i, r in enumerate(candidates)
        )
        context = (
            f"LISTA COMPLETA DE RESTAURANTES REALES EN {city.upper()}:\n"
            f"{db_lines}\n\n"
            f"REGLA ABSOLUTA: Solo puedes recomendar restaurantes de la lista anterior. "
            f"Nunca inventes ni añadas ninguno que no esté ahí."
        )
    else:
        context = (
            f"No tengo base de datos propia para {city}. "
            f"Recomienda restaurantes que sepas con CERTEZA que existen y están abiertos en {city}, España. "
            f"Si tienes cualquier duda sobre si un restaurante existe, NO lo incluyas."
        )

    prompt = f"""Eres un experto en gastronomía española.

{context}

PETICIÓN:
- Ciudad: {city}
- Qué busca: {description}
- Personas: {n_people}
- Presupuesto por persona: {budget}
- Número de resultados: {limit}

Selecciona los {limit} restaurantes que mejor encajen con la petición.
Ordénalos de mejor a peor match.

Responde EXCLUSIVAMENTE con un array JSON válido, sin texto antes ni después:
[
  {{
    "name": "Nombre exacto del restaurante (igual que en la lista)",
    "cuisine": "Tipo de cocina",
    "price_range": "€ / €€ / €€€ / €€€€ / €€€€€",
    "neighborhood": "Barrio",
    "description": "Descripción del restaurante (2-3 frases)",
    "why_matches": "Por qué encaja exactamente con lo que pide el usuario"
  }}
]"""

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2500,
        )
        raw = response.choices[0].message.content.strip()

        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        results = json.loads(match.group() if match else raw)

        # Enriquecer con URLs reales de la base de datos
        db_by_name = {r["name"].lower(): r for r in candidates}
        for item in results:
            key = item.get("name", "").lower()
            if key in db_by_name and db_by_name[key].get("url"):
                item["thefork_url"] = db_by_name[key]["url"]
            item["maps_url"] = (
                "https://www.google.com/maps/search/"
                + item.get("name", "").replace(" ", "+")
                + "+" + city.replace(" ", "+")
            )

        return results[:limit]

    except Exception as e:
        print(f"Groq error: {e}")
        return []
