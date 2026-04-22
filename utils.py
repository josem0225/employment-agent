import json
import os
import re
from datetime import datetime, date

# --- FILTROS DE UBICACIÓN STRICTOS (ZERO-TOKEN) ---
def filtrar_por_ubicacion_estricta(ofertas):
    """
    Filtra ofertas que requieren residencia física específica (USA, EU, UK)
    a menos que mencionen explícitamente LATAM/Worldwide.
    """
    print("🌍 Validando restricciones geográficas estrictas...")
    
    # PATRONES DE EXCLUSIÓN (RED FLAGS)
    # Solo patrones que indican RESTRICCIÓN EXPLÍCITA de ubicación o ciudadanía.
    # Mencionar un país NO es red flag — una empresa de USA puede contratar remoto global.
    patrones_red = [
        r"\bUS only\b", r"\bUSA only\b", r"\bUnited States only\b",
        r"\bNorth America only\b", r"\bEurope only\b", r"\bUK only\b",
        r"\bCanada only\b", r"\bEU only\b",
        r"\bUS citizen(ship)?\b", r"\bu\.s\. citizen(ship)?\b",
        r"\bcitizenship required\b",
        r"\bmust reside in\b", r"\bmust be located in\b", r"\bmust be based in\b",
        r"\bauthorized to work in\b", r"\beligible to work in\b",
        r"\bwork authorization required\b",
        r"\bno visa sponsorship\b", r"\bvisa sponsorship (not|no longer) available\b",
    ]

    # PATRONES DE SALVACIÓN (GREEN FLAGS)
    # Si aparecen estos, la oferta claramente está abierta a candidatos internacionales.
    patrones_green = [
        r"\bLATAM\b", r"\bLatin America\b", r"\bSouth America\b",
        r"\bWorldwide\b", r"\bGlobal\b", r"\bAnywhere\b",
        r"\bRemote\s?Worker\b", r"\bRemote\s?Global\b",
        r"\bopen to international\b", r"\binternational candidates\b",
        r"\bvisa sponsorship (available|provided|offered)\b",
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

# --- ENCODER PERSONALIZADO PARA JSON ---
class CustomJSONEncoder(json.JSONEncoder):
    """
    Encoder robusto que maneja:
    - Fechas (datetime/date) -> ISO format string
    - NaNs / Infinite -> null (Estándar JSON)
    - Sets -> Listas
    """
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, set):
            return list(obj)
        # Pandas NaNs y NaTs
        try:
            import pandas as pd
            if pd.isna(obj):
                return None
        except ImportError:
            pass
            
        # Standard float NaN handling handled by json.dump usually via allow_nan=True but 
        # we want strict JSON (null) not NaN
        if isinstance(obj, float):
             import math
             if math.isnan(obj) or math.isinf(obj):
                 return None
                 
        return super().default(obj)

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
                # Handle empty file or bad JSON
                try:
                    history = json.load(f)
                except json.JSONDecodeError:
                    history = []
                
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
        """
        Guarda las nuevas ofertas en el archivo maestro de forma ATÓMICA.
        Evita corrupciones si se interrumpe la escritura.
        """
        if not new_offers:
            return

        # 1. Leemos todo el archivo actual
        current_history = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    current_history = json.load(f)
            except:
                current_history = []
        
        # 2. Agregamos lo nuevo
        current_history.extend(new_offers)
        
        # 3. Escritura Atómica (Write .tmp -> Rename)
        temp_file = self.history_file + ".tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                # Usamos el Encoder personalizado para sanar NaNs y Fechas
                json.dump(current_history, f, indent=4, ensure_ascii=False, cls=CustomJSONEncoder)
            
            os.replace(temp_file, self.history_file)
            print(f"💾 {len(new_offers)} nuevas ofertas guardadas SEGURO (Total: {len(current_history)}).")
        except Exception as e:
            print(f"❌ Error CRÍTICO guardando historial: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
