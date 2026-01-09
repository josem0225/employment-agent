import feedparser
import time
import re
import os
import json
from datetime import datetime

# --- CONFIGURACIÓN DE FUENTES WWR ---
# WWR divide sus ofertas por categorías en RSS separados.
# Seleccionamos las que encajan con tu perfil (Backend, Full Stack, DevOps)
WWR_FEEDS = [
    "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss" # Por tu background en Linux/Servidores
]

def limpiar_html(texto_html):
    """Limpia etiquetas HTML simples de la descripción para el análisis."""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', texto_html)

def buscar_ofertas_wwr(filtros_json):
    """
    Consume los RSS oficiales de WeWorkRemotely.
    No requiere selenium ni proxies.
    """
    print("\n📡 INICIANDO MOTOR WE WORK REMOTELY (Vía RSS)...")
    
    # ADAPTER: Usamos la lista limpia si existe (Mejor práctica)
    lista_keywords = filtros_json.get("keyword_list", [])
    
    # Fallback: Si no hay lista, intentamos limpiar el string antiguo
    if not lista_keywords:
        keywords = filtros_json.get("keywords", "").lower()
        lista_keywords = [k.strip() for k in keywords.replace("(", "").replace(")", "").replace("OR", "").replace("AND", "").split() if len(k) > 2]
    
    ofertas_encontradas = []

    for url_feed in WWR_FEEDS:
        print(f"   🔌 Conectando a feed: {url_feed.split('/')[-1]}...")
        
        try:
            # feedparser se encarga de descargar y parsear el XML
            feed = feedparser.parse(url_feed)
            
            if feed.status != 200 and feed.status != 301:
                print(f"      ⚠️ Error conectando al feed (Status {feed.status})")
                continue
                
            print(f"      📥 Descargadas {len(feed.entries)} entradas.")

            for entry in feed.entries:
                titulo = entry.title
                empresa = entry.get('author', 'Unknown Company') # WWR pone la empresa en 'author'
                descripcion = entry.summary # En RSS 'summary' o 'description' es el cuerpo
                link = entry.link
                publicado = entry.published
                
                # --- FILTRO RÁPIDO (Python) ---
                # Como WWR es 100% remoto, filtramos por Tecnología.
                texto_completo = (titulo + " " + descripcion).lower()
                
                # Si definiste keywords, verificamos que tenga al menos una
                if lista_keywords:
                    if not any(k in texto_completo for k in lista_keywords):
                        continue
                
                # Empaquetamos para que sea idéntico a los otros motores
                ofertas_encontradas.append({
                    "title": titulo,
                    "company": empresa,
                    "location": "Remote (WWR)", # WWR es remoto por defecto
                    "description": limpiar_html(descripcion),
                    "job_url": link,
                    "source": "WeWorkRemotely",
                    "date": publicado
                })
                
        except Exception as e:
            print(f"      ❌ Error procesando feed: {e}")

    print(f"   ✅ Se encontraron {len(ofertas_encontradas)} ofertas potenciales en WWR.")
    
    # Guardado automático
    guardar_en_archivo(ofertas_encontradas)
    
    return ofertas_encontradas

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