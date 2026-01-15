import os
import sys
import requests
import html
import re
import json
import time
import concurrent.futures
from datetime import datetime

# --- CONFIGURACIÓN API HACKER NEWS ---
HN_API_BASE = "https://hacker-news.firebaseio.com/v0"

def get_latest_hiring_thread_id():
    """
    Busca el ID del último post 'Ask HN: Who is hiring?'
    """
    print("📡 Conectando a Hacker News para buscar el hilo de este mes...")
    try:
        # El usuario 'whoishiring' es el bot oficial que postea estos hilos
        resp = requests.get(f"{HN_API_BASE}/user/whoishiring/submitted.json")
        submitted_ids = resp.json()[:30] # Revisamos los últimos 30 posts

        for item_id in submitted_ids:
            item_resp = requests.get(f"{HN_API_BASE}/item/{item_id}.json")
            item = item_resp.json()
            title = item.get('title', '')
            
            # Buscamos el patrón exacto "Who is hiring?"
            if "Ask HN: Who is hiring?" in title:
                print(f"   ✅ Hilo encontrado: '{title}' (ID: {item_id})")
                return item_id, title
                
        print("❌ No se encontró el hilo de contratación reciente.")
        return None, None
    except Exception as e:
        print(f"❌ Error conectando a HN: {e}")
        return None, None

def fetch_comment_details(comment_id):
    """
    Descarga un comentario individual y lo limpia.
    """
    try:
        resp = requests.get(f"{HN_API_BASE}/item/{comment_id}.json", timeout=10)
        data = resp.json()
        
        if not data or 'text' not in data or data.get('deleted'):
            return None
            
        # Hacker News devuelve HTML, hay que limpiarlo a texto plano
        raw_html = data['text']
        clean_text = html.unescape(re.sub(r'<[^>]+>', ' ', raw_html)) # Quitar tags HTML
        
        return {
            "id": data['id'],
            "by": data.get('by', 'anon'),
            "time": data.get('time'),
            "text": clean_text.strip(),
            "url": f"https://news.ycombinator.com/item?id={comment_id}"
        }
    except:
        return None

def filtrar_oferta_hn(oferta, keywords, red_flags, filtros_extra={}):
    """
    Aplica filtros de texto básicos (Keywords y Red Flags).
    """
    texto = oferta['text'].lower()
    
    # 1. Filtro "Remote" (Obligatorio en nuestra estrategia)
    # 1. Filtro "Remote" MEJORADO (Anti-Falsos Positivos)
    # Primero buscamos DEALBREAKERS explicitos que indican presencialidad
    dealbreakers = [
        r"\bno remote\b", r"\bnot remote\b", r"\bonsite only\b", 
        r"\boffice based\b", r"\bhybrid only\b", r"\bmust be in\b"
    ]
    
    for db in dealbreakers:
        if re.search(db, texto):
            return False

    # Luego validamos que DIGA remote
    if "remote" not in texto:
        return False

    # 2. Filtro de Red Flags (Ciudadanía, etc)
    for flag in red_flags:
        if flag in texto:
            return False
            
    # 3. Filtro de ROLES (Identidad) - "MUST HAVE"
    # Si definimos roles explícitos (ej: "Product Manager"), la oferta DEBE tener al menos uno.
    role_keywords = filtros_extra.get('role_keywords', [])
    if role_keywords:
        role_found = False
        for role in role_keywords:
            # Búsqueda de palabra completa para evitar falsos positivos parciales (ej: "Manager" en "Managerial")
            # Usamos boundaries \b si es posible, o in simple.
            # Dado que los roles pueden ser "Product Manager", 'in' está bien.
            if role.lower() in texto:
                role_found = True
                break
        
        if not role_found:
             return False

    # 4. Filtro de SKILLS (Herramientas) - "NICE TO HAVE" / Validación Secundaria
    # Ya sabemos que es el ROL correcto, ahora vemos si usa las TECNOLOGÍAS correctas.
    # Si la lista de keywords está vacía, pasa. Si no, verificamos coincidencia.
    keywords_clean = []
    
    if isinstance(keywords, list):
        keywords_clean = [k.strip().lower() for k in keywords]
    elif isinstance(keywords, str):
         keywords_clean = [k.strip().lower() for k in keywords.replace("(", "").replace(")", "").replace("OR", "").replace("AND", "").split()]
    
    if keywords_clean:
         found = False
         for k in keywords_clean:
             if len(k) > 1 and k in texto: # len > 1 para evitar "C" o "R" sueltos falsos
                 found = True
                 break
         
         if not found:
             return False

    return True

def buscar_ofertas_hackernews(filtros_json):
    """
    Función principal orquestadora para HN.
    """
    print("\n🍊 INICIANDO MOTOR HACKER NEWS (La Cueva de los Ingenieros)...")
    
    # Adapter: Intentamos usar la lista limpia, si no, el string antiguo
    keywords = filtros_json.get("keyword_list", [])
    if not keywords:
        keywords = filtros_json.get("keywords", "")
    
    # Definimos Red Flags específicas para texto libre
    red_flags = [
        "us citizen", "u.s. citizen", "citizenship required", 
        "must reside in usa", "must reside in the us", 
        "onsite in", "on-site in" # Si es on-site no nos sirve
    ]

    # 1. Obtener el hilo madre
    thread_id, thread_title = get_latest_hiring_thread_id()
    if not thread_id:
        return []

    # 2. Obtener lista de comentarios (IDs)
    try:
        resp = requests.get(f"{HN_API_BASE}/item/{thread_id}.json")
        all_kids_ids = resp.json().get('kids', [])
        print(f"   📦 El hilo tiene {len(all_kids_ids)} comentarios/ofertas totales.")
    except Exception as e:
        print(f"❌ Error obteniendo comentarios: {e}")
        return []

    ofertas_crudas = []
    print("   🚀 Descargando ofertas en paralelo (esto será rápido)...")
    
    # 3. Descarga Paralela (ThreadPool)
    # Usamos 20 hilos simultáneos para volar
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fetch_comment_details, kid_id) for kid_id in all_kids_ids]
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            if i % 100 == 0 and i > 0:
                print(f"      ...procesadas {i}/{len(all_kids_ids)}...")
            
            result = future.result()
            if result:
                # Filtrado preliminar inmediato para no guardar basura
                if filtrar_oferta_hn(result, keywords, red_flags, filtros_json):
                    # Formateamos para que parezca una oferta estandarizada
                    ofertas_crudas.append({
                        "title": f"HN Offer by {result['by']}", # HN no tiene títulos, usamos el autor
                        "company": "Startup (See Description)", # A deducir por IA luego
                        "location": "Remote (Verificado en texto)",
                        "description": result['text'], # AQUÍ ESTÁ EL ORO
                        "job_url": result['url'],
                        "source": "HackerNews"
                    })

    print(f"   💎 Se encontraron {len(ofertas_crudas)} ofertas potenciales en HN después del filtrado básico.")
    
    # 4. Deduplicación Histórica y Guardado
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from utils import JobHistoryManager, filtrar_por_ubicacion_estricta
    history = JobHistoryManager()
    
    # NUEVO: Filtro Estricto de Ubicación
    ofertas_geo_validas = filtrar_por_ubicacion_estricta(ofertas_crudas)

    ofertas_nuevas = history.filter_new_offers(ofertas_geo_validas)
    print(f"   🤏 De {len(ofertas_geo_validas)} candidatas geo-validas, {len(ofertas_nuevas)} son NUEVAS en el historial.")
    
    if ofertas_nuevas:
        history.save_offers(ofertas_nuevas)
    else:
        print("🤷‍♂️ No hay ofertas nuevas de HN.")

    return ofertas_nuevas

def guardar_en_archivo(ofertas):
    if not ofertas:
        print("⚠️ No hay ofertas de HN para guardar.")
        return

    # Ruta consistente con el módulo de LinkedIn
    ruta_base = "/Users/josemiguelrozobaez/documents/develop/agent-offers/"
    os.makedirs(ruta_base, exist_ok=True)
    
    # Prefijo HN para distinguir
    nombre_archivo = "HN_" + datetime.now().strftime("%d%b%H%M") + ".json"
    ruta_completa = os.path.join(ruta_base, nombre_archivo)
    
    try:
        with open(ruta_completa, 'w', encoding='utf-8') as f:
            json.dump(ofertas, f, indent=4, ensure_ascii=False)
        print(f"\n💾 ARCHIVO HN GUARDADO EXITOSAMENTE:")
        print(f"   📂 {ruta_completa}")
    except Exception as e:
        print(f"❌ Error guardando archivo HN: {e}")

# --- TEST ---
if __name__ == "__main__":
    filtros_test = {
        "keywords": "Python React", # Palabras clave simples
    }
    resultados = buscar_ofertas_hackernews(filtros_test)
    
    # Mostrar un ejemplo
    if resultados:
        print("\n--- EJEMPLO DE OFERTA ENCONTRADA ---")
        print(resultados[0]['description'][:500] + "...")