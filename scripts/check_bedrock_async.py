#!/usr/bin/env python3
"""
Reproduce la llamada a Bedrock con aiobotocore (async), igual que Pipecat.
Si este script FALLA con UnrecognizedClientException y check_bedrock.py (boto3) OK,
el fallo está en aiobotocore/contexto async. Si este script OK, el fallo está en Pipecat.
"""
import asyncio
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "src"))
os.chdir(root)
from dotenv import load_dotenv
load_dotenv(root + "/.env", override=True)


async def main():
    import aioboto3
    from botocore.exceptions import ClientError

    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    model = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    akid = os.getenv("AWS_ACCESS_KEY_ID", os.getenv("aws_access_key_id"))
    secret = os.getenv("AWS_SECRET_ACCESS_KEY", os.getenv("aws_secret_access_key"))
    token = os.getenv("AWS_SESSION_TOKEN", os.getenv("aws_session_token"))

    # Forzar env como hace el agente
    if akid:
        os.environ["AWS_ACCESS_KEY_ID"] = akid
    if secret:
        os.environ["AWS_SECRET_ACCESS_KEY"] = secret
    if token:
        os.environ["AWS_SESSION_TOKEN"] = token
    os.environ["AWS_REGION"] = region

    print("=== aiobotocore ConverseStream (mismo flujo que Pipecat) ===")
    print(f"  region={region} model={model} access_key={'set' if akid else 'NOT SET'}")

    session = aioboto3.Session()
    params = {
        "aws_access_key_id": akid,
        "aws_secret_access_key": secret,
        "aws_session_token": token,
        "region_name": region,
    }
    try:
        async with session.client("bedrock-runtime", **params) as client:
            response = await client.converse_stream(
                modelId=model,
                messages=[{"role": "user", "content": [{"text": "Di hola en una palabra."}]}],
            )
            async for _ in response.get("stream", []):
                break
            print("  OK  Primera respuesta recibida (aiobotocore async funciona).")
    except ClientError as e:
        err = e.response.get("Error", {})
        meta = e.response.get("ResponseMetadata", {})
        print(f"  ERROR Code={err.get('Code')} Message={err.get('Message')}")
        print(f"  RequestId={meta.get('RequestId')}")
        return 1
    except Exception as e:
        print(f"  ERROR {type(e).__name__}: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
