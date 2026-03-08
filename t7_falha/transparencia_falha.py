import time
import random
from enum import Enum

class CBState(Enum):
    CLOSED    = "closed"      # normal: requisicoes passam
    OPEN      = "open"        # falhas detectadas: rejeita rapidamente
    HALF_OPEN = "half_open"   # teste: uma requisicao passa para verificar recuperacao

class CircuitBreaker:
    """
    Padrao Circuit Breaker para transparencia de falha.
    Referencia: NYGARD, Michael T. Release It! 2. ed. Pragmatic Bookshelf, 2018.
    """
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 5.0):
        self.state       = CBState.CLOSED
        self.failures    = 0
        self.threshold   = failure_threshold
        self.timeout     = recovery_timeout
        self._opened_at  = None

    def call(self, fn, *args, **kwargs):
        if self.state == CBState.OPEN:
            if time.time() - self._opened_at > self.timeout:
                self.state = CBState.HALF_OPEN
                print("  [CB] HALF_OPEN — testando recuperacao do servico")
            else:
                print("  [CB] OPEN — falha rapida (servico indisponivel)")
                return None

        try:
            result = fn(*args, **kwargs)
            if self.state == CBState.HALF_OPEN:
                print("  [CB] Servico recuperado -> CLOSED")
                self.state    = CBState.CLOSED
                self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            print(f"  [CB] Falha #{self.failures}: {e}")
            if self.failures >= self.threshold:
                self.state      = CBState.OPEN
                self._opened_at = time.time()
                print(f"  [CB] Limiar atingido -> OPEN por {self.timeout}s")
            return None

def servico_externo(user_id: int) -> dict:
    """Servico instavel — 70% de chance de falha."""
    if random.random() < 0.7:
        raise ConnectionError("Timeout de rede")
    return {"id": user_id, "nome": "Usuario Teste"}

cb = CircuitBreaker(failure_threshold=3, recovery_timeout=3.0)

print("=== Simulando 10 chamadas ao servico externo ===\n")
for i in range(10):
    resultado = cb.call(servico_externo, i)
    status = f"ok: {resultado}" if resultado else "falhou"
    print(f"  Chamada {i + 1:02d}: {status} | Estado CB: {cb.state.value}")
    time.sleep(0.3)