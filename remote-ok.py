import requests
import html
import re
import os
import json
import sys
from datetime import datetime

# --- CONFIGURACIÓN ---
REMOTEOK_API_URL = "https://remoteok.com/api"

def limpiar_html(texto_html):
    """Limpia etiquetas HTML simples."""
    if not texto_html: return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, ' ', texto_html)

def buscar_ofertas_remoteok(filtros_json):
    """
    Consume la API oficial de RemoteOK.
    """
    print("\n📡 INICIANDO MOTOR REMOTE OK (Vía API)...")
    
    # Role synonyms: todas las variantes del rol para matching
    role_variants = [v.lower() for v in filtros_json.get("role_synonyms", filtros_json.get("role_keywords", []))]

    # Keywords técnicas: solo obligatorias si el stack ES la identidad del rol
    usar_keywords_como_filtro = filtros_json.get("keywords_are_hard_filter", False)
    lista_keywords = filtros_json.get("keyword_list", [])
    if not lista_keywords:
        keywords_str = filtros_json.get("keywords", "").lower()
        lista_keywords = [k.strip() for k in keywords_str.replace("(", "").replace(")", "").replace("OR", "").replace("AND", "").split() if len(k) > 2]
    lista_keywords = [k.lower() for k in lista_keywords]

    # Red Flags de ciudadanía/restricción explícita en descripción
    red_flags = [
        "us citizen", "u.s. citizen", "citizenship required",
        "must reside in usa", "must reside in the us",
        "authorized to work in", "work authorization required",
        "no visa sponsorship",
    ]

    ofertas_encontradas = []

    try:
        # RemoteOK a veces pide User-Agent para no bloquear
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        print(f"   🔌 Conectando a {REMOTEOK_API_URL}...")
        
        resp = requests.get(REMOTEOK_API_URL, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"      ❌ Error API RemoteOK: Status {resp.status_code}")
            return []
            
        data = resp.json()
        print(f"      📥 Descargadas {len(data)} entradas crudas.") # data[0] suele ser legal text, el resto jobs

        # La primera entrada suele ser info legal, la ignoramos si no tiene 'title' o 'company'
        jobs_list = [item for item in data if 'title' in item and 'company' in item]

        for job in jobs_list:
            titulo = job.get('title', '')
            empresa = job.get('company', '')
            descripcion = job.get('description', '')
            job_url = job.get('url', '')
            tags = job.get('tags', []) # RemoteOK tiene tags, útil
            location_api = job.get('location', '').lower()
            
            # --- FILTRADO ---

            # 1. Filtro Ubicación: solo restricciones explícitas en campo location
            location_restrictiva = any(flag in location_api for flag in ["only", "us only", "usa only", "europe only", "uk only", "canada only"])
            location_abierta = any(flag in location_api for flag in ["worldwide", "latam", "anywhere", "global", "international"])
            if location_restrictiva and not location_abierta:
                continue

            texto_completo = (titulo + " " + descripcion).lower()
            tags_lower = [t.lower() for t in tags]

            # 2. Red Flags de ciudadanía en descripción
            if any(flag in texto_completo for flag in red_flags):
                continue

            # 3. Filtro de ROL: al menos una variante del rol debe aparecer
            if role_variants:
                if not any(v in texto_completo or v in titulo.lower() for v in role_variants):
                    continue

            # 4. Filtro de KEYWORDS: solo si el stack técnico es identidad del rol
            if usar_keywords_como_filtro and lista_keywords:
                match_keyword = any(
                    k in texto_completo or k in tags_lower
                    for k in lista_keywords
                )
                if not match_keyword:
                    continue
            
            # Si pasa todos los filtros, es candidata
            ofertas_encontradas.append({
                "title": titulo,
                "company": empresa,
                "location": f"Remote ({location_api or 'Worldwide'})",
                "description": limpiar_html(descripcion),
                "job_url": job_url,
                "source": "RemoteOK",
                "date": job.get('date', datetime.now().isoformat())
            })

    except Exception as e:
        print(f"      ❌ Error procesando RemoteOK: {e}")
        return []

    print(f"   ✅ Se encontraron {len(ofertas_encontradas)} ofertas potenciales en RemoteOK.")
    
    # --- DEDUPLICACIÓN Y GUARDADO ---
    # Usamos el gestor centralizado
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
            print("🤷‍♂️ No hay ofertas nuevas de RemoteOK.")
            
        return ofertas_nuevas
        
    except ImportError:
        print("⚠️ Advertencia: utils.py no encontrado, devolviendo sin guardar en historial.")
        return ofertas_encontradas

# --- TEST ---
if __name__ == "__main__":
    filtros_test = {
        "keyword_list": ["Python", "Django", "Backend"]
    }
    buscar_ofertas_remoteok(filtros_test)
