"""
Serviço de envio de mensagens WhatsApp via Twilio.

Requer no .env:
    TWILIO_ACCOUNT_SID
    TWILIO_AUTH_TOKEN
    TWILIO_WHATSAPP_FROM   (ex: whatsapp:+14155238886)
"""
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from app.config import settings


class WhatsAppService:
    def __init__(self):
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        if self._client is None:
            if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
                raise RuntimeError(
                    "Credenciais da Twilio não configuradas (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN)."
                )
            self._client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        return self._client

    def enviar_mensagem(self, telefone_destino: str, mensagem: str) -> dict:
        """
        Envia mensagem via WhatsApp usando a API da Twilio.
        telefone_destino: número em formato E.164, ex: +5511999999999
        Retorna dict com sucesso, sid e erro (se houver).
        """
        destino = telefone_destino if telefone_destino.startswith("whatsapp:") else f"whatsapp:{telefone_destino}"

        try:
            msg = self.client.messages.create(
                from_=settings.TWILIO_WHATSAPP_FROM,
                to=destino,
                body=mensagem,
            )
            return {"sucesso": True, "sid": msg.sid, "erro": None}
        except TwilioRestException as exc:
            return {"sucesso": False, "sid": None, "erro": str(exc)}
        except RuntimeError as exc:
            return {"sucesso": False, "sid": None, "erro": str(exc)}


whatsapp_service = WhatsAppService()


# --------------------------- Templates de mensagem ---------------------------

def mensagem_lembrete_devolucao(nome_cliente: str, material: str, prazo: str) -> str:
    return (
        f"Olá, {nome_cliente}! 👋\n"
        f"Lembrete: o material \"{material}\" que você retirou deve ser devolvido até {prazo}.\n"
        f"Qualquer dúvida, estamos à disposição."
    )


def mensagem_atraso(nome_cliente: str, material: str, prazo: str) -> str:
    return (
        f"Olá, {nome_cliente}. Identificamos que o material \"{material}\" "
        f"(prazo de devolução {prazo}) ainda não foi devolvido.\n"
        f"Por favor, providencie a devolução o quanto antes ou entre em contato conosco."
    )


def mensagem_confirmacao_devolucao(nome_cliente: str, material: str) -> str:
    return (
        f"Olá, {nome_cliente}! ✅ Confirmamos o recebimento da devolução do material "
        f"\"{material}\". Obrigado!"
    )