import requests
import re
import os
import sys
from datetime import datetime

# --- CONFIGURACIÓN ---
YC_JOBS_URL = "https://news.ycombinator.com/jobs"

def limpiar_html(texto_html):
    """Limpia etiquetas HTML simples."""
    if not texto_html: return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, ' ', texto_html)

def extract_links_with_regex(html_content):
    """
    Extrae (url, titulo) del HTML de YC Jobs usando regex simple para no depender de BS4.
    Busca patrones de links en la tabla principal.
    """
    ofertas = []
    # Patrón para encontrar filas de jobs (aproximación simple)
    # YC usa HTML muy básico. <a href="...">Title</a>
    # Buscamos links que no sean 'ycombinator.com' (o si son, que sean de jobs)
    
    # Regex para capturar href y texto del link
    # <a href="https://..." ...>Title...</a>
    pattern = re.compile(r'<a href="([^"]+)"[^>]*>([^<]+)</a>')
    
    matches = pattern.findall(html_content)
    
    for url, titulo in matches:
        # Filtros básicos de limpieza de links irrelevantes del footer/header
        if "ycombinator.com" in url and "jobs" not in url and "item" not in url:
            continue
        if url.startswith("item?id="): # Es un link interno (Job post dentro de HN)
            url = f"https://news.ycombinator.com/{url}"
        if url == "https://news.ycombinator.com/news": continue
        if "security" in url or "legal" in url: continue
        
        # YC Jobs suele tener el formato "Company Is Hiring..."
        if len(titulo) < 10: continue

        ofertas.append({
            "url": url,
            "title": titulo,
        })
    return ofertas

def buscar_ofertas_yc(filtros_json):
    """
    Scrapea la página de Y Combinator Jobs.
    """
    print("\n🍊 INICIANDO MOTOR Y COMBINATOR JOBS...")
    
    # Role synonyms: todas las variantes del rol para matching en el título
    role_variants = [v.lower() for v in filtros_json.get("role_synonyms", filtros_json.get("role_keywords", []))]

    # Keywords técnicas: solo obligatorias si el stack ES la identidad del rol
    usar_keywords_como_filtro = filtros_json.get("keywords_are_hard_filter", False)
    lista_keywords = filtros_json.get("keyword_list", [])
    if not lista_keywords:
        keywords_str = filtros_json.get("keywords", "").lower()
        lista_keywords = [k.strip() for k in keywords_str.replace("(", "").replace(")", "").replace("OR", "").replace("AND", "").split() if len(k) > 2]
    lista_keywords = [k.lower() for k in lista_keywords]

    ofertas_encontradas = []

    try:
        print(f"   🔌 Conectando a {YC_JOBS_URL}...")
        resp = requests.get(YC_JOBS_URL, timeout=10)
        if resp.status_code != 200:
            print(f"      ❌ Error YC Jobs: Status {resp.status_code}")
            return []
            
        # Extracción simple
        raw_jobs = extract_links_with_regex(resp.text)
        print(f"      📥 Analizando {len(raw_jobs)} links encontrados.")

        for job in raw_jobs:
            titulo = job['title']
            url = job['url']
            
            # --- FILTRADO ---
            # En YC Jobs el título contiene toda la info disponible.
            texto_completo = titulo.lower()

            # Filtro de presencialidad explícita
            dealbreakers = ["onsite only", "on-site only", "in-office only", "local only", "no remote"]
            if any(db in texto_completo for db in dealbreakers):
                continue
            if "onsite in" in texto_completo and "remote" not in texto_completo:
                continue

            # Filtro de ROL: al menos una variante del rol debe aparecer en el título
            if role_variants:
                if not any(v in texto_completo for v in role_variants):
                    continue

            # Filtro de KEYWORDS: solo si el stack técnico es identidad del rol
            if usar_keywords_como_filtro and lista_keywords:
                if not any(k in texto_completo for k in lista_keywords):
                    continue

            ofertas_encontradas.append({
                "title": titulo,
                "company": "Y Combinator Startup", # Dificil extraer clean sin NLP
                "location": "Startup (See Description)",
                "description": titulo, # En YC Jobs el titulo es la descripción corta
                "job_url": url,
                "source": "YC Jobs",
                "date": datetime.now().isoformat()
            })

    except Exception as e:
        print(f"      ❌ Error procesando YC Jobs: {e}")
        return []

    print(f"   ✅ Se encontraron {len(ofertas_encontradas)} ofertas potenciales en YC Jobs.")
    
    # --- DEDUPLICACIÓN Y GUARDADO ---
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    try:
        from utils import JobHistoryManager, filtrar_por_ubicacion_estricta
        history = JobHistoryManager()
        
        # NUEVO: Filtro Estricto de Ubicación
        ofertas_geo_validas = filtrar_por_ubicacion_estricta(ofertas_encontradas)
        
        ofertas_nuevas = history.filter_new_offers(ofertas_geo_validas)
        print(f"   🤏 De {len(ofertas_geo_validas)} candidatas geo-validas, {len(ofertas_nuevas)} son NUEVAS en el historial.")
        
        if ofertas_nuevas:
            history.save_offers(ofertas_nuevas)
        else:
            print("🤷‍♂️ No hay ofertas nuevas de YC.")
            
        return ofertas_nuevas
        
    except ImportError:
        print("⚠️ Advertencia: utils.py no encontrado.")
        return ofertas_encontradas

# --- TEST ---
if __name__ == "__main__":
    filtros_test = {
        "keyword_list": ["Engineer", "Developer", "Back End"]
    }
    buscar_ofertas_yc(filtros_test)
