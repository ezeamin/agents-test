import os
import json
import sys
import boto3
from io import StringIO
from datetime import datetime
from dotenv import load_dotenv
from strands import Agent as StrandsAgent
from strands.models.bedrock import BedrockModel
from tools.tools import get_customer_profile, check_credit_limit, issue_card

load_dotenv()


class Agent(StrandsAgent):
    """Agente de ventas usando Strands + AWS Bedrock"""

    def __init__(self, customer_id: str, system_prompt: str):
        self.customer_id = customer_id
        self.conversation_trace = []  # Guardar trace completo

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
        Procesa un mensaje del usuario y retorna solo el texto final del agente.
        Captura toda la ejecución (incluyendo prints) en el trace.
        """
        # Guardar mensaje del usuario en trace
        self.conversation_trace.append({
            "timestamp": datetime.now().isoformat(),
            "role": "user",
            "content": user_message
        })

        # Capturar stdout para guardar en trace pero no mostrarlo
        original_stdout = sys.stdout
        captured_output = StringIO()

        try:
            # Redirigir stdout temporalmente
            sys.stdout = captured_output

            # Ejecutar agente
            response = self(user_message)

        finally:
            # Restaurar stdout
            sys.stdout = original_stdout

        # Obtener lo que Strands imprimió
        raw_output = captured_output.getvalue()

        # Parsear solo el texto final limpio
        clean_response = self._parse_response(response)

        # Guardar respuesta del agente en trace (con raw output completo)
        self.conversation_trace.append({
            "timestamp": datetime.now().isoformat(),
            "role": "assistant",
            "content": clean_response,
            "raw_output": raw_output,  # Guardar también el output crudo con tools
            "response_type": str(type(response))
        })

        return clean_response

    def _parse_response(self, response) -> str:
        """
        Parsea la respuesta de Strands para extraer solo el mensaje del agente.
        Elimina logs de tools y duplicados.
        """
        # Si response es una lista o dict, extraer el texto
        if isinstance(response, dict):
            response = response.get('content', response.get('text', str(response)))
        elif isinstance(response, list):
            # Extraer solo bloques de texto
            text_blocks = [block.get('text', '') for block in response if isinstance(block, dict) and block.get('type') == 'text']
            response = '\n'.join(text_blocks)

        # Convertir a string si no lo es
        response = str(response)

        # Eliminar líneas que empiezan con "Tool #"
        lines = response.split('\n')
        clean_lines = [line for line in lines if not line.strip().startswith('Tool #')]

        # Unir y limpiar
        clean_response = '\n'.join(clean_lines).strip()

        return clean_response

    def save_trace(self, filename: str = None):
        """Guarda el trace completo de la conversación en JSON"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"traces/conversation_{self.customer_id}_{timestamp}.json"

        # Crear directorio traces si no existe
        os.makedirs("traces", exist_ok=True)

        trace_data = {
            "customer_id": self.customer_id,
            "conversation": self.conversation_trace,
            "total_messages": len(self.conversation_trace),
            "created_at": datetime.now().isoformat()
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(trace_data, f, indent=2, ensure_ascii=False)

        return filename
