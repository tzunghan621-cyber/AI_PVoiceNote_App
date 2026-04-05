"""設定管理 — 讀取/寫入 YAML 設定檔"""

from __future__ import annotations

from pathlib import Path

import yaml


class ConfigManager:
    def __init__(self, config_path: str = "config/default.yaml"):
        self._path = Path(config_path)
        with open(self._path, "r", encoding="utf-8") as f:
            self._config: dict = yaml.safe_load(f)

    def get(self, dotted_key: str, default=None):
        """取得設定值。支援點分隔 key，如 'whisper.model'"""
        keys = dotted_key.split(".")
        val = self._config
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
                if val is None:
                    return default
            else:
                return default
        return val

    def set(self, dotted_key: str, value):
        """設定值。支援點分隔 key。"""
        keys = dotted_key.split(".")
        d = self._config
        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value

    def save(self):
        """回寫 YAML 到檔案"""
        with open(self._path, "w", encoding="utf-8") as f:
            yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False)
