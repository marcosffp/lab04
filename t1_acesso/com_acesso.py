import json
import os
import requests
from abc import ABC, abstractmethod

class ConfigRepository(ABC):
    @abstractmethod
    def get(self, key: str) -> dict: ...

class LocalConfig(ConfigRepository):
    def __init__(self, path: str = "config.json"):
        self._path = path

    def get(self, key: str) -> dict:
        with open(self._path) as f:
            return json.load(f)[key]

class RemoteConfig(ConfigRepository):
    def __init__(self, base_url: str):
        self._base = base_url

    def get(self, key: str) -> dict:
        r = requests.get(f"{self._base}/{key}", timeout=3)
        r.raise_for_status()
        return r.json()

def get_repo_from_env() -> ConfigRepository:
    """Factory: seleciona o backend pela variável CONFIG_BACKEND."""
    backend = os.getenv("CONFIG_BACKEND", "local")
    if backend == "local":
        return LocalConfig()
    elif backend == "http":
        url = os.getenv("CONFIG_URL", "http://localhost:8080/config")
        return RemoteConfig(url)
    raise ValueError(f"Backend desconhecido: {backend}")

# O código cliente é IDENTICO independente do backend configurado
repo = get_repo_from_env()
try:
    cfg = repo.get("database")
    print("Configuração obtida:", cfg)
except Exception as e:
    print(f"Erro ao obter configuração: {e}")