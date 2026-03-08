# Reflexão

## Sumário

- **Tarefas**

- [Tarefa 1 — Transparência de Acesso](#tarefa-1--transparência-de-acesso)
- [Tarefa 2 — Transparência de Localização](#tarefa-2--transparência-de-localização)
- [Tarefa 3 — Transparência de Migração](#tarefa-3--transparência-de-migração)
- [Tarefa 4 — Transparência de Relocação](#tarefa-4--transparência-de-relocação)
- [Tarefa 5 — Transparência de Replicação](#tarefa-5--transparência-de-replicação)
- [Tarefa 6 — Transparência de Concorrência](#tarefa-6--transparência-de-concorrência)
- [Tarefa 7 — Transparência de Falha e seus Limites](#tarefa-7--transparência-de-falha-e-seus-limites)

- **Bloco de Reflexão**

- [Questão 1](#questão-1)
- [Questão 2](#questão-2)
- [Questão 3](#questão-3)
- [Questão 4](#questão-4)
- [Questão 5](#questão-5)

---

## Tarefa 1 — Transparência de Acesso

Quatro cenários foram executados. Com `CONFIG_BACKEND=local` o resultado foi o esperado: `{'host': 'localhost', 'port': 5432}`. Com `CONFIG_BACKEND=invalido` o `com_acesso.py` lançou `ValueError: Backend desconhecido: invalido` — falha rápida e explicita, sem comportamento silencioso. Com `CONFIG_BACKEND=http` sem servidor na porta 8080, retornou `ConnectionRefusedError`. Subindo o `http.server`, a conexão foi estabelecida mas retornou 404 em `/database`, confirmando que a URL está sendo montada corretamente como `{base_url}/{key}`.

O código cliente não precisou mudar entre nenhuma das execuções. A chamada `repo.get("database")` é idêntica independente do backend — essa é exatamente a transparência de acesso que o padrão oferece. No `sem_acesso.py` isso não acontece: o cliente precisa passar `"local"` ou `"http"` explicitamente, acoplando a lógica de transporte à lógica de negócio.

- **Quanto aos papéis no padrão Strategy:** `ConfigRepository` é a interface que define o contrato — qualquer backend precisa implementar `get(key)`. `LocalConfig` e `RemoteConfig` são as estratégias concretas, cada uma encapsulando um mecanismo diferente de acesso. `get_repo_from_env()` é a factory que decide qual estratégia instanciar com base no ambiente, mantendo essa decisão fora do código cliente. O resultado é que trocar de backend vira configuração, não alteração de código.

## Tarefa 2 — Transparência de Localização

Quatro cenários foram executados. O `sem_localizacao.py` falhou com `ConnectTimeout` — o IP `192.168.10.42` não existe e o cliente ficou esperando até o timeout, sem nenhuma mensagem útil.

O `com_localizacao.py` sem variável resolveu `"user-service"` para o fallback `http://localhost:8080` e falhou com `Expecting value: line 1 column 1` — o servidor de arquivos estáticos respondeu 200 com HTML em vez de JSON, o que confirma que a URL foi montada corretamente como `{base}/users/1` e chegou ao servidor. A falha é no parse da resposta, não na conexão.

O cenário com `env USER_SERVICE_URL==http://localhost:8080` (dois sinais de igual) gerou o erro `No connection adapters were found for '=http://localhost:8080/users/1'` — o `=` extra foi incluído na URL, o que mostrou na prática que o locator usa o valor da variável sem validação. Corrigindo para um único `=`, o comportamento voltou ao normal.

O código cliente não precisou mudar em nenhum dos cenários — a chamada `buscar_usuario(1)` é idêntica independente de onde o serviço está.

- **Resolução dinâmica:** o `SERVICE_REGISTRY` é montado uma vez na inicialização do módulo, então instâncias que sobem depois não são refletidas. Para resolução dinâmica, o método `resolve()` do `ServiceLocator` precisaria consultar um registry externo a cada chamada em vez de ler um dicionário em memória — assim, se uma instância cair e uma nova subir com endereço diferente, a próxima chamada ao `resolve()` já retorna o endereço atualizado em vez de continuar apontando para um servidor que não existe mais.

- **Duas tecnologias além do Consul:**
-**Eureka** — desenvolvido pela Netflix e integrado ao Spring Cloud, cada serviço se registra automaticamente ao subir e se desregistra ao cair. O `ServiceLocator` substituiria a leitura do dicionário local por uma chamada à API REST do Eureka, que retorna as instâncias ativas naquele momento.
-**Apache ZooKeeper** — usado por Kafka e Hadoop para coordenação distribuída. Cada serviço que sobe cria um *ephemeral node* — um nó temporário que existe enquanto o processo estiver vivo. Quando o processo morre, o ZooKeeper remove o nó automaticamente e notifica os outros serviços, mantendo a lista de instâncias sempre atualizada sem lógica manual de desregistro.

- **Referências**
- Eureka — documentação oficial do Spring Cloud Netflix: <https://spring.io/projects/spring-cloud-netflix>
- Eureka — repositório original Netflix OSS: <https://github.com/Netflix/eureka>
- Apache ZooKeeper — documentação oficial: <https://zookeeper.apache.org/doc/current/zookeeperOver.html>
- ZooKeeper ephemeral nodes: <https://zookeeper.apache.org/doc/current/zookeeperProgrammers.html#Ephemeral+Nodes>

## Tarefa 3 — Transparência de Migração

A Instância A salvou a sessão no Redis Cloud e encerrou. A Instância B subiu como processo completamente separado, conectou no mesmo Redis e recuperou `{'cart': ['item_1', 'item_2'], 'promo': 'DESCONTO10'}` sem nenhuma comunicação direta entre os dois processos.

- **Separação entre estado e lógica:** o que o experimento demonstra é que a lógica computacional — o código que salva e lê sessão — pode residir em qualquer processo, em qualquer máquina, desde que o estado esteja num store externo compartilhado. A Instância B não recebeu nada da Instância A diretamente; ela apenas soube a chave `session:user_42` e o Redis entregou o estado. Isso é o princípio *stateless application + stateful store*: a aplicação não carrega estado entre requisições, quem carrega é o Redis. Qualquer réplica da aplicação que conheça a chave consegue continuar o trabalho de onde outra parou.

- **Por que `session_store = {}` não resolve:** mesmo que as duas instâncias estejam na mesma máquina física, cada processo Python tem seu próprio espaço de memória isolado pelo sistema operacional. Um dicionário em memória na Instância A é invisível para a Instância B — não há compartilhamento automático entre processos. Em produção, com múltiplas réplicas rodando em containers ou VMs diferentes, o problema é ainda mais evidente: cada réplica teria seu próprio `session_store` vazio, e o usuário perderia o carrinho toda vez que o load balancer direcionasse a requisição para uma réplica diferente da que atendeu o login.

## Tarefa 4 — Transparência de Relocação

- **Diferença entre migração e relocação:** na Tarefa 3, a Instância A encerrou completamente antes da Instância B assumir — não havia conexão ativa para manter. Na relocação, o serviço se move enquanto há uma conexão WebSocket aberta e em uso. Relocação é tecnicamente mais difícil porque exige que o cliente continue funcionando durante a transição: mensagens enviadas no intervalo entre a conexão antiga cair e a nova subir não podem ser perdidas, o que exige bufferização, reordenação e reenvio — complexidade inexistente na migração simples.

- **_message_buffer:** O `_message_buffer` garante que mensagens enviadas durante `MIGRATING` não sejam descartadas, mas não garante exactly-once. Se a nova conexão cair após o reenvio parcial do buffer e antes do `clear()`, as mensagens já enviadas serão reenviadas novamente — entrega duplicada. Perda pode ocorrer se o processo crashar enquanto o buffer ainda está em memória, antes de qualquer reenvio. Para exactly-once seria necessário persistir o buffer externamente e usar identificadores de mensagem para deduplicação no receptor.

- **Mudança de estados:** Uma flag `is_relocating` só distingue dois estados, mas o processo tem três fases relevantes: bufferizando (`MIGRATING`), reconectando (`RECONNECTING`) e operacional (`CONNECTED`). Além disso, estados explícitos dificultam transições inválidas — com uma flag booleana nada impede ir de `MIGRATING` direto para `CONNECTED` sem passar pelo `RECONNECTING`, o que poderia causar o envio de mensagens antes da nova conexão estar estabelecida. A máquina de estados torna essas transições explícitas no código, facilitando a identificação de comportamentos incorretos.

- **Sistema real:** Kubernetes Pod rescheduling, onde o Service mantém o mesmo DNS interno mesmo com o Pod sendo movido entre nós; e live migration de VMs em hipervisores como VMware, onde a VM é transferida entre hosts com a memória copiada incrementalmente enquanto continua em execução.

- **Referências**

- Kubernetes Services e DNS interno: <https://kubernetes.io/docs/concepts/services-networking/service/>
- Kubernetes Pod scheduling e eviction: <https://kubernetes.io/docs/concepts/scheduling-eviction/kube-scheduler/>
- Live migration KVM: <https://www.linux-kvm.org/page/Migration>
- VMware vSphere Live Migration (vMotion): <https://docs.vmware.com/en/VMware-vSphere/8.0/vsphere-vcenter-esxi-management/GUID-D19EA1CB-5222-49F9-A002-4F8692B3E3D2.html>

## Tarefa 5 — Transparência de Replicação

- **Read-your-writes:** O código não garante essa consistência. Após uma escrita no master, a próxima leitura vai para uma réplica escolhida aleatoriamente por _pick_replica() — e réplicas têm lag de replicação, então o dado recém-escrito pode não estar disponível ainda.

Com posição no log de replicação, geralmente os bancos de dados mantém um log sequencial de alterações — cada inserção, atualização ou deleção gera uma entrada ordenada nesse log. Em sistemas com replicação baseada em log, as réplicas se atualizam lendo e aplicando essas entradas na mesma ordem. Após uma escrita, o servidor primário pode devolver a posição do log (por exemplo, um LSN). Em leituras subsequentes, o cliente envia essa posição mínima exigida para a réplica. Se a réplica já aplicou todas as entradas até aquela posição, ela responde normalmente; caso contrário, a leitura é direcionada ao primário. Assim, o primário só é consultado quando a réplica realmente está atrasada.

Outra alternativa é usar **sticky session após escrita**. Nesse modelo, quando uma sessão realiza uma operação de escrita, o sistema registra que aquela sessão escreveu recentemente e, por um período curto de tempo, direciona todas as leituras dessa mesma sessão para o servidor primário. A ideia é que logo após uma escrita existe maior chance de as réplicas ainda não terem recebido a atualização devido ao *replication lag*. Ao manter temporariamente as leituras da sessão no primário, isso possibilita que o cliente veja o resultado da própria escrita. Após esse intervalo — geralmente alguns segundos, tempo suficiente para que a replicação se propague na maioria dos casos — as leituras voltam a ser distribuídas normalmente entre as réplicas.

- **Recursão no fallback:** A versão antiga do query() chamava return self.query(sql, write=True) dentro do próprio except ConnectionError. O problema fica acompanhando o fluxo: query() tenta conectar na réplica → falha → cai no except → chama self.query() de novo → tenta o master → master também fora → cai no except de novo → chama self.query() de novo → loop infinito até o Python estourar a pilha com RecursionError. A versão atual quebra esse ciclo porque no except chama connect(self.master_dsn) diretamente, sem passar pelo query(). Se o master também falhar nesse ponto, o ConnectionError sobe imediatamente para quem chamou — sem nenhuma chamada recursiva no caminho. O comentário # Fallback direto para master — sem recursao para evitar loop infinito no código confirma que foi uma decisão consciente de refatoração.

- **Referências**

- PostgreSQL WAL Internals: <https://www.postgresql.org/docs/current/wal-internals.html>
- Sticky Writer (Kir Shatrov): <https://kirshatrov.com/posts/sticky-writer>

## Tarefa 6 — Transparência de Concorrência

### Correção do Lock Distribuído

#### Problema na implementação inicial

Na primeira versão do código, o lock distribuído usava o comando do Redis:

```
SET lock:conta:saldo 1 NX EX 5
```

Isso garante que apenas **um processo crie o lock**, pois `NX` impede sobrescrever a chave existente.

Porém, se o lock já estivesse em uso, o código fazia:

```python
if not acquired:
    raise RuntimeError(...)
```

Ou seja, o processo **abortava imediatamente** em vez de esperar o lock ser liberado.

#### Execução observada

```
(venv)
User@DESKTOP-M0Q2F5Q MINGW64 /d/github/lab04/t6_concorrencia (master)
$ python com_concorrencia.py

Saldo inicial: R$1000

RuntimeError: Recurso 'conta:saldo' em uso — tente novamente

  [Processo-B] transferiu R$300. Saldo atual: R$700

Saldo final no Redis: R$700
Resultado: race condition detectada
```

Nesse caso, apenas **um processo executou a transferência**, resultando em saldo incorreto.

O valor esperado seria:

```
1000 - 200 - 300 = 500
```

---

#### Solução

O lock foi modificado para **tentar novamente até que o recurso fique disponível**, usando retry com timeout.

Estratégia:

```
tenta adquirir lock
se não conseguir:
    espera um pequeno intervalo
    tenta novamente
```

Trecho principal:

```python
while time.time() < deadline:

    if r.set(key, "1", nx=True, ex=ttl):
        try:
            yield
        finally:
            r.delete(key)
        return

    time.sleep(0.1)
```

---

#### Execução após correção

```
User@DESKTOP-M0Q2F5Q MINGW64 /d/github/lab04/t6_concorrencia (master)
$ python com_concorrencia.py

Saldo inicial: R$1000
  [Processo-B] transferiu R$300. Saldo atual: R$700
  [Processo-A] transferiu R$200. Saldo atual: R$500

Saldo final no Redis: R$500
Resultado: R$500 correto
```

Agora os processos **aguardam o lock e executam de forma serializada**, eliminando a race condition.

---

- **Uso de multiprocessing ao invés de threading:** o CPython tem o GIL, que impede duas threads de executarem bytecode Python ao mesmo tempo dentro do mesmo processo. Com `threading`, o Python intercala as threads mas não as roda de verdade em paralelo — a race condition pode não aparecer de forma consistente. Com `multiprocessing` cada processo tem memória separada e GIL próprio, então a execução é realmente paralela, a race condition aparece de forma reproduzível e reflete com fidelidade o que acontece em servidores distintos num sistema distribuído.

- **Diferença de distributed_lock vs threading.Lock():** um `threading.Lock()` existe na memória de um único processo — processo A não enxerga o lock do processo B. O `distributed_lock` usa o Redis Cloud como árbitro externo: quando o Processo-A grava `lock:conta:saldo` com `SET NX`, o Redis garante atomicamente que só um processo consegue fazer isso, independente de quantos processos ou máquinas tentem ao mesmo tempo. É a diferença entre um cadeado por processo e um cadeado num servidor central que todos consultam.

- **TTL e risco residual:** o parâmetro `ex=5` existe para o caso em que o Processo-A trava dentro da seção crítica antes do `finally` — sem o TTL, o `r.delete(key)` nunca executaria e o lock ficaria preso para sempre, bloqueando todos os outros processos indefinidamente. O Redis expira a chave automaticamente após 5 segundos, quebrando esse deadlock. O TTL resolve um problema mas cria outro: se a operação dentro da seção crítica levar mais de 5 segundos, o Redis expira a chave enquanto o Processo-A ainda está rodando. Nesse momento o Processo-B consegue adquirir o lock — e agora os dois processos estão na seção crítica simultaneamente, que é exatamente o cenário que o lock deveria prevenir.

- **Referências**
- Python multiprocessing — documentação oficial: <https://docs.python.org/3/library/multiprocessing.html>

## Tarefa 7 — Transparência de Falha e seus Limites

- **Falácia violada:** o `anti_pattern.py` viola diretamente a segunda falácia de Peter Deutsch: *"a latência é zero"*. A função `get_user()` parece uma consulta local — sem `async`, sem timeout, sem `Optional` no retorno — mas por baixo faz uma chamada de rede que pode levar 800ms ou nunca retornar. O chamador não tem como saber disso pela assinatura da função, então não tem como se proteger. O `print(user["name"])` na linha seguinte assume que `user` sempre vai existir, o que gera `KeyError` silencioso se a chamada remota falhar e retornar `None`.

- **Por que `async/await` quebra a transparência — e por que isso é correto:** Transparência em sistemas distribuídos tenta fazer chamadas remotas parecerem chamadas locais simples. O problema é que operações remotas têm latência real e podem falhar, e esconder isso cria o anti-pattern mostrado na Parte B: a função parece trivial, mas pode demorar muito ou falhar inesperadamente. `async/await` quebra essa ilusão de propósito. O `await` deixa claro no código que a operação pode suspender a execução (ou seja, não é instantânea). Já o `async`, o `timeout=2.0` e o retorno `Optional[dict]` tornam explícito no contrato da função que a chamada pode demorar ou não retornar resultado. Isso é um bom design porque evita esconder o custo de uma operação remota. Quando a função parece local, quem chama não sabe que precisa lidar com latência, timeout ou falhas. Com `async/await`, essas possibilidades ficam explícitas e o próprio Python exige o uso de `await`, reduzindo o risco de usar a função de forma incorreta.

## Bloco de Reflexão

### Questão 1

Acesso e localização não apresentaram dificuldade real de implementação. No acesso, o padrão Strategy com uma factory lendo `CONFIG_BACKEND` do ambiente já resolve o problema, o cliente chama `repo.get("database")` e não sabe, nem precisa saber, se o dado veio de um arquivo local ou de uma requisição HTTP. Localização funciona da mesma forma, o `ServiceLocator` lê `USER_SERVICE_URL` e devolve o endereço certo. Migração exige um Redis externo, porém o estado sai do processo e vai para o store (Redis), e qualquer instância que conheça a chave consegue continuar de onde parou. Relocação complica um pouco porque a conexão WebSocket precisa continuar ativa durante a transição, então o `_message_buffer` segura as mensagens enviadas no intervalo do `MIGRATING`, mas os estados são explícitos e o fluxo é possível acompanhar. Concorrência tem sua parte complicada, o `SET NX` serializa os processos e o problema da recursão no fallback aparece claramente quando se traça o fluxo de execução. Falha talvez seja a mais explicita das sete: `async/await` com `Optional` no retorno simplesmente expõe o que sempre foi verdade — a operação pode não voltar.

Replicação é outra história. O que torna ela difícil não é a implementação em si, é que o sistema quebra sem avisar. O *replication lag* não gera exceção nenhuma: a escrita vai para master, a leitura cai numa réplica que ainda não aplicou aquela entrada do WAL, e o cliente recebe um dado desatualizado sem nenhum sinal de que algo está errado. Não tem como detectar isso pelo comportamento externo do sistema. As soluções conhecidas resolvem o sintoma e introduzem outro problema — rastrear a posição no log e exigir que a réplica esteja sincronizada antes de responder elimina a leitura suja, mas em períodos de lag alto praticamente todo o tráfego volta pro master, que é exatamente o cenário que a replicação deveria evitar. O *sticky session* pós-escrita é mais tolerável na prática, mas a janela de tempo é arbitrária e qualquer estimativa errada do lag médio faz o problema reaparecer. No código da Tarefa 5 isso se manifestou de forma menor mas representativa: o fallback com recursão dentro do `except` parecia razoável falhou na réplica, tenta no master até que em falha total o `query()` chamava a si mesmo indefinidamente até o `RecursionError`. Chamar `connect(self.master_dsn)` direto quebrou o ciclo. É um caso pequeno, mas o padrão é o mesmo: na replicação, os problemas aparecem nos casos que o código não testou.

### Questão 2

O Spotify é um caso interessante de transparência de localização e replicação aplicadas de forma agressiva. Enquanto há conexão, a playlist aparece completa, o app não diferencia o que está no armazenamento local do que está sendo servido pelos servidores. O resultado é que músicas que nunca foram baixadas aparecem lado a lado com as que estão em cache, sem nenhuma marcação. Quando a rede cai, o modo offline assume e parte da playlist simplesmente some. Não tem erro, não tem aviso, o app só para de mostrar o que não consegue mais buscar. O usuário só descobre o que estava realmente armazenado depois que a conexão foi embora. Esse comportamento conecta diretamente com o problema do `anti_pattern.py` da Tarefa 7: esconder a origem do dado funciona bem quando a rede está disponível, mas remove do usuário qualquer capacidade de agir antes da falha. Nesse caso define transparência de localização exatamente como isso, ocultar onde o recurso está fisicamente, só que aqui o custo aparece na hora errada. Um retorno `Optional` na camada de acesso, como feito no `fetch_user_remote`, já forçaria o sistema a reconhecer que nem todo dado está garantido, o que abriria espaço para marcar faixas como indisponíveis offline antes de a conexão cair.

### Questão 3

No Lab 02, o `async/await` entrou como solução de escalabilidade: o servidor precisava atender 10 clientes simultâneos sem abrir uma thread por conexão, então o Event Loop assumiu o controle — cada corrotina chega no `await asyncio.sleep(5)`, cede a execução, e o loop passa para a próxima sem nenhum context switch de SO. O resultado observado foi a mesma carga, fração do consumo de memória do `server.py` multithread.

Na Tarefa 7 o mesmo `async` aparece, mas o motivo é outro. O `get_user()` do `anti_pattern.py` parece uma consulta local, sem timeout, sem `Optional` no retorno, sem nada que avise que aquilo cruza a rede. Quando a chamada demora 800ms ou retorna `None`, o `print(user["name"])` na linha seguinte quebra silenciosamente e o chamador não tinha como saber que precisava se proteger. O `fetch_user_remote` resolve isso não por ser mais robusto internamente, mas porque o `async` na assinatura faz o Python recusar compilar qualquer chamada sem `await` o contrato fica visível antes de rodar. O `Optional[dict]` e o `timeout=2.0` explícito completam isso, quem chama a função não consegue ignorar que o resultado pode não vir. Nos dois laboratórios o mecanismo é o mesmo, mas no Lab 02 o `await` existe porque a operação é lenta e não pode bloquear o loop; na Tarefa 7 ele existe para que a lentidão não fique escondida de quem chama.

### Questão 4

O GIL é um mutex interno do CPython que impede duas threads de executarem bytecode ao mesmo tempo dentro do mesmo processo. Na prática, mesmo usando `threading`, o interpretador serializa o acesso — as threads se revezam, não rodam em paralelo de verdade. Para uma race condition aparecer de forma explicita, os dois fluxos precisam acessar o mesmo recurso simultaneamente, e o GIL quebra isso antes mesmo de qualquer lógica de lock entrar em cena.

O `multiprocessing` resolve porque cada processo carrega seu próprio interpretador e seu próprio GIL. O Processo-A e o Processo-B passam a rodar de fato ao mesmo tempo, e ambos chegam no `r.set("conta:saldo", saldo - valor)` sem nenhuma coordenação entre eles — um lê o saldo, o outro lê o mesmo saldo, cada um subtrai o seu valor e grava de volta, e o resultado final reflete só uma das operações. Com threads isso seria difícil de observar de forma consistente, o que tornaria o experimento do `sem_concorrencia.py` pouco confiável como demonstração.

### Questão 5

As complicações mais concretas apareceram no código em si. Na Tarefa 5 (`t5_replicacao/replicacao_transparente.py`), a lógica de fallback para o master estava dentro de um bloco `except`, e o método `query()` se chamava recursivamente quando a réplica falhava. Rastreando o fluxo: o `except` disparava `query()`, que internamente chamava `connect()`, que falhava novamente, retornando ao `except` — o ciclo se fechava até estourar um `RecursionError`. A correção foi substituir a chamada recursiva por `connect(self.master_dsn)` diretamente, quebrando o loop sem comprometer a semântica de failover.

Na Tarefa 4 (`t4_relocacao/relocacao_websocket.py`), entender o propósito do `_message_buffer` não foi imediato. A leitura do fluxo de estados esclareceu: durante `MIGRATING`, a conexão WebSocket do cliente permanece ativa, então descartar mensagens nesse intervalo quebraria a transparência de relocação que o restante do código tenta manter. O buffer retém essas mensagens até a transição concluir e o estado retornar a `CONNECTED`.

O provisionamento do Redis Cloud foi direto, utilizando o plano Essentials gratuito na região **South America (São Paulo) sa-east-1** e armazenando as credenciais no arquivo `.env`. O único detalhe que exigiu atenção foi definir `ssl=False` na função `get_redis()`, pois sem isso a conexão falhava com o erro `[SSL: WRONG_VERSION_NUMBER]`, já que o plano gratuito não oferece suporte a TLS. Como o próprio laboratório já apontava essa limitação, identificar a solução foi rápido: bastou ajustar o parâmetro no `get_redis()` dentro do `teste_conexao_redis.py`.
