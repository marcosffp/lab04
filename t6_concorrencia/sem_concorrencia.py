import multiprocessing
import time
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

def inicializar_saldo(valor: int = 1000):
    r = get_redis()
    r.set("conta:saldo", valor)
    print(f"Saldo inicial: R${valor}")

def transferir_sem_lock(valor: int, nome: str):
    """Transferencia SEM controle de concorrencia — sujeita a race condition."""
    r = get_redis()
    saldo_atual = int(r.get("conta:saldo"))  # Processo A le 1000
    time.sleep(0.05)                          # B tambem le 1000 durante este sleep
    novo_saldo = saldo_atual - valor
    r.set("conta:saldo", novo_saldo)          # A escreve 800; B escreve 700 (correto seria 500)
    print(f"  [{nome}] transferiu R${valor}. Saldo registrado: R${novo_saldo}")

if __name__ == "__main__":
    inicializar_saldo(1000)

    p1 = multiprocessing.Process(target=transferir_sem_lock, args=(200, "Processo-A"))
    p2 = multiprocessing.Process(target=transferir_sem_lock, args=(300, "Processo-B"))

    p1.start(); p2.start()
    p1.join();  p2.join()

    r = get_redis()
    saldo_final = int(r.get("conta:saldo"))
    print(f"\nSaldo final no Redis: R${saldo_final}")
    print(f"Saldo correto seria: R$500")
    print(f"Perda por race condition: R${500 - saldo_final}")