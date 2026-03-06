import os
import boto3
from dotenv import load_dotenv
from strands import Agent as StrandsAgent
from strands.models.bedrock import BedrockModel
from tools.tools import get_customer_profile, check_credit_limit, issue_card

load_dotenv()


class Agent(StrandsAgent):
    """Agente de ventas usando Strands + AWS Bedrock"""

    def __init__(self, customer_id: str, system_prompt: str):
        self.customer_id = customer_id

        boto_session = boto3.Session(
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            aws_session_token=os.getenv('AWS_SESSION_TOKEN'),
        )
        model = BedrockModel(
            model_id=os.getenv('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-20250514-v1:0'),
            boto_session=boto_session,
            max_tokens=2000,
        )

        # Inicializar el agente de Strands con configuración Bedrock
        super().__init__(
            model=model,
            system_prompt=system_prompt.format(customer_id=customer_id),
            tools=[get_customer_profile, check_credit_limit, issue_card],
        )

    def chat(self, user_message: str) -> str:
        """
        Procesa un mensaje del usuario y retorna la respuesta del agente.
        Strands maneja automáticamente la orquestación de tools.
        """
        response = self(user_message)
        return str(response)
