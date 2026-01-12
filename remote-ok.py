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
    
    # 1. Preparar Keywords (Adapter Pattern)
    lista_keywords = filtros_json.get("keyword_list", [])
    if not lista_keywords:
        # Fallback a limpiar el string si no hay lista
        keywords_str = filtros_json.get("keywords", "").lower()
        lista_keywords = [k.strip() for k in keywords_str.replace("(", "").replace(")", "").replace("OR", "").replace("AND", "").split() if len(k) > 2]

    # Red Flags específicos
    red_flags = [
        "us citizen", "u.s. citizen", "citizenship required", 
        "must reside in usa", "must reside in the us", 
        "location: united states", "location: us"
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
            
            # --- FILTRADO (Python Logic) ---
            
            # 1. Filtro Ubicación (Red Flags en campo location)
            if any(flag in location_api for flag in ["united states", "usa only", "us only", "europe only", "uk only"]):
                # Si pide explicitamente US/EU y no dice "worldwide" ni "latam", descartar
                if "worldwide" not in location_api and "latam" not in location_api and "anywhere" not in location_api:
                    continue

            # 2. Filtro Red Flags en descripción
            texto_completo = (titulo + " " + descripcion).lower()
            if any(flag in texto_completo for flag in red_flags):
                continue
                
            # 3. Filtro Keywords (Universal)
            # Verificamos si CUALQUIERA de las keywords está presente
            match_keyword = False
            if lista_keywords:
                # Chequeamos en titulo, descripcion O tags
                for k in lista_keywords:
                    k_lower = k.lower()
                    if k_lower in texto_completo or k_lower in [t.lower() for t in tags]:
                        match_keyword = True
                        break
                
                if not match_keyword:
                    continue # No hizo match con ninguna tecnologia del perfil
            
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
