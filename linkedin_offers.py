from jobspy import scrape_jobs
import pandas as pd
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
import time
import random
from datetime import datetime

# --- CONFIGURACIÓN ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

# --- 1. MOTOR DE BÚSQUEDA (SOLO LINKEDIN) ---
def ejecutar_busqueda_avanzada(keywords, location, is_remote, job_type, hours_old, cantidad):
    """
    Busca estrictamente en LinkedIn.
    """
    print(f"   ➤ Scrapeando LinkedIn: {keywords} en {location}...")
    
    try:
        jobs_df = scrape_jobs(
            site_name=["linkedin"], # <--- SOLO LINKEDIN
            search_term=keywords,
            location=location,
            results_wanted=cantidad,
            hours_old=hours_old, 
            is_remote=is_remote,
            job_type=job_type,  
            linkedin_fetch_description=True
        )
        print(f"      ✅ Encontradas: {len(jobs_df)}")
        return jobs_df.to_dict(orient='records')
    except Exception as e:
        print(f"      ❌ Error scraping {location}: {e}")
        return []

# --- 2. FILTROS DE LIMPIEZA (PYTHON PURO) ---
def limpiar_y_deduplicar(todas_las_ofertas):
    ofertas_unicas = []
    vistos_ids = set() 
    vistos_nombres = set()

    print(f"\n🧹 Iniciando limpieza de {len(todas_las_ofertas)} ofertas crudas...")

    for oferta in todas_las_ofertas:
        url = oferta.get('job_url')
        titulo = str(oferta.get('title', '')).strip().lower()
        empresa = str(oferta.get('company', '')).strip().lower()
        key_nombre = f"{titulo}|{empresa}"

        if url and url in vistos_ids:
            continue
        
        if key_nombre in vistos_nombres:
            continue

        vistos_ids.add(url)
        vistos_nombres.add(key_nombre)
        ofertas_unicas.append(oferta)

    print(f"   📉 Reducido a {len(ofertas_unicas)} ofertas únicas.")
    return ofertas_unicas

def pre_filtro_palabras_clave(ofertas):
    ofertas_limpias = []
    red_flags = [
        "security clearance", "top secret", "us citizenship required", 
        "only us citizens", "must reside in the us", "must live in",
        "gmt-5 only" 
    ]
    
    print("🛡️ Ejecutando Pre-Filtro de palabras prohibidas...")
    for oferta in ofertas:
        desc = str(oferta.get('description', '')).lower()
        
        if any(flag in desc for flag in red_flags):
            continue
            
        ofertas_limpias.append(oferta)
        
    print(f"   ✅ Quedan {len(ofertas_limpias)} candidatas para la IA.")
    return ofertas_limpias

# --- 3. FILTRO DE INTELIGENCIA (GEMINI) ---
def analizar_viabilidad_oferta(oferta):
    descripcion = oferta.get('description', '')
    titulo = oferta.get('title', '')
    
    if not descripcion or len(descripcion) < 50: 
        return True 
        
    print(f"   🤖 IA Analizando: {titulo}...")
    
    prompt = f"""
    Eres un filtro de reclutamiento experto.
    CANDIDATO: Colombiano, busca Remoto (Latam/Worldwide) o Relocation.
    NO tiene visa USA/UE.
    
    TAREA: Responde JSON.
    {{
        "es_valida": boolean,
        "razon": "string corto"
    }}
    
    CRITERIOS EXCLUSIÓN:
    1. Requiere ciudadanía explícita.
    2. Residencia física obligatoria fuera de Colombia (sin relocation).
    
    OFERTA:
    {descripcion[:3000]}
    """
    
    try:
        response = model.generate_content(prompt)
        texto = response.text.replace("```json", "").replace("```", "").strip()
        analisis = json.loads(texto)
        
        if analisis.get("es_valida"):
            return True
        else:
            print(f"      ⛔ {analisis.get('razon')}")
            return False
    except:
        return True

# --- 4. FUNCIÓN DE GUARDADO ---
def sanitizar_datos(data):
    """
    Reemplaza valores NaN/Infinity de floats a None para que sea JSON válido.
    """
    if isinstance(data, list):
        return [sanitizar_datos(item) for item in data]
    elif isinstance(data, dict):
        return {k: sanitizar_datos(v) for k, v in data.items()}
    elif isinstance(data, float):
        if pd.isna(data): # Chequea NaN de pandas o math
            return None
    return data

def guardar_en_archivo(ofertas):
    if not ofertas:
        print("⚠️ No hay ofertas para guardar.")
        return

    # Limpiamos los datos antes de guardar
    ofertas_limpias = sanitizar_datos(ofertas)

    # ⚠️ AJUSTA TU RUTA AQUÍ SI ES NECESARIO
    ruta_base = "/Users/josemiguelrozobaez/documents/develop/agent-offers/"
    os.makedirs(ruta_base, exist_ok=True)
    
    nombre_archivo = datetime.now().strftime("%d%b%H%M") + ".json"
    ruta_completa = os.path.join(ruta_base, nombre_archivo)
    
    try:
        with open(ruta_completa, 'w', encoding='utf-8') as f:
            json.dump(ofertas_limpias, f, indent=4, ensure_ascii=False)
        print(f"\n💾 ARCHIVO GUARDADO EXITOSAMENTE:")
        print(f"   📂 {ruta_completa}")
    except Exception as e:
        print(f"❌ Error guardando archivo: {e}")

# --- 5. ORQUESTADOR PRINCIPAL ---
def buscar_ofertas_desde_json(filtros_json):
    print("\n🚀 INICIANDO PROCESO BATCH (SOLO LINKEDIN)")
    
    # IMPORTAR GESTOR DE HISTORIAL
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from utils import JobHistoryManager
    history = JobHistoryManager()

    keywords = filtros_json.get("keywords", "")
    locations = filtros_json.get("target_locations", ["Remote"])
    is_remote = filtros_json.get("is_remote", True)
    job_type = filtros_json.get("job_type", "fulltime")
    hours_old = filtros_json.get("hours_old", 72) 
    cantidad = filtros_json.get("results_count", 30) 
    
    todas_las_ofertas_crudas = []
    
    # 1. COSECHA
    for i, loc in enumerate(locations):
        resultados = ejecutar_busqueda_avanzada(
            keywords, loc, is_remote, job_type, hours_old, cantidad
        )
        todas_las_ofertas_crudas.extend(resultados)
        
        if i < len(locations) - 1:
            time.sleep(random.uniform(5, 8))

    if not todas_las_ofertas_crudas:
        print("❌ No se encontraron ofertas crudas.")
        return []

    # 2. LIMPIEZA & PRE-FILTRO
    ofertas_unicas = limpiar_y_deduplicar(todas_las_ofertas_crudas)
    ofertas_candidatas = pre_filtro_palabras_clave(ofertas_unicas)
    
    # --- DEDUPLICACIÓN HISTÓRICA ---
    ofertas_nuevas = history.filter_new_offers(ofertas_candidatas)
    print(f"   🤏 De {len(ofertas_candidatas)} candidatas, {len(ofertas_nuevas)} son NUEVAS en el historial.")
    
    if not ofertas_nuevas:
        print("🤷‍♂️ No hay ofertas nuevas por ahora.")
        return []

    # 3. ANÁLISIS IA (Solo sobre las nuevas)
    print(f"\n🧠 Iniciando Análisis IA sobre {len(ofertas_nuevas)} ofertas...")
    ofertas_finales = []
    
    for oferta in ofertas_nuevas:
        es_viable = analizar_viabilidad_oferta(oferta)
        if es_viable:
            ofertas_finales.append(oferta)
        time.sleep(2) 

    # 4. GUARDADO FINAL
    print(f"\n🎉 PROCESO TERMINADO: {len(ofertas_finales)} ofertas válidas.")
    
    # Guardamos en el historial global
    history.save_offers(ofertas_finales)
    
    return ofertas_finales

# --- TEST ---
if __name__ == "__main__":
    filtros_test = {
        "keywords": "Senior Full Stack Python",
        # NOTA: Cambié "LATAM" por "Worldwide" o países específicos
        # porque LinkedIn a veces no reconoce "LATAM" como ubicación válida en el scraper.
        "target_locations": ["United States", "Remote", "Worldwide"], 
        "is_remote": True,
        "job_type": "fulltime",
        "results_count": 20 
    }
    buscar_ofertas_desde_json(filtros_test)