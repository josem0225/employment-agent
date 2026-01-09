import os
import sys
import json
from read_cv import procesar_cv, CV_FILE_PATH
from linkedin_offers import buscar_ofertas_desde_json
# INTEGRACIÓN: Importamos el módulo de Hacker News
sys.path.append(os.path.dirname(os.path.abspath(__file__))) # Asegurar path
from importlib import import_module
hacker_news = import_module("hacker-news")
buscar_ofertas_hackernews = hacker_news.buscar_ofertas_hackernews
wwr = import_module("wwr")
buscar_ofertas_wwr = wwr.buscar_ofertas_wwr

def main():
    print("🚀 INICIANDO AGENTE DE BÚSQUEDA DE EMPLEO v1.0")
    print("=============================================")
    
    # 1. Obtener filtros del CV
    print("\n[Paso 1] Analizando CV para definir estrategia...")
    if not os.path.exists(CV_FILE_PATH):
         print(f"❌ Error: No se encuentra el archivo de CV en: {CV_FILE_PATH}")
         return

    filtros = procesar_cv(CV_FILE_PATH)
    
    if not filtros:
        print("❌ Falló el análisis del CV. Abortando.")
        return

    print("\n✅ Filtros generados con éxito:")
    print(json.dumps(filtros, indent=2, ensure_ascii=False))

    # 2. Buscar ofertas (SELECCIONAR MOTOR)
    ofertas = []
    
    # --- MOTOR 1: LINKEDIN (COMENTADO POR AHORA) ---
    # print("\n[Paso 2] Buscando ofertas en LinkedIn...")
    # ofertas_linkedin = buscar_ofertas_desde_json(filtros)
    # ofertas.extend(ofertas_linkedin)
    
    # --- MOTOR 2: HACKER NEWS ---
    print("\n[Paso 2b] Buscando ofertas en Hacker News...")
    ofertas_hn = buscar_ofertas_hackernews(filtros)
    ofertas.extend(ofertas_hn)
    
    # --- MOTOR 3: WE WORK REMOTELY ---
    print("\n[Paso 2c] Buscando ofertas en We Work Remotely...")
    ofertas_wwr = buscar_ofertas_wwr(filtros)
    ofertas.extend(ofertas_wwr)
    
    print("\n\n🎉 RESUMEN FINAL")
    print("=============================================")
    print(f"Total de ofertas encontradas: {len(ofertas)}")
    
    for i, oferta in enumerate(ofertas, 1):
        titulo = oferta.get('title', 'Sin título')
        empresa = oferta.get('company', 'Empresa confidencial')
        ubicacion = oferta.get('location', 'Ubicación desconocida')
        url = oferta.get('job_url', '#')
        
        print(f"\n{i}. {titulo}")
        print(f"   🏢 {empresa} | 📍 {ubicacion}")
        print(f"   🔗 {url}")

if __name__ == "__main__":
    import sys
    main()
