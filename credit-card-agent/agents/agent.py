import os
import json
import boto3
from dotenv import load_dotenv
from tools.tools import TOOLS, TOOL_FUNCTIONS

load_dotenv()

class Agent:
    """Agente de ventas usando AWS Bedrock"""
    
    def __init__(self, customer_id: str, system_prompt: str):
        self.customer_id = customer_id
        self.system_prompt = system_prompt.format(customer_id=customer_id)
        
        # Cliente Bedrock
        self.bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            aws_session_token=os.getenv('AWS_SESSION_TOKEN')
        )
        
        self.model_id = os.getenv('BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20241022-v2:0')
        self.messages = []
    
    def _execute_tool(self, tool_name: str, tool_input: dict):
        """Ejecuta una tool y retorna el resultado"""
        if tool_name in TOOL_FUNCTIONS:
            return TOOL_FUNCTIONS[tool_name](**tool_input)
        return {"error": f"Tool {tool_name} no encontrada"}
    
    def chat(self, user_message: str) -> str:
        """Procesa un mensaje y retorna la respuesta"""
        # Agregar mensaje del usuario
        self.messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Request a Bedrock
        request = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "system": self.system_prompt,
            "messages": self.messages,
            "tools": TOOLS
        }
        
        response = self.bedrock.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request)
        )
        
        response_body = json.loads(response['body'].read())
        
        # Procesar tool uses
        while response_body.get('stop_reason') == 'tool_use':
            tool_results = []
            assistant_content = response_body['content']
            
            # Ejecutar tools
            for block in assistant_content:
                if block['type'] == 'tool_use':
                    result = self._execute_tool(block['name'], block['input'])
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block['id'],
                        "content": json.dumps(result)
                    })
            
            # Agregar respuesta del asistente
            self.messages.append({
                "role": "assistant",
                "content": assistant_content
            })
            
            # Agregar resultados de tools
            self.messages.append({
                "role": "user",
                "content": tool_results
            })
            
            # Continuar conversación
            request['messages'] = self.messages
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request)
            )
            response_body = json.loads(response['body'].read())
        
        # Extraer respuesta final
        text = ""
        for block in response_body['content']:
            if block['type'] == 'text':
                text += block['text']
        
        # Guardar respuesta del asistente
        self.messages.append({
            "role": "assistant",
            "content": response_body['content']
        })
        
        return text
