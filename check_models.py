import os
import google.generativeai as genai
from dotenv import load_dotenv

# 1. Cargar la llave
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ Error: No se encontró la API KEY en el .env")
    exit()

print(f"🔑 Llave encontrada (termina en ...{api_key[-5:]})")
print("📡 Conectando con Google para listar modelos disponibles...")

try:
    genai.configure(api_key=api_key)
     
    # 2. Listar modelos
    encontrados = False
    for m in genai.list_models():
        # Filtramos solo los que sirven para generar texto (chat)
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ MODELO DISPONIBLE: {m.name}")
            encontrados = True
            
    if not encontrados:
        print("⚠️ Conectamos, pero no aparecieron modelos con capacidad 'generateContent'.")
        print("Posible causa: Tu API Key no tiene permisos o la región está restringida.")

except Exception as e:
    print(f"❌ Error fatal conectando: {e}")