# motor_cv.py
import os
import json
import google.generativeai as genai
from pypdf import PdfReader
import time
import hashlib
from dotenv import load_dotenv

# Configuración inicial (Solo carga si se ejecuta este archivo, o se re-configura al importar)
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    # Usamos el modelo rápido y capaz que ya validamos
    model = genai.GenerativeModel('gemini-flash-latest')

CV_FILE_PATH = r"/Users/josemiguelrozobaez/downloads/Cristotech.pdf"
# CV_FILE_PATH = r"/Users/josemiguelrozobaez/downloads/cvJose.pdf"


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
    REGLAS PARA KEYWORDS:
    1. "role_synonyms" (IDENTIDAD COMPLETA): Todas las formas posibles en que el rol del candidato aparece en ofertas de empleo reales.
       - Incluye: título exacto, abreviaciones, variantes sénior/junior/lead, títulos alternativos del mercado.
       - Piensa como reclutador: ¿cómo publican este rol en LinkedIn, HN, RemoteOK, Indeed?
       - Para Product Manager: ["Product Manager", "PM", "TPM", "Product Owner", "PO", "Head of Product", "VP of Product", "Director of Product", "Group PM", "GPM", "APM", "Product Lead", "Product Strategist"]
       - Para Backend Dev: ["Backend Developer", "Backend Engineer", "Software Engineer", "SWE", "API Developer", "Full Stack Developer", "Node Developer", "Python Developer", "Software Developer", "Dev"]
       - Para Data Analyst: ["Data Analyst", "Business Analyst", "BI Analyst", "Analytics Engineer", "Data Scientist", "Reporting Analyst", "Insights Analyst", "Data Engineer"]
       - Para Scrum Master: ["Scrum Master", "Agile Coach", "Delivery Manager", "Agile Lead", "Agile Facilitator", "Iteration Manager", "Release Train Engineer"]
       GENERA AL MENOS 12-15 VARIANTES para el rol específico del CV que estás analizando.
    2. "role_keywords": Subset de 3-5 variantes principales (las más comunes en el mercado).
    3. "keyword_list" (HERRAMIENTAS): Skills técnicas del candidato. Ej: "Jira", "SQL", "Python".
    4. "keywords_are_hard_filter": true si el stack técnico ES la identidad del rol (Dev, Data Engineer, Designer).
       false si las herramientas son secundarias al rol (PM, Scrum Master, Manager, Coach).
       Regla práctica: si cambiar de Python a Java cambia fundamentalmente el perfil -> true. Si no -> false.

    FORMATO JSON ESPERADO:
    {{
        "keywords": "String con la query booleana optimizada (mezcla de roles y skills clave).",
        "role_synonyms": ["Lista de 12-15 variantes del rol detectado, cubriendo todas las formas en que aparece en job postings"],
        "role_keywords": ["Lista de 3-5 variantes principales del rol (subset de role_synonyms)"],
        "keyword_list": ["Lista de 5-7 skills/tecnologías para filtrado secundario. Ej: 'Jira', 'SQL', 'Python'"],
        "keywords_are_hard_filter": false,

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

    # Configuración de Seguridad para evitar bloqueos por falsos positivos en CVs
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt, safety_settings=safety_settings)
            
            # Verificación robusta antes de acceder a .text
            if not response.parts:
                print(f"⚠️ Alerta: Gemini devolvió una respuesta vacía (Intento {attempt+1}). Finish Reason: {response.candidates[0].finish_reason if response.candidates else 'Unknown'}")
                # Si falló por seguridad, a veces ayuda reintentar o imprimir feedback
                if response.prompt_feedback:
                    print(f"   Prompt Feedback: {response.prompt_feedback}")
                continue

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
                # No retornamos {} inmediatamente, intentamos de nuevo si quedan intentos
                if attempt == max_retries - 1:
                    return {}
    
    print("❌ Se agotaron los reintentos. No se pudo analizar el CV.")
    return {}

def calculate_file_hash(filepath):
    """Calcula el MD5 del archivo para detectar cambios."""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def procesar_cv(ruta_cv):
    """
    Función principal para orquestar la lectura y análisis del CV.
    Utiliza caché para evitar llamadas redundantes a la API.
    """
    if not os.path.exists(ruta_cv):
        print(f"⚠️ No encontré '{ruta_cv}'.")
        return None

    # --- 1. Lógica de Caché ---
    cache_dir = "/Users/josemiguelrozobaez/documents/develop/agent-offers"
    cache_file = os.path.join(cache_dir, "cv_analysis_cache.json")
    
    current_hash = calculate_file_hash(ruta_cv)
    filtros_cachados = None
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                if cache_data.get("file_hash") == current_hash:
                    print("⚡ CACHÉ DETECTADO: El CV no ha cambiado. Usando filtros guardados.")
                    return cache_data.get("filters")
        except Exception as e:
            print(f"⚠️ Error leyendo caché: {e}")

    # --- 2. Análisis Real (Si no hay caché válido) ---
    print(f"📖 Leyendo PDF: {ruta_cv}...")
    texto = extraer_texto_pdf(ruta_cv)
    
    if not texto:
        print("❌ No se pudo extraer texto del PDF.")
        return None

    print(f"✅ Texto extraído ({len(texto)} caracteres).")
    print("🧠 Enviando a Gemini para perfilado universal...")
    
    parametros = analizar_cv_para_busqueda(texto)
    
    # --- 3. Guardar en Caché ---
    if parametros:
        try:
            os.makedirs(cache_dir, exist_ok=True)
            cache_payload = {
                "file_hash": current_hash,
                "filters": parametros,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_payload, f, indent=4, ensure_ascii=False)
            print(f"💾 Filtros guardados en caché: {cache_file}")
        except Exception as e:
             print(f"⚠️ No se pudo guardar caché: {e}")
             
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