import json
import os
from datetime import datetime

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
