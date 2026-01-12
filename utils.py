import json
import os
import re
from datetime import datetime

# --- FILTROS DE UBICACIÓN STRICTOS (ZERO-TOKEN) ---
def filtrar_por_ubicacion_estricta(ofertas):
    """
    Filtra ofertas que requieren residencia física específica (USA, EU, UK)
    a menos que mencionen explícitamente LATAM/Worldwide.
    """
    print("🌍 Validando restricciones geográficas estrictas...")
    
    # PATRONES DE EXCLUSIÓN (RED FLAGS)
    # Si aparecen estos, es probable que no sirvan
    patrones_red = [
        r"\bUS only\b", r"\bUSA only\b", r"\bUnited States only\b",
        r"\bNorth America only\b", r"\bEurope only\b", r"\bUK only\b",
        r"\bCanada only\b", r"\bEU only\b", r"\bUS citizen\b",
        r"\bcitizenship\b", r"\bmust reside in\b", r"\bmust be located in\b",
        r"\bU\.S\.\b", r"\bUnited States\b" # Cuidado con este, puede ser la empresa
    ]
    
    # PATRONES DE SALVACIÓN (GREEN FLAGS)
    # Si aparecen estos, ignoramos los Red Flags (ej: "US Company hiring Worldwide")
    patrones_green = [
        r"\bLATAM\b", r"\bLatin America\b", r"\bSouth America\b",
        r"\bWorldwide\b", r"\bGlobal\b", r"\bAnywhere\b",
        r"\bRemote\s?Worker\b", r"\bRemote\s?Global\b"
    ]

    ofertas_validas = []
    descartadas = 0

    for oferta in ofertas:
        # Combinamos campos clave para análisis
        titulo = str(oferta.get('title', '')).lower()
        ubicacion = str(oferta.get('location', '')).lower()
        # Descripción corta si existe (a veces el titulo lo es todo)
        # Nota: No usamos descripción completa aquí para ser rápidos y no filtrar de más por menciones circunstanciales.
        texto_analisis = f"{titulo} {ubicacion}"
        
        es_segura = False
        
        # 1. Chequeo Green Flags (Prioridad)
        for p in patrones_green:
            if re.search(p, texto_analisis, re.IGNORECASE):
                es_segura = True
                break
        
        if es_segura:
            ofertas_validas.append(oferta)
            continue

        # 2. Chequeo Red Flags
        tiene_red_flag = False
        for p in patrones_red:
            if re.search(p, texto_analisis, re.IGNORECASE):
                tiene_red_flag = True
                # print(f"   🗑️ Descartada por geo: {titulo} ({ubicacion})") 
                break
        
        if tiene_red_flag:
            descartadas += 1
            continue

        # Si no es Green ni Red, pasa (Permisivo por defecto)
        ofertas_validas.append(oferta)

    print(f"   🛡️ Filtro Geo: {len(ofertas)} -> {len(ofertas_validas)} ({descartadas} descartadas por restricción país)")
    return ofertas_validas

class JobHistoryManager:
    def __init__(self, history_file_path=None):
        if history_file_path is None:
            # Ruta por defecto
            base_dir = "/Users/josemiguelrozobaez/documents/develop/agent-offers"
            os.makedirs(base_dir, exist_ok=True)
            self.history_file = os.path.join(base_dir, "offers_history.json")
        else:
            self.history_file = history_file_path
            
        self.seen_urls = set()
        self._load_history()

    def _load_history(self):
        """Carga los URLs existentes para chequeo rápido (O(1))."""
        if not os.path.exists(self.history_file):
            return

        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
                for offer in history:
                    url = offer.get('job_url')
                    if url:
                        self.seen_urls.add(url)
            print(f"📚 Historia cargada: {len(self.seen_urls)} ofertas previas.")
        except Exception as e:
            print(f"⚠️ Error cargando historia: {e} (Se creará un archivo nuevo)")

    def filter_new_offers(self, offers_list):
        """Retorna solo las ofertas que NO están en el historial."""
        new_offers = []
        for offer in offers_list:
            url = offer.get('job_url')
            if url and url not in self.seen_urls:
                new_offers.append(offer)
                self.seen_urls.add(url) # Marcamos como vista para esta misma ejecución
        return new_offers

    def save_offers(self, new_offers):
        """Guarda las nuevas ofertas en el archivo maestro (Append logic)."""
        if not new_offers:
            return

        # 1. Leemos todo el archivo actual (Para JSON standard es necesario)
        # Ojo: Con millones de registros esto sería lento, pero para <50k está ok.
        current_history = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    current_history = json.load(f)
            except:
                current_history = []
        
        # 2. Agregamos lo nuevo
        current_history.extend(new_offers)
        
        # 3. Reescribimos
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(current_history, f, indent=4, ensure_ascii=False)
            print(f"💾 {len(new_offers)} nuevas ofertas guardadas en el historial maestro.")
        except Exception as e:
            print(f"❌ Error guardando historial: {e}")
