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
    
    # 1. Preparar Keywords (Adapter Pattern)
    lista_keywords = filtros_json.get("keyword_list", [])
    if not lista_keywords:
        keywords_str = filtros_json.get("keywords", "").lower()
        lista_keywords = [k.strip() for k in keywords_str.replace("(", "").replace(")", "").replace("OR", "").replace("AND", "").split() if len(k) > 2]

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
            
            # --- FILTRADO (Python Logic) ---
            # En YC Jobs, el título suele tener toda la info: "Company (YC W21) is hiring a Senior Eng..."
            texto_completo = titulo.lower()
            
            # Filtro Ubicación (Simple check si menciona lugar)
            # Si dice "San Francisco" y nuestro perfil es Remote, cuidado.
            # Pero YC suele ser flexible. Si no dice "Onsite only", lo consideramos.
            if "onsite in" in texto_completo:
                # Si no menciona remote, dudoso.
                if "remote" not in texto_completo:
                    continue

            # Filtro Keywords
            match_keyword = False
            if lista_keywords:
                for k in lista_keywords:
                    if k.lower() in texto_completo:
                        match_keyword = True
                        break
                
                if not match_keyword:
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
        from utils import JobHistoryManager
        history = JobHistoryManager()
        
        ofertas_nuevas = history.filter_new_offers(ofertas_encontradas)
        print(f"   🤏 De {len(ofertas_encontradas)} candidatas, {len(ofertas_nuevas)} son NUEVAS en el historial.")
        
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
