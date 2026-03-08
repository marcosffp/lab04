import os
import requests

# Em producao este dicionario seria substituido por uma chamada ao Consul,
# etcd ou DNS interno do Kubernetes. A interface do ServiceLocator nao muda.
SERVICE_REGISTRY = {
    "user-service":    os.getenv("USER_SERVICE_URL",    "http://localhost:8080"),
    "product-service": os.getenv("PRODUCT_SERVICE_URL", "http://localhost:9090"),
}

class ServiceLocator:
    """Resolve nomes logicos de servico para URLs concretas."""
    def __init__(self, registry: dict):
        self._registry = registry

    def resolve(self, service_name: str) -> str:
        url = self._registry.get(service_name)
        if not url:
            raise ValueError(f"Servico '{service_name}' nao registrado")
        return url

locator = ServiceLocator(SERVICE_REGISTRY)

def buscar_usuario(user_id: int) -> dict:
    base = locator.resolve("user-service")   # nome logico, nunca IP
    try:
        return requests.get(f"{base}/users/{user_id}", timeout=2).json()
    except Exception as e:
        print(f"[user-service] indisponivel: {e}")
        return {}

def buscar_produto(prod_id: int) -> dict:
    base = locator.resolve("product-service")
    try:
        return requests.get(f"{base}/products/{prod_id}", timeout=2).json()
    except Exception as e:
        print(f"[product-service] indisponivel: {e}")
        return {}

print("URL resolvida para user-service:", locator.resolve("user-service"))
print("Resultado da busca:", buscar_usuario(1))  # falha graciosamente