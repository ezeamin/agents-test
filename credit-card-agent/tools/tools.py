import json

def load_data(filename):
    """Carga archivos JSON de data/"""
    with open(f'data/{filename}', 'r', encoding='utf-8') as f:
        return json.load(f)

def get_customer_profile(customer_id: str) -> dict:
    """Obtiene el perfil completo del cliente"""
    customers = load_data('customers.json')
    
    if customer_id in customers:
        return {
            "success": True,
            "data": customers[customer_id]
        }
    return {"success": False, "error": "Cliente no encontrado"}

def check_credit_limit(customer_id: str) -> dict:
    """Obtiene el límite de crédito pre-aprobado"""
    customers = load_data('customers.json')
    
    if customer_id in customers:
        customer = customers[customer_id]
        products = load_data('products.json')
        currency = products[customer['country']]['currency']
        
        return {
            "success": True,
            "limit": customer['credit_limit'],
            "currency": currency
        }
    return {"success": False, "error": "Cliente no encontrado"}

def issue_card(customer_id: str) -> dict:
    """Emite la tarjeta virtual"""
    customers = load_data('customers.json')
    
    if customer_id in customers:
        return {
            "success": True,
            "card_number": "**** **** **** 1234",
            "status": "active",
            "message": "Tarjeta virtual emitida"
        }
    return {"success": False, "error": "Cliente no encontrado"}

# Tool definitions para Bedrock
TOOLS = [
    {
        "name": "get_customer_profile",
        "description": "Obtiene el perfil del cliente con nombre, producto que vio, dirección. Úsalo al inicio de la conversación.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "ID del cliente (COL_001 o MEX_001)"
                }
            },
            "required": ["customer_id"]
        }
    },
    {
        "name": "check_credit_limit",
        "description": "Obtiene el límite de crédito pre-aprobado. Úsalo en la fase de propuesta para revelar el cupo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "ID del cliente"
                }
            },
            "required": ["customer_id"]
        }
    },
    {
        "name": "issue_card",
        "description": "Emite la tarjeta virtual. SOLO úsalo cuando el cliente acepte en el cierre positivo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "ID del cliente"
                }
            },
            "required": ["customer_id"]
        }
    }
]

# Mapeo de funciones
TOOL_FUNCTIONS = {
    "get_customer_profile": get_customer_profile,
    "check_credit_limit": check_credit_limit,
    "issue_card": issue_card
}
