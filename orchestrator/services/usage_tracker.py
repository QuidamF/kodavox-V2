import os
import json
from datetime import datetime

class UsageTracker:
    def __init__(self):
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.file_path = os.path.join(self.data_dir, "usage_stats.json")
        self.stats = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, indent=4)
        except Exception as e:
            print(f"[UsageTracker] Error guardando estadísticas: {e}")

    def _get_today_key(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _ensure_today(self, today: str):
        if today not in self.stats:
            self.stats[today] = {
                "openai_tokens_in": 0,
                "openai_tokens_out": 0,
                "gemini_tokens": 0,
                "elevenlabs_chars": 0
            }

    def add_openai_tokens(self, tokens_in: int, tokens_out: int):
        today = self._get_today_key()
        self._ensure_today(today)
        self.stats[today]["openai_tokens_in"] += tokens_in
        self.stats[today]["openai_tokens_out"] += tokens_out
        self._save()

    def add_gemini_tokens(self, tokens_total: int):
        today = self._get_today_key()
        self._ensure_today(today)
        self.stats[today]["gemini_tokens"] += tokens_total
        self._save()
        
    def add_elevenlabs_chars(self, chars: int):
        today = self._get_today_key()
        self._ensure_today(today)
        self.stats[today]["elevenlabs_chars"] += chars
        self._save()

    def get_all_stats(self) -> dict:
        return self.stats

tracker = UsageTracker()
