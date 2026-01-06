from jobspy import scrape_jobs
import os
import feedparser
import google.generativeai as genai
from dotenv import load_dotenv
from jobspy import scrape_jobs
import pandas as pd

# --- PASO 1: CONFIGURACIÓN INICIAL ---
# Cargamos el token del archivo .env
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ ERROR CRÍTICO: No encontré la GOOGLE_API_KEY en tu archivo .env")
    exit() # Detiene el script aquí si no hay llave

# Configuramos Gemini
print("✅ Llave encontrada. Conectando con Gemini...")
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-flash-latest')

# --- PASO 2: DESCARGAR OFERTAS ---
RSS_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
print(f"📡 Descargando ofertas de {RSS_URL}...")

feed = feedparser.parse(RSS_URL)

if feed.bozo:
    print("❌ Error conectando al RSS.")
    exit()

print(f"✅ Descarga exitosa. Hay {len(feed.entries)} ofertas disponibles.")
print("--- 🧠 INICIANDO ANÁLISIS CON IA (Solo las primeras 3) ---")

# --- PASO 3: BUCLE DE ANÁLISIS ---
# Recorremos solo las primeras 3 ofertas para no saturar la pantalla
for i, oferta in enumerate(feed.entries[:1]):
    titulo = oferta.title
    # A veces la descripción viene en 'summary' o 'description', tomamos la que haya
    contenido = oferta.get('summary', '') or oferta.get('description', '')

    print(f"\n🔎 [{i+1}] Analizando oferta: {titulo}")
    
    # Preparamos el mensaje para Gemini
    prompt = f"""
    Actúa como un reclutador experto. Lee la siguiente oferta de trabajo y extrae SOLO las tecnologías requeridas (Lenguajes, Frameworks, Cloud).
    Devuelve la respuesta como una lista simple separada por comas. No uses Markdown ni introducciones.
    
    OFERTA:
    Título: {titulo}
    Descripción: {contenido}
    """

    try:
        # Aquí enviamos la data a Google
        response = model.generate_content(prompt)
        
        # Mostramos el resultado
        print(f"🤖 STACK DETECTADO: {response.text.strip()}")
        
    except Exception as e:
        print(f"❌ Error con Gemini en esta oferta: {e}")

    print("-" * 50)