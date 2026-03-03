import os
from dotenv import load_dotenv
import redis

load_dotenv()

r = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD"),
    ssl=False,              # plano Essentials (gratuito) não usa TLS
    decode_responses=True
)

try:
    r.ping()
    print("Conexão com Redis Cloud estabelecida com sucesso!")
    r.set("lab04:teste", "ok", ex=60)
    print("SET/GET funcionando:", r.get("lab04:teste"))
except redis.exceptions.ConnectionError as e:
    print(f"Falha de conexão: {e}")
    print("   Verifique HOST e PORT no seu .env")
except redis.exceptions.AuthenticationError as e:
    print(f"Falha de autenticação: {e}")
    print("   Verifique se a REDIS_PASSWORD está correta no seu .env")