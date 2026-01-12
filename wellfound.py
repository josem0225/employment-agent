import requests
import re
import os
import sys
import json
import time
from datetime import datetime

# --- CONFIGURACIÓN ---
# Wellfound es difícil de scrapear directamente por URL de búsqueda sin JS.
# Usaremos una estrategia de búsqueda en paths públicos que a veces exponen datos en JSON incrustado o HTML simple.
# URL objetivo: Búsqueda general de Software Engineer
WELLFOUND_URL = "https://wellfound.com/role/l/software-engineer"

def limpiar_html(texto_html):
    if not texto_html: return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, ' ', texto_html)

def extract_jobs_from_html(html_content):
    """
    Intenta extraer trabajos del HTML de Wellfound.
    Wellfound usa React (Next.js), así que el HTML estático a veces contiene un JSON gigante en __NEXT_DATA__.
    """
    ofertas = []
    
    # ESTRATEGIA 1: Buscar __NEXT_DATA__ (JSON incrustado)
    try:
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html_content)
        if match:
            json_text = match.group(1)
            data = json.loads(json_text)
            # Navegar el JSON es complejo y cambia, pero intentamos encontrar listas de 'jobs'
            # Esta estructura es hipotética basada en estructuras comunes de Next.js
            # Si falla, haremos fallback a regex.
            pass 
    except:
        pass

    # ESTRATEGIA 2: Regex Brutal (Más resiliente a cambios de estructura JSON profunda)
    # Buscamos patrones de links de trabajos: /jobs/12345-company-title
    # Y titulos cercanos.
    
    # Patrón: <a href="/jobs/..." ...>Title</a>
    # Wellfound suele tener links tipo: href="/jobs/2997972-senior-software-engineer"
    link_pattern = re.compile(r'href="(/jobs/[^"]+)"[^>]*>([^<]+)</a>')
    matches = link_pattern.findall(html_content)
    
    seen_links = set()
    for link, text in matches:
        if link in seen_links: continue
        if len(text) < 5: continue # Ruido
        
        full_url = f"https://wellfound.com{link}"
        seen_links.add(link)
        
        # El texto del link suele ser el título.
        # En Wellfound a veces el nombre de la empresa está en otro div cercano, dificil de asociar con regex simple.
        # Asumiremos que el texto es el Título.
        
        ofertas.append({
            "title": text.strip(),
            "company": "Startup en Wellfound", # Placeholder
            "url": full_url,
            "description": "Ver detalles en Wellfound (Login requerido para aplicar)"
        })
        
    return ofertas

def buscar_ofertas_wellfound(filtros_json):
    print("\n✌️  INICIANDO MOTOR WELLFOUND (ANGELLIST)...")
    
    # 1. Preparar Keywords
    lista_keywords = filtros_json.get("keyword_list", [])
    if not lista_keywords:
        keywords = filtros_json.get("keywords", "").lower()
        lista_keywords = [k.strip() for k in keywords.replace("(", "").replace(")", "").replace("OR", "").replace("AND", "").split() if len(k) > 2]

    ofertas_encontradas = []

    # Headers para parecer un navegador real (Chrome Mac)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Referer': 'https://google.com',
        'Accept-Language': 'en-US,en;q=0.9'
    }

    try:
        print(f"   🔌 Conectando a {WELLFOUND_URL}...")
        # Nota: Si Wellfound detecta bot, devolverá 403 o Captcha.
        resp = requests.get(WELLFOUND_URL, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            raw_jobs = extract_jobs_from_html(resp.text)
            print(f"      Source descargado. Analizando {len(raw_jobs)} posibles candidatos...")

            for job in raw_jobs:
                titulo = job['title']
                url = job['url']
                
                # --- FILTRADO POR KEYWORDS ---
                match_keyword = False
                texto_check = titulo.lower()
                
                # Wellfound suele mostrar "Senior Software Engineer" etc.
                if lista_keywords:
                    for k in lista_keywords:
                        if k.lower() in texto_check:
                            match_keyword = True
                            break
                    if not match_keyword:
                        continue

                ofertas_encontradas.append({
                    "title": titulo,
                    "company": job['company'],
                    "location": "Startup (Remote check required)",
                    "description": job['description'],
                    "job_url": url,
                    "source": "Wellfound",
                    "date": datetime.now().isoformat()
                })
        elif resp.status_code == 403:
             print("      🔒 Wellfound bloqueó la conexión (Cloudflare 403). Se requiere navegador completo.")
        else:
             print(f"      ❌ Error Status: {resp.status_code}")

    except Exception as e:
        print(f"      ❌ Error inesperado Wellfound: {e}")

    print(f"   ✅ Se encontraron {len(ofertas_encontradas)} ofertas potenciales en Wellfound.")
    
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
        
        return ofertas_nuevas
        
    except ImportError:
        return ofertas_encontradas

if __name__ == "__main__":
    test_filters = {"keyword_list": ["Software", "Engineer", "Developer"]}
    buscar_ofertas_wellfound(test_filters)
