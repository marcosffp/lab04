# Lab 04 — Transparência em Sistemas Distribuídos: Código na Prática

**Disciplina:** Laboratório de Desenvolvimento de Aplicações Móveis e Distribuídas  
**Curso:** Engenharia de Software — PUC Minas  
**Professor:** Cristiano de Macedo Neto  
**Carga horária:** 100 minutos  
**Pré-requisitos:** Lab 02 (concorrência e async) concluído; Python 3.11+ instalado  

---

## Contexto e Motivação

A norma ISO/IEC 10746 — *Reference Model of Open Distributed Processing* (RM-ODP) — define **transparência** como a propriedade de um sistema distribuído de ocultar do usuário e do programador de aplicações a separação entre seus componentes. Em outras palavras: o sistema distribuído deve se comportar, do ponto de vista do código cliente, como se fosse um sistema centralizado simples.

Este laboratório traduz cada um dos sete tipos de transparência da RM-ODP em código Python executável, seguindo a abordagem "antes e depois" vista em aula. Ao final, você também vai explorar os **limites** da transparência — situações em que esconder a distribuição é, na verdade, prejudicial.

> **Referência principal:** TANENBAUM, Andrew S.; VAN STEEN, Maarten. *Distributed Systems: Principles and Paradigms*. 3. ed. Pearson, 2017. Cap. 1 (Seção 1.3 — Transparency).

---

## Objetivos de Aprendizagem

Ao concluir este laboratório, o aluno será capaz de:

1. Identificar cada um dos 7 tipos de transparência da ISO/RM-ODP em trechos de código reais.
2. Refatorar código sem transparência aplicando o padrão adequado.
3. Reconhecer anti-padrões em que a transparência excessiva obscurece falhas de rede.
4. Explicar por que `threading.Lock()` **não é suficiente** como mecanismo de exclusão mútua em sistemas distribuídos com múltiplos processos.

---

## Gestão de Tempo

> ⚠️ Este laboratório tem mais conteúdo do que tempo disponível por design. As Tarefas 1 a 6 são obrigatórias; a Tarefa 7 é para quem terminar antes. Gerencie seu ritmo: se uma tarefa ultrapassar o tempo indicado, passe para a próxima e retome depois.

| Tarefa | Tipo | Tempo sugerido |
|---|---|---|
| Provisionamento Redis Cloud | Setup | 10 min |
| Tarefa 1 — Acesso | Implementação | 15 min |
| Tarefa 2 — Localização | Implementação | 10 min |
| Tarefa 3 — Migração | Implementação | 15 min |
| Tarefa 4 — Relocação | Análise + discussão | 10 min |
| Tarefa 5 — Replicação | Implementação | 10 min |
| Tarefa 6 — Concorrência | Implementação | 20 min |
| Tarefa 7 — Falha | Implementação (opcional) | +10 min |
| **Total** | | **~90 min + 10 bônus** |

---

## Ambiente e Dependências

```bash
# Criar ambiente virtual (recomendado)
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate.bat     # Windows

# Instalar dependências
pip install requests redis websockets python-dotenv
```

---

## Pré-requisito: Provisionando sua Instância Redis Cloud (gratuita)

As Tarefas 3 e 6 exigem um servidor Redis **externo e compartilhado entre processos distintos**. Neste laboratório você utilizará o **Redis Cloud** — banco Redis gerenciado como serviço, com plano gratuito de 30 MB, sem necessidade de cartão de crédito.

> **Documentação oficial:** <https://redis.io/docs/latest/operate/rc/>

### Passo a passo de provisionamento

**1. Criar conta gratuita**

Acesse <https://redis.io/try-free/> e crie sua conta. Você pode usar e-mail/senha ou autenticação via Google/GitHub.

**2. Criar o banco de dados gratuito**

Após o login no [Redis Cloud Console](https://cloud.redis.io/):

- Clique em **"New database"**
- Selecione o plano **"Essentials — Free (30 MB)"**
- Escolha um provedor de nuvem e região próxima ao Brasil (ex.: AWS `us-east-1` ou GCP `us-east1`)
- Clique em **"Confirm & create"**
- Aguarde cerca de 1 minuto até o status ficar **"Active"**

**3. Obter as credenciais de conexão**

Na tela do banco criado, localize e anote:

| Campo | Onde encontrar |
|---|---|
| **Public endpoint** | Seção "General" — formato `redis-XXXXX.c1.us-east-1-2.ec2.redns.redis-cloud.com:PORTA` |
| **Password** | Seção "Security" → clique no ícone de olho ao lado de "Default user password" |

**4. Configurar variáveis de ambiente**

Crie um arquivo `.env` na raiz do seu projeto `lab04/` com as credenciais — **nunca coloque senhas diretamente no código-fonte**:

```dotenv
# lab04/.env  — NÃO versionar este arquivo (adicione ao .gitignore)
REDIS_HOST=redis-XXXXX.c1.us-east-1-2.ec2.redns.redis-cloud.com
REDIS_PORT=12345
REDIS_PASSWORD=sua_senha_aqui
```

**5. Testar a conexão**

Execute o snippet abaixo para confirmar que a conexão funciona antes de prosseguir com as tarefas:

```python
# teste_conexao_redis.py
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
```

> **Importante:** Adicione `.env` ao seu `.gitignore`:
> ```bash
> echo ".env" >> .gitignore
> ```

> **Nota sobre TLS:** O plano gratuito **Essentials** não usa TLS. Se você receber o erro `[SSL: WRONG_VERSION_NUMBER]`, certifique-se de que `ssl=False` está configurado.

**6. Função de conexão padrão**

Todos os arquivos que usam Redis neste laboratório devem reutilizar esta função:

```python
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
```

---

## Estrutura do Repositório

```
lab04/
├── .env                        <- credenciais Redis Cloud (NÃO versionar)
├── .gitignore                  <- deve conter ".env"
├── teste_conexao_redis.py
├── t1_acesso/
│   ├── sem_acesso.py
│   ├── com_acesso.py
│   └── config.json
├── t2_localizacao/
│   ├── sem_localizacao.py
│   └── com_localizacao.py
├── t3_migracao/
│   ├── instancia_a.py          <- salva a sessão (instância que "cai")
│   └── instancia_b.py          <- lê a sessão (instância que assumiu)
├── t4_relocacao/
│   └── relocacao_websocket.py  <- análise de código
├── t5_replicacao/
│   └── replicacao_transparente.py
├── t6_concorrencia/
│   ├── sem_concorrencia.py
│   └── com_concorrencia.py
├── t7_falha/
│   └── transparencia_falha.py
└── reflexao.md
```

---

## Roteiro de Atividades

### Tarefa 1 — Transparência de Acesso (15 min)

**Conceito:** O cliente não deve precisar conhecer *como* o recurso é acessado — se é um arquivo local, uma API HTTP ou um bucket S3. A interface de acesso deve ser uniforme independente do backend.

**Passo 1.1 — Analise o problema:**

Crie `t1_acesso/sem_acesso.py` com o código abaixo e execute-o. Observe que o cliente precisa decidir a origem em tempo de escrita e lidar com três APIs completamente diferentes.

```python
# sem_acesso.py
import json
import requests

def ler_configuracao(origem: str):
    if origem == "local":
        with open("config.json") as f:
            return json.load(f)
    elif origem == "http":
        resp = requests.get("http://config-srv/config")
        return resp.json()
    elif origem == "s3":
        raise NotImplementedError("S3 não configurado neste lab")

try:
    cfg = ler_configuracao("local")
    print("Configuração carregada:", cfg)
except FileNotFoundError:
    print("config.json não encontrado — crie um para testar")
```

Crie também `t1_acesso/config.json`:

```json
{"database": {"host": "localhost", "port": 5432}}
```

**Passo 1.2 — Aplique a transparência:**

Crie `t1_acesso/com_acesso.py`. O padrão aplicado é o **Strategy** (GoF): o algoritmo de acesso é encapsulado em classes intercambiáveis (`LocalConfig`, `RemoteConfig`) atrás de um contrato comum (`ConfigRepository`). O cliente nunca conhece qual implementação está em uso.

```python
# com_acesso.py
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
```

**Questões para reflexão:**
- Execute com `CONFIG_BACKEND=local` e depois com `CONFIG_BACKEND=http` (vai falhar com `ConnectionError` — esperado). O código cliente precisou mudar entre as duas execuções?
- Identifique os papéis de `ConfigRepository`, `LocalConfig` e `get_repo_from_env()` no padrão Strategy.

---

### Tarefa 2 — Transparência de Localização (10 min)

**Conceito:** O cliente usa **nomes lógicos** para identificar serviços, nunca IPs ou portas hardcoded. O mapeamento nome→endereço é resolvido em tempo de execução por um mecanismo de descoberta. Em produção esse mecanismo é um Consul, etcd ou o DNS interno do Kubernetes — neste laboratório simulamos o registro via variáveis de ambiente para isolar o conceito sem dependência de infraestrutura adicional.

**Passo 2.1 — Analise o problema:**

```python
# sem_localizacao.py
import requests

def buscar_usuario(user_id: int):
    # IP fixo — qualquer mudança de servidor exige redeploy
    url = f"http://192.168.10.42:8080/users/{user_id}"
    return requests.get(url, timeout=2).json()

def buscar_produto(prod_id: int):
    url = f"http://192.168.10.55:9090/products/{prod_id}"
    return requests.get(url, timeout=2).json()

# Teste — vai falhar com ConnectionError (IPs inexistentes, propositalmente)
try:
    u = buscar_usuario(1)
except Exception as e:
    print(f"Falha esperada (IP hardcoded): {type(e).__name__}")
```

**Passo 2.2 — Aplique a transparência:**

```python
# com_localizacao.py
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
```

**Questões para reflexão:**
- O `ServiceLocator` faz resolução estática (na inicialização). O que precisaria mudar para que a resolução fosse **dinâmica** — refletindo instâncias que sobem e caem em tempo real?
- Cite duas tecnologias de produção utilizadas como service registry (além do Consul).

---

### Tarefa 3 — Transparência de Migração (15 min)

**Conceito:** O cliente não percebe que um serviço foi **movido** de um servidor para outro. Para isso, o estado da sessão não pode residir na memória da instância que está sendo movida — ele precisa estar em um store externo e independente da instância.

Esta tarefa usa **dois scripts separados** para demonstrar migração de forma realista: a "Instância A" salva a sessão e é encerrada; a "Instância B" lê a mesma sessão do Redis Cloud, simulando a nova instância que assumiu o tráfego.

**Passo 3.1 — Analise o anti-padrão:**

```python
# anti_pattern_migracao.py — apenas para leitura, nao executar
# Estado preso a memoria da instancia: sessao perdida ao migrar

session_store = {}  # dicionario em memoria local

def save_session(user_id: str, data: dict):
    session_store[user_id] = data   # existe apenas NESTE processo

def get_session(user_id: str) -> dict:
    return session_store.get(user_id, {})

save_session("user_42", {"cart": ["item_1"]})
# Se este processo for encerrado e outro assumir o trafego,
# session_store estara vazio na nova instancia.
print(get_session("user_42"))   # ok aqui
# [processo encerrado — nova instancia sobe em outro servidor]
print(get_session("user_42"))   # {} — sessao perdida!
```

**Passo 3.2 — Instancia A: salva a sessao e encerra**

Crie `t3_migracao/instancia_a.py`:

```python
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
```

**Passo 3.3 — Instancia B: le a sessao apos a migracao**

Crie `t3_migracao/instancia_b.py`:

```python
# instancia_b.py — nova instancia que assumiu o trafego
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
```

**Como executar:**

```bash
# Passo 1: roda a Instancia A e encerra (processo termina sozinho)
python t3_migracao/instancia_a.py

# Passo 2: roda a Instancia B em um novo terminal (processo completamente separado)
python t3_migracao/instancia_b.py
```

**Questoes para reflexao:**
- A sessao persistiu entre dois processos Python completamente separados. O que isso demonstra sobre o principio de **separacao entre estado e logica computacional** (*stateless application + stateful store*)?
- Por que uma variavel global em memoria (`session_store = {}`) nao resolve o problema mesmo com as duas instancias na mesma maquina fisica, em um cenario com multiplas replicas da aplicacao?

---

### Tarefa 4 — Transparência de Relocacao (analise + discussao, 10 min)

**Conceito:** É uma forma mais exigente que a migracao: o recurso se move **enquanto ainda esta sendo usado** pelo cliente. O sistema deve manter a continuidade da operacao sem que o codigo de negocio perceba a interrupcao.

> Esta tarefa e uma **atividade de analise de codigo**, nao de implementacao. O objetivo e identificar as decisoes de design que tornam a relocacao transparente. Nao e necessario executar o codigo — ele depende de um servidor WebSocket real.

```python
# relocacao_websocket.py — analise de design
import asyncio
from enum import Enum

class ConnectionState(Enum):
    CONNECTED    = "connected"
    MIGRATING    = "migrating"      # relocacao em andamento
    RECONNECTING = "reconnecting"

class TransparentWSClient:
    """
    Cliente WebSocket com reconexao automatica transparente.
    O codigo de negocio chama .send() normalmente; toda a
    complexidade de relocacao e gerenciada internamente.
    """
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.state = ConnectionState.CONNECTED
        self._ws = None
        self._message_buffer = []

    async def send(self, msg: str):
        if self.state == ConnectionState.MIGRATING:
            # Bufferiza silenciosamente — o codigo de negocio nao percebe
            self._message_buffer.append(msg)
            return
        if self._ws:
            await self._ws.send(msg)

    async def _handle_relocation(self, new_endpoint: str):
        """
        Chamado quando o servidor sinaliza relocacao iminente.
        O codigo de negocio nao e notificado.
        """
        self.state = ConnectionState.MIGRATING
        print(f"Relocando conexao para {new_endpoint}...")
        # [abre nova conexao com new_endpoint — omitido]
        self.state = ConnectionState.RECONNECTING

        # Apos reconexao, reenvia mensagens bufferizadas em ordem
        for buffered_msg in self._message_buffer:
            await self._ws.send(buffered_msg)
        self._message_buffer.clear()
        self.state = ConnectionState.CONNECTED
        print("Relocacao concluida — buffer drenado.")
```

**Questoes para reflexao (discuta em dupla e registre no `reflexao.md`):**

1. Qual e a diferenca pratica entre **migracao** (Tarefa 3) e **relocacao** (esta tarefa)? Por que relocacao e tecnicamente mais dificil?
2. O buffer interno (`_message_buffer`) garante semantica de entrega *exactly-once*? O que poderia causar entrega duplicada ou perda de mensagem mesmo com o buffer?
3. A mudanca de estado `MIGRATING -> RECONNECTING -> CONNECTED` e uma maquina de estados. Por que modelar estados explicitamente em vez de uma flag booleana `is_relocating`?
4. Cite um sistema real em que transparencia de relocacao e requisito (dica: Kubernetes Pod rescheduling ou live migration de VMs).

---

### Tarefa 5 — Transparência de Replicação (10 min)

**Conceito:** O cliente nao sabe quantas copias (replicas) do servico existem, nem qual esta respondendo em cada requisicao. O balanceamento e o failover sao internos ao sistema.

```python
# replicacao_transparente.py
import random
from typing import List
from dataclasses import dataclass, field

class FakeConnection:
    def __init__(self, dsn: str):
        self.dsn = dsn

    def execute(self, sql: str) -> list:
        host = self.dsn.split("@")[-1]
        print(f"  [query em {host}]: {sql}")
        return [{"result": "ok"}]

def connect(dsn: str) -> FakeConnection:
    if "bad" in dsn:
        raise ConnectionError(f"Replica indisponivel: {dsn}")
    return FakeConnection(dsn)

@dataclass
class ReplicaPool:
    """
    Pool de replicas transparente. O cliente usa apenas .query().
    Internamente o pool faz balanceamento e failover automatico.
    """
    master_dsn: str
    replica_dsns: List[str] = field(default_factory=list)
    _healthy: List[str] = field(default_factory=list, init=False)

    def __post_init__(self):
        self._healthy = list(self.replica_dsns)

    def _pick_replica(self) -> str:
        return random.choice(self._healthy) if self._healthy else self.master_dsn

    def query(self, sql: str, write: bool = False) -> list:
        dsn = self.master_dsn if write else self._pick_replica()
        try:
            conn = connect(dsn)
            return conn.execute(sql)
        except ConnectionError as e:
            print(f"  [aviso] {e} — usando master como fallback.")
            if dsn in self._healthy:
                self._healthy.remove(dsn)
            if not write:
                # Fallback direto para master — sem recursao para evitar loop infinito
                conn = connect(self.master_dsn)
                return conn.execute(sql)
            raise  # escrita no master falhou — propaga para o chamador

pool = ReplicaPool(
    master_dsn="postgresql://app@master:5432/app",
    replica_dsns=[
        "postgresql://app@replica1:5432/app",
        "postgresql://app@bad-replica:5432/app",   # replica com falha simulada
        "postgresql://app@replica2:5432/app",
    ]
)

print("=== Leituras (com balanceamento entre replicas) ===")
for i in range(5):
    pool.query(f"SELECT * FROM users WHERE id={i + 1}")

print("\n=== Escrita (sempre no master) ===")
pool.query("INSERT INTO logs VALUES ('evento')", write=True)

print(f"\nReplicas saudaveis restantes: {len(pool._healthy)}")
```

**Questoes para reflexao:**
- O codigo acima implementa consistencia *read-your-writes*? O que precisaria mudar para garantir essa propriedade?
- Uma versao anterior deste codigo usava recursao no fallback (`return self.query(sql, write=True)`). Por que isso e perigoso? Como a versao atual resolve o problema?

---

### Tarefa 6 — Transparência de Concorrência (20 min)

**Conceito:** Multiplos processos acessam o mesmo recurso concorrentemente sem perceber uns aos outros. O sistema garante consistencia internamente por meio de exclusao mutua distribuida.

> **Por que `multiprocessing` e nao `threading`?**
> O CPython possui o GIL (*Global Interpreter Lock*), que impede que duas threads executem bytecode Python simultaneamente no mesmo processo. Isso significa que uma race condition com `threading` pode nao se manifestar de forma reproduzivel — tornando a demonstracao pedagogicamente imprecisa. Com `multiprocessing` cada processo tem seu proprio espaco de memoria e proprio GIL: a race condition e real, reproduzivel, e reflete com mais fidelidade o cenario de sistemas distribuidos, onde os processos concorrentes estao em maquinas diferentes.

**Passo 6.1 — Observe a race condition com processos reais:**

```python
# sem_concorrencia.py
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
```

Execute este codigo algumas vezes. O saldo e sempre R$500?

**Passo 6.2 — Lock distribuido com Redis:**

```python
# com_concorrencia.py
import multiprocessing
import time
import os
from contextlib import contextmanager
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

@contextmanager
def distributed_lock(r: redis.Redis, resource: str, ttl: int = 5):
    """
    Lock distribuido via Redis SET NX EX.
    NX = somente define se a chave NAO existir — operacao atomica no Redis.
    EX = TTL em segundos — previne deadlock se o processo travar antes de liberar.
    Documentacao: https://redis.io/docs/latest/commands/set/
    """
    key = f"lock:{resource}"
    acquired = r.set(key, "1", nx=True, ex=ttl)
    if not acquired:
        raise RuntimeError(f"Recurso '{resource}' em uso — tente novamente")
    try:
        yield
    finally:
        r.delete(key)  # sempre libera, mesmo em caso de excecao

def inicializar_saldo(valor: int = 1000):
    r = get_redis()
    r.set("conta:saldo", valor)
    print(f"Saldo inicial: R${valor}")

def transferir_com_lock(valor: int, nome: str):
    """Transferencia COM lock distribuido — segura entre processos distintos."""
    r = get_redis()
    with distributed_lock(r, "conta:saldo"):
        saldo_atual = int(r.get("conta:saldo"))
        time.sleep(0.05)                       # mesmo delay — agora serializado pelo lock
        novo_saldo = saldo_atual - valor
        r.set("conta:saldo", novo_saldo)
        print(f"  [{nome}] transferiu R${valor}. Saldo atual: R${novo_saldo}")

if __name__ == "__main__":
    inicializar_saldo(1000)

    p1 = multiprocessing.Process(target=transferir_com_lock, args=(200, "Processo-A"))
    p2 = multiprocessing.Process(target=transferir_com_lock, args=(300, "Processo-B"))

    p1.start(); p2.start()
    p1.join();  p2.join()

    r = get_redis()
    saldo_final = int(r.get("conta:saldo"))
    print(f"\nSaldo final no Redis: R${saldo_final}")
    print(f"Resultado: {'R$500 correto' if saldo_final == 500 else 'race condition detectada'}")
```

**Questoes para reflexao:**
- Por que esta tarefa usa `multiprocessing` em vez de `threading`? O que e o GIL e por que ele interfere na demonstracao de race conditions?
- O `distributed_lock` usa o Redis Cloud — um servidor **externo** aos dois processos. Por que isso e fundamentalmente diferente de um `threading.Lock()` local, que so funciona dentro de um unico processo?
- O que acontece se o Processo-A travar dentro da secao critica (antes do `finally`)? Como o parametro `ex` (TTL) mitiga esse risco? Existe algum risco residual mesmo com o TTL?

---

### Tarefa 7 — Transparência de Falha e seus Limites (opcional, +10 min)

**Parte A — Circuit Breaker:**

**Conceito:** O sistema mascara falhas e recuperacoes de componentes. O padrao *Circuit Breaker* intercepta chamadas remotas, conta falhas consecutivas e, apos um limiar, rejeita chamadas imediatamente (*fail fast*) — evitando que timeouts encadeados derrubem o sistema inteiro.

```python
# transparencia_falha.py
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
```

**Parte B — Quando NAO aplicar transparencia:**

```python
# anti_pattern.py — transparencia excessiva: parece uma chamada local
def get_user(user_id: int) -> dict:
    return db.query(f"SELECT * FROM users WHERE id={user_id}")

# O chamador nao tem como saber que isso pode:
#  - Levar 800ms (latencia de rede)
#  - Lancar TimeoutError (rede caiu)
#  - Retornar None silenciosamente e causar KeyError adiante
user = get_user(42)
print(user["name"])   # KeyError silencioso se user for None!
```

```python
# bom_pattern.py — transparencia consciente: o contrato e explicito
import asyncio
from typing import Optional

async def fetch_user_remote(
    user_id: int,
    timeout: float = 2.0
) -> Optional[dict]:
    """
    'async' sinaliza que esta operacao pode suspender o event loop.
    'remote' no nome sinaliza chamada de rede, nao operacao local.
    timeout explicito e retorno Optional[dict] forcam o chamador
    a lidar com a possibilidade de falha.
    """
    try:
        await asyncio.sleep(0.1)  # latencia simulada
        return {"id": user_id, "nome": "Usuario Teste"}
    except asyncio.TimeoutError:
        print(f"Timeout buscando user={user_id}")
        return None
    except Exception as e:
        print(f"Servico indisponivel: {e}")
        return None

async def main():
    user = await fetch_user_remote(42)
    if user:
        print("Usuario:", user["nome"])
    else:
        print("Usuario nao disponivel no momento.")

asyncio.run(main())
```

**Questoes para reflexao:**
- Qual das **oito falacies da computacao distribuida** de Peter Deutsch (1994) o `anti_pattern.py` viola diretamente? Enuncie a falacia.
- Por que `async/await` e uma forma deliberada de **quebrar** a transparencia — e por que isso e, neste contexto, a decisao correta de design?

---

## Bloco de Reflexao (obrigatorio — entregue no `reflexao.md`)

Responda individualmente, com suas proprias palavras. Cada resposta deve ter no minimo **4 linhas**, citar pelo menos **um conceito tecnico** e, quando aplicavel, referenciar o codigo que voce escreveu.

1. **Sintese:** Qual dos 7 tipos de transparencia voce considera mais dificil de implementar corretamente em um sistema real? Justifique com um argumento tecnico baseado nos exercicios realizados.

2. **Trade-offs:** Descreva um cenario concreto de um sistema que voce conhece (app, site, jogo) em que esconder completamente a distribuicao levaria a um sistema menos resiliente para o usuario final.

3. **Conexao com Labs anteriores:** Como o conceito de `async/await` explorado no Lab 02 se conecta com a decisao de quebrar a transparencia conscientemente, vista na Tarefa 7?

4. **GIL e multiprocessing:** Explique com suas palavras por que a Tarefa 6 usa `multiprocessing` em vez de `threading`. O que e o GIL e por que ele interfere na demonstracao de race conditions em Python?

5. **Desafio tecnico:** Descreva uma dificuldade tecnica encontrada durante o laboratorio (incluindo o provisionamento do Redis Cloud), o processo de diagnostico e a solucao. Se nao houve dificuldade, descreva o exercicio mais interessante e explique por que.

---

## Criterios de Avaliacao

| Criterio | Detalhamento | Peso |
|---|---|---|
| **Codigo executavel** | Tarefas 1, 2, 3, 5 e 6 rodando sem erros, organizadas conforme a estrutura do repositorio | 50% |
| **Reflexao** | 5 respostas no `reflexao.md`, minimo 4 linhas cada, com ao menos 1 conceito tecnico por resposta | 30% |
| **Organizacao** | Estrutura de arquivos correta, `.env` no `.gitignore`, sem credenciais hardcoded no codigo | 10% |
| **Tarefa 7 (bonus)** | Circuit Breaker executavel + respostas das questoes da Parte B no `reflexao.md` | +10% |

---

## Referencias

- TANENBAUM, Andrew S.; VAN STEEN, Maarten. *Distributed Systems: Principles and Paradigms*. 3. ed. Pearson, 2017. Secoes 1.3 e 8.5.
- ISO/IEC 10746-1. *Information Technology — Open Distributed Processing — Reference Model: Overview*. 1998.
- NYGARD, Michael T. *Release It! Design and Deploy Production-Ready Software*. 2. ed. Pragmatic Bookshelf, 2018. Cap. 5 (Circuit Breaker).
- DEUTSCH, Peter. *The Eight Fallacies of Distributed Computing*. Sun Microsystems, 1994. Disponivel em: <https://nighthacks.com/jag/res/Fallacies.html>.
- MARTIN, Robert C. *Arquitetura Limpa: o guia do artesao para estrutura e design de software*. Alta Books, 2019. Cap. 17 (Boundaries: Drawing Lines) e Cap. 18 (Boundary Anatomy).
- PYTHON SOFTWARE FOUNDATION. *multiprocessing — Process-based parallelism*. Disponivel em: <https://docs.python.org/3/library/multiprocessing.html>.
