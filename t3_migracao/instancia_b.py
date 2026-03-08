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
print("[Instancia B] Nova instancia conectada ao Redis Cloud.")

def get_session(user_id: str) -> dict:
    raw = r.get(f"session:{user_id}")
    return json.loads(raw) if raw else {}

sessao = get_session("user_42")

if sessao:
    print(f"[Instancia B] Sessao recuperada: {sessao}")
    print("[Instancia B] O usuario nao percebeu a migracao de servidor.")
else:
    print("[Instancia B] Sessao nao encontrada — execute instancia_a.py primeiro.")