import json
from strands.tools import tool

def load_data(filename):
    """Carga archivos JSON de data/"""
    with open(f'data/{filename}', 'r', encoding='utf-8') as f:
        return json.load(f)


@tool
def get_customer_profile(customer_id: str) -> dict:
    """
    Obtiene el perfil del cliente con nombre, producto que vio, dirección y límite de crédito.
    Úsalo al inicio de la conversación para personalizar la apertura.
    
    Args:
        customer_id: ID del cliente (COL_001 para Colombia o MEX_001 para México)
    
    Returns:
        Diccionario con success=True y data con el perfil completo del cliente
    """
    customers = load_data('customers.json')
    
    if customer_id in customers:
        return {
            "success": True,
            "data": customers[customer_id]
        }
    return {"success": False, "error": "Cliente no encontrado"}


@tool
def check_credit_limit(customer_id: str) -> dict:
    """
    Obtiene el límite de crédito pre-aprobado del cliente.
    Úsalo en la fase de propuesta cuando necesites revelar el cupo exacto al cliente.
    
    Args:
        customer_id: ID del cliente
    
    Returns:
        Diccionario con success=True, limit (monto) y currency (COP o MXN)
    """
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


@tool
def issue_card(customer_id: str) -> dict:
    """
    Emite la tarjeta virtual para uso inmediato del cliente.
    SOLO úsalo cuando el cliente acepte explícitamente la tarjeta en el cierre positivo.
    NO lo uses antes de que el cliente diga que sí quiere la tarjeta.
    
    Args:
        customer_id: ID del cliente
    
    Returns:
        Diccionario con success=True, card_number, status y mensaje de confirmación
    """
    customers = load_data('customers.json')
    
    if customer_id in customers:
        return {
            "success": True,
            "card_number": "**** **** **** 1234",
            "status": "active",
            "message": "Tarjeta virtual emitida"
        }
    return {"success": False, "error": "Cliente no encontrado"}
