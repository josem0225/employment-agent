
import os
import json
from read_cv import procesar_cv, CV_FILE_PATH
from linkedin_offers import buscar_ofertas_desde_json

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

    # 2. Buscar ofertas en LinkedIn
    print("\n[Paso 2] Buscando ofertas en LinkedIn...")
    ofertas = buscar_ofertas_desde_json(filtros)
    
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
    main()
