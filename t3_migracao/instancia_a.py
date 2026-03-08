# instancia_a.py — instancia que vai ser migrada/encerrada
import json
import os
from dotenv import load_dotenv
import redis

load_dotenv()

def get_redis() -> redis.Redis:
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD"),
        ssl=False,
        decode_responses=True
    )

r = get_redis()
r.ping()
print("[Instancia A] Conectada ao Redis Cloud.")

def save_session(user_id: str, data: dict) -> None:
    r.setex(name=f"session:{user_id}", time=3600, value=json.dumps(data))
    print(f"[Instancia A] Sessao de '{user_id}' salva no Redis Cloud.")

# Usuario navega — estado salvo no Redis Cloud, nao em memoria
save_session("user_42", {"cart": ["item_1", "item_2"], "promo": "DESCONTO10"})
print("[Instancia A] Encerrando processo — simulando migracao de servidor.")
# Processo termina aqui. A sessao sobrevive no Redis Cloud.