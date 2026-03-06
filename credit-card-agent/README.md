# 💳 Agentes de Venta - Tarjetas de Crédito

Sistema de agentes conversacionales para venta de tarjetas usando AWS Bedrock.

## 🚀 Setup Rápido

### 1. Configurar credenciales AWS

Copia `.env.example` a `.env` y completa:

```bash
cp .env.example .env
```

Edita `.env`:
```
AWS_ACCESS_KEY_ID=tu-access-key
AWS_SECRET_ACCESS_KEY=tu-secret-key
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Ejecutar

```bash
python main.py
```

## 🤖 Agentes

- **Sofia** 🇨🇴 - Colombia (formal "usted", millas para vuelos)
- **Miguel** 🇲🇽 - México (informal "tú", MSI + cashback)

## 👥 Clientes de Prueba

- `COL_001` - Carlos Ramírez (Colombia)
- `MEX_001` - Andrés Torres (México)

## 📁 Estructura

```
credit-card-agent/
├── agents/          # Agentes (Sofia, Miguel)
├── tools/           # Herramientas (tools + funciones)
├── data/            # Datos mock (clientes, productos)
├── main.py          # Script principal
└── .env             # Credenciales AWS
```

## 🔧 Tools Disponibles

1. `get_customer_profile` - Datos del cliente
2. `check_credit_limit` - Límite pre-aprobado
3. `issue_card` - Emitir tarjeta virtual

## ⚠️ Requisitos AWS

- Bedrock habilitado en tu cuenta
- Modelo Claude habilitado en us-east-1
- Permisos IAM: `bedrock:InvokeModel`
