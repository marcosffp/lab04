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