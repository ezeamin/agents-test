#!/usr/bin/env python3
import os
import json
from dotenv import load_dotenv
from agents.agent import Agent
from agents.sofia_prompt import SOFIA_PROMPT
from agents.miguel_prompt import MIGUEL_PROMPT

load_dotenv()

def select_agent(customer_id: str):
    """Selecciona el agente según el país del cliente"""
    with open('data/customers.json', 'r') as f:
        customers = json.load(f)
    
    if customer_id not in customers:
        raise ValueError(f"Cliente {customer_id} no encontrado")
    
    country = customers[customer_id]['country']
    
    if country == 'Colombia':
        print(f"🇨🇴 Iniciando Sofia para {customers[customer_id]['name']}")
        return Agent(customer_id, SOFIA_PROMPT)
    else:
        print(f"🇲🇽 Iniciando Miguel para {customers[customer_id]['name']}")
        return Agent(customer_id, MIGUEL_PROMPT)

def main():
    # Verificar credenciales
    if not os.getenv('AWS_ACCESS_KEY_ID'):
        print("❌ Error: Configura tus credenciales AWS en el archivo .env")
        return
    
    print("\n" + "="*60)
    print("💳 SISTEMA DE AGENTES DE VENTA")
    print("="*60)
    
    # Mostrar clientes disponibles
    with open('data/customers.json', 'r') as f:
        customers = json.load(f)
    
    print("\n📋 Clientes disponibles:\n")
    for cid, data in customers.items():
        flag = "🇨🇴" if data['country'] == 'Colombia' else "🇲🇽"
        print(f"{flag} {cid}: {data['name']} - Viendo: {data['product_viewed']}")
    
    # Seleccionar cliente
    customer_id = input("\n🎯 ID del cliente: ").strip()
    
    try:
        agent = select_agent(customer_id)
        print("\n" + "─"*60)
        print("📞 CONVERSACIÓN INICIADA")
        print("─"*60)
        print("💡 Escribe 'salir' para terminar\n")
        
        # Loop de conversación
        while True:
            user_input = input("👤 Tú: ").strip()
            
            if user_input.lower() in ['salir', 'exit']:
                # Guardar trace antes de salir
                trace_file = agent.save_trace()
                print(f"\n💾 Conversación guardada en: {trace_file}")
                print("👋 Conversación terminada\n")
                break
            
            if not user_input:
                continue
            
            response = agent.chat(user_input)
            print(f"\n🤖 Agente: {response}\n")
    
    except Exception as e:
        print(f"\n❌ Error: {e}\n")

if __name__ == "__main__":
    main()