# motor_cv.py
import os
import json
import google.generativeai as genai
from pypdf import PdfReader
from dotenv import load_dotenv

# Configuración inicial (Solo carga si se ejecuta este archivo, o se re-configura al importar)
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    # Usamos el modelo rápido y capaz que ya validamos
    model = genai.GenerativeModel('gemini-flash-latest')

CV_FILE_PATH = r"/Users/josemiguelrozobaez/downloads/cvJose.pdf"

def extraer_texto_pdf(ruta_pdf):
    """
    Lee un archivo PDF y devuelve todo su contenido como un string de texto plano.
    """
    if not os.path.exists(ruta_pdf):
        return None

    try:
        reader = PdfReader(ruta_pdf)
        texto_completo = ""
        for page in reader.pages:
            texto_completo += page.extract_text() + "\n"
        return texto_completo
    except Exception as e:
        print(f"❌ Error leyendo el PDF: {e}")
        return None

def analizar_cv_para_busqueda(texto_cv):
    """
    Recibe el texto crudo del CV y usa IA para definir los MEJORES parámetros de búsqueda.
    El prompt es UNIVERSAL (funciona para cualquier carrera).
    """
    
    # --- EL PROMPT UNIVERSAL ---
    # Este es el secreto. Le pedimos que actúe como Headhunter y traduzca
    # "Experiencia" en "Keywords de Búsqueda".
    prompt = f"""
    Actúa como un Headhunter Global experto en movilidad de talento internacional.
    Analiza el siguiente CV y define la estrategia de búsqueda más agresiva para conseguir trabajo REMOTO o con Relocation en mercados de moneda fuerte (USD/EUR).

    TEXTO DEL CV:
    {texto_cv[:8000]}

    TAREA:
    Genera un objeto JSON con los filtros óptimos.
    IMPORTANTE: No te limites a la ubicación actual del candidato. Tu objetivo es exportar este talento.

    REGLAS PARA LOCACIONES (TARGET LOCATIONS):
    1. Si el perfil es TECH/DIGITAL: Debes incluir SIEMPRE "United States", "Canada" y "Remote".
    2. Si el perfil habla inglés: Prioriza países angloparlantes.
    3. Si el perfil habla solo español: Prioriza "Spain", "LATAM" y "Remote".
    4. El objetivo es encontrar empresas dispuestas a contratar talento de LATAM/Extranjero.
    5. NO agregues keywords de Relocation en la query principal (lo filtraremos despues).

    FORMATO JSON ESPERADO:
    {{
        "keywords": "String con la query booleana optimizada. NO uses terminos como Seniority en la query si reduce mucho los resultados. Hazla amplia pero relevante.",
        
        "target_locations": [
            "Lista de strings con las 10 mejores ubicaciones para buscar. LATAM SIEMPRE DEBE SER LA PRIMERA OPCION POR FAVOR",
            "Ejemplo 1: 'Remote'",
            "Ejemplo 2: 'United States' (Para buscar empresas de USA que contraten remoto)",
            "Ejemplo 3: 'European Union'",
            "Ejemplo 4: 'Worldwide'",
            "Ejemplo 5: 'LATAM'"
        ],
        
        "is_remote": true, 
        "job_type": "fulltime",
        "experience_level": "Seniority inferido (ej: Senior, Mid-Senior)",
        "hours_old": 72, 
        "results_count": 50
    }}

    Devuelve SOLO el JSON.
    """

    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            # Limpieza de bloques de código markdown si Gemini los pone
            texto_limpio = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(texto_limpio)
        except Exception as e:
            if "429" in str(e):
                wait_time = (attempt + 1) * 20 # 20s, 40s, 60s
                print(f"⚠️ Quota excedida (429). Reintentando en {wait_time}s... (Intento {attempt+1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"❌ Error analizando con IA: {e}")
                return {}
    
    print("❌ Se agotaron los reintentos. No se pudo analizar el CV.")
    return {}

def procesar_cv(ruta_cv):
    """
    Función principal para orquestar la lectura y análisis del CV.
    Retorna el diccionario con los filtros de búsqueda o None si falla.
    """
    if not os.path.exists(ruta_cv):
        print(f"⚠️ No encontré '{ruta_cv}'.")
        return None

    print(f"📖 Leyendo PDF: {ruta_cv}...")
    texto = extraer_texto_pdf(ruta_cv)
    
    if not texto:
        print("❌ No se pudo extraer texto del PDF.")
        return None

    print(f"✅ Texto extraído ({len(texto)} caracteres).")
    print("🧠 Enviando a Gemini para perfilado universal...")
    
    parametros = analizar_cv_para_busqueda(texto)
    return parametros

# --- BLOQUE DE PRUEBA (Para correrlo solo) ---
if __name__ == "__main__":
    print("🧪 MODO PRUEBA: Analizando CV local...")
    
    # ⚠️ CAMBIA ESTO POR LA RUTA REAL DE TU CV PARA PROBAR
    # Puedes poner el path absoluto o relativo. Ej: "mi_cv.pdf"
    # RUTA_CV_HARDCODED = "cv_jose.pdf" 
    
    parametros = procesar_cv(CV_FILE_PATH)
    
    if parametros:
        print("\n--- 🎯 RESULTADO: PARÁMETROS DE BÚSQUEDA ---")
        print(json.dumps(parametros, indent=4, ensure_ascii=False))
        
        print("\n✅ Estos datos son los que pasaremos al motor_linkedin.py")