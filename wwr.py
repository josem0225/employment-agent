import feedparser
import time
import re
import os
import sys
import json
import requests
from datetime import datetime

# --- CONFIGURACIÓN DE FUENTES WWR ---
# Feeds organizados por tipo de rol. Se seleccionan dinámicamente según el CV.
WWR_FEEDS_BY_ROLE = {
    "tech": [
        "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
        "https://weworkremotely.com/categories/remote-qa-jobs.rss",
    ],
    "product": [
        "https://weworkremotely.com/categories/remote-product-jobs.rss",
        "https://weworkremotely.com/categories/remote-management-business-jobs.rss",
    ],
    "data": [
        "https://weworkremotely.com/categories/remote-data-science-jobs.rss",
        "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
    ],
    "design": [
        "https://weworkremotely.com/categories/remote-design-jobs.rss",
        "https://weworkremotely.com/categories/remote-product-jobs.rss",
    ],
    "management": [
        "https://weworkremotely.com/categories/remote-management-business-jobs.rss",
        "https://weworkremotely.com/categories/remote-product-jobs.rss",
    ],
    "other": [
        "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-product-jobs.rss",
        "https://weworkremotely.com/categories/remote-management-business-jobs.rss",
        "https://weworkremotely.com/categories/remote-data-science-jobs.rss",
    ],
}

def limpiar_html(texto_html):
    """Limpia etiquetas HTML simples de la descripción para el análisis."""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', texto_html)

def buscar_ofertas_wwr(filtros_json):
    """
    Consume los RSS oficiales de WeWorkRemotely.
    Selecciona los feeds dinámicamente según el tipo de rol del CV.
    Funciona para cualquier perfil: dev, PM, data, design, management, etc.
    """
    print("\n📡 INICIANDO MOTOR WE WORK REMOTELY (Vía RSS)...")

    # Selección dinámica de feeds según el tipo de rol detectado por Gemini
    role_type = filtros_json.get("role_type", "other").lower()
    wwr_feeds = WWR_FEEDS_BY_ROLE.get(role_type, WWR_FEEDS_BY_ROLE["other"])
    print(f"   🎯 Rol detectado: '{role_type}' → {len(wwr_feeds)} feed(s) seleccionado(s).")

    # Role synonyms: todas las variantes del rol para matching en título/descripción
    role_variants = [v.lower() for v in filtros_json.get("role_synonyms", filtros_json.get("role_keywords", []))]

    # Keywords técnicas: solo obligatorias si el stack ES la identidad del rol (dev, data)
    usar_keywords_como_filtro = filtros_json.get("keywords_are_hard_filter", False)
    lista_keywords = filtros_json.get("keyword_list", [])
    if not lista_keywords:
        keywords_str = filtros_json.get("keywords", "").lower()
        lista_keywords = [k.strip() for k in keywords_str.replace("(", "").replace(")", "").replace("OR", "").replace("AND", "").split() if len(k) > 2]
    lista_keywords = [k.lower() for k in lista_keywords]

    ofertas_encontradas = []

    for url_feed in wwr_feeds:
        print(f"   🔌 Conectando a feed: {url_feed.split('/')[-1]}...")

        try:
            feed = feedparser.parse(url_feed)

            if feed.status != 200 and feed.status != 301:
                print(f"      ⚠️ Error conectando al feed (Status {feed.status})")
                continue

            print(f"      📥 Descargadas {len(feed.entries)} entradas.")

            for entry in feed.entries:
                titulo = entry.title
                empresa = entry.get('author', 'Unknown Company')
                descripcion = entry.summary
                link = entry.link
                publicado = entry.published

                texto_completo = (titulo + " " + descripcion).lower()

                # Filtro de ROL: si tenemos sinónimos, al menos uno debe aparecer
                if role_variants:
                    if not any(v in texto_completo for v in role_variants):
                        continue

                # Filtro de KEYWORDS: solo si el stack técnico es identidad del rol
                if usar_keywords_como_filtro and lista_keywords:
                    if not any(k in texto_completo for k in lista_keywords):
                        continue

                ofertas_encontradas.append({
                    "title": titulo,
                    "company": empresa,
                    "location": "Remote (WWR)",
                    "description": limpiar_html(descripcion),
                    "job_url": link,
                    "source": "WeWorkRemotely",
                    "date": publicado
                })

        except Exception as e:
            print(f"      ❌ Error procesando feed: {e}")

    print(f"   ✅ Se encontraron {len(ofertas_encontradas)} ofertas potenciales en WWR.")
    
    # 3. Deduplicación Histórica y Guardado
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from utils import JobHistoryManager, filtrar_por_ubicacion_estricta
    history = JobHistoryManager()
    
    # NUEVO: Filtro Estricto de Ubicación
    ofertas_geo_validas = filtrar_por_ubicacion_estricta(ofertas_encontradas)
    
    ofertas_nuevas = history.filter_new_offers(ofertas_geo_validas)
    print(f"   🤏 De {len(ofertas_geo_validas)} candidatas geo-validas, {len(ofertas_nuevas)} son NUEVAS en el historial.")
    
    if ofertas_nuevas:
        history.save_offers(ofertas_nuevas)
    else:
        print("🤷‍♂️ No hay ofertas nuevas de WWR.")
    
    return ofertas_nuevas

def guardar_en_archivo(ofertas):
    if not ofertas:
        return

    # Ruta consistente
    ruta_base = "/Users/josemiguelrozobaez/documents/develop/agent-offers/"
    os.makedirs(ruta_base, exist_ok=True)
    
    # Prefijo WWR
    nombre_archivo = "WWR_" + datetime.now().strftime("%d%b%H%M") + ".json"
    ruta_completa = os.path.join(ruta_base, nombre_archivo)
    
    try:
        with open(ruta_completa, 'w', encoding='utf-8') as f:
            json.dump(ofertas, f, indent=4, ensure_ascii=False)
        print(f"\n💾 ARCHIVO WWR GUARDADO: {ruta_completa}")
    except Exception as e:
        print(f"❌ Error guardando WWR: {e}")

# --- TEST ---
if __name__ == "__main__":
    filtros_test = {
        "keywords": "Python", 
    }
    resultados = buscar_ofertas_wwr(filtros_test)
    
    if resultados:
        print("\n--- EJEMPLO ---")
        print(f"Título: {resultados[0]['title']}")
        print(f"Empresa: {resultados[0]['company']}")
        print(f"Link: {resultados[0]['job_url']}")