# src/helpers/tools.py
import json
import random
from pipecat.adapters.schemas.tools_schema import ToolsSchema

# --- MOCK DATA ---
MOCK_PRODUCTS = [
    {"id": "1", "name": "Velox Runner", "category": "running", "price": 150, "stock": True},
    {"id": "2", "name": "Strata Tee", "category": "clothing", "price": 50, "stock": True}
]

# --- TOOL DEFINITIONS ---

async def identify_user(params, id: str):
    """Identifica al usuario por su ID / documento de identidad."""
    # Mock: All IDs starting with '1' are valid
    if id.startswith("1"):
        user = {"id": id, "name": "Juan Pérez", "email": "juan@example.com"}
        await params.result_callback(f"Usuario identificado: {json.dumps(user)}")
    else:
        await params.result_callback("Usuario no identificado, indica al cliente que debe registrarse.")

async def search_products(params, category: str = None, price_max: float = None):
    """Busca productos en el catálogo por categoría o precio máximo."""
    results = MOCK_PRODUCTS
    if category:
        results = [p for p in results if p["category"] == category]
    if price_max:
        results = [p for p in results if p["price"] <= price_max]
    await params.result_callback(json.dumps(results))

async def check_for_size(params, product_id: str, size: str):
    """Verifica si el producto tiene el tamaño solicitado (talla)."""
    await params.result_callback(json.dumps({"product_id": product_id, "size": size, "available": True}))

async def add_to_cart(params, product_id: str, size: str, quantity: int):
    """Agrega un producto al carrito de compras."""
    await params.result_callback("Producto agregado al carrito exitosamente.")

async def apply_promo(params, product_id: str, current_price: float = None, new_price: float = None, trial_period: bool = False):
    """Aplica una promoción especial o garantía de prueba."""
    response = {"product_id": product_id, "authorized": True, "message": "Promoción aplicada correctamente."}
    if trial_period:
        response["message"] += " Garantía de 30 días activada."
    await params.result_callback(json.dumps(response))

async def order_cart(params, address_index: int, card_last_4: str):
    """Realiza el pedido del carrito."""
    order_id = random.randint(1000, 9999)
    await params.result_callback(f"Pedido procesado con éxito. ID de seguimiento: {order_id}")

async def get_order_status(params, order_id: str):
    """Obtiene el estado de una orden por su ID."""
    await params.result_callback(json.dumps({"order_id": order_id, "status": "CONFIRMED", "message": "Tu pedido llegará mañana."}))

async def final_survey(params, problem_solved: int, information_useful: int, agent_attitude: int, recommendability: int):
    """Registra la encuesta de satisfacción final."""
    await params.result_callback("Encuesta registrada. Agradece al cliente y despídete.")

# --- SCHEMA REGISTRATION ---
tools_list = [
    identify_user,
    search_products,
    check_for_size,
    add_to_cart,
    apply_promo,
    order_cart,
    get_order_status,
    final_survey
]

tools_schema = ToolsSchema(standard_tools=tools_list)