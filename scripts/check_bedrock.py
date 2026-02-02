#!/usr/bin/env python3
"""
Diagnóstico de AWS Bedrock: reproduce la misma llamada que hace Pipecat
y muestra la respuesta completa de AWS (RequestId, Code, etc.).

Uso (desde la raíz del proyecto):
  uv run python scripts/check_bedrock.py

Asegúrate de tener .env con AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
AWS_SESSION_TOKEN (si aplica), AWS_DEFAULT_REGION.
"""
import os
import sys

# Cargar .env desde la raíz del proyecto
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "src"))
os.chdir(root)

from dotenv import load_dotenv
load_dotenv(override=True)

def main():
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError

    region = os.getenv("AWS_DEFAULT_REGION", os.getenv("aws_default_region", "us-east-1"))
    model_inference = "us.anthropic.claude-haiku-4-5-20251001-v1:0"  # perfil cross-region
    model_base = "anthropic.claude-haiku-4-5-20251001-v1:0"  # mismo modelo, sin perfil cross-region "us."

    session = boto3.Session(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", os.getenv("aws_access_key_id")),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", os.getenv("aws_secret_access_key")),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN", os.getenv("aws_session_token")),
        region_name=region,
    )

    print("=== 1) STS get_caller_identity ===")
    try:
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        print(f"  OK  Account={identity['Account']} Arn={identity['Arn'][:70]}...")
    except NoCredentialsError as e:
        print(f"  ERROR No hay credenciales: {e}")
        return 1
    except ClientError as e:
        err = e.response.get("Error", {})
        meta = e.response.get("ResponseMetadata", {})
        print(f"  ERROR Code={err.get('Code')} Message={err.get('Message')}")
        print(f"  RequestId={meta.get('RequestId')} HTTPStatusCode={meta.get('HTTPStatusCode')}")
        print(f"  Respuesta completa: {e.response}")
        return 1

    print("\n=== 2) Bedrock ConverseStream (mismo modelo que Pipecat) ===")
    print(f"  region={region} model={model_inference}")
    try:
        bedrock = session.client("bedrock-runtime", region_name=region)
        stream = bedrock.converse_stream(
            modelId=model_inference,
            messages=[{"role": "user", "content": [{"text": "Di hola en una palabra."}]}],
        )
        first = next(iter(stream), None)
        if first:
            print("  OK  Primera respuesta recibida (ConverseStream funciona con este modelo).")
        else:
            print("  OK  Stream vacío pero sin excepción.")
    except ClientError as e:
        err = e.response.get("Error", {})
        meta = e.response.get("ResponseMetadata", {})
        print(f"  ERROR Code={err.get('Code')} Message={err.get('Message')}")
        print(f"  RequestId={meta.get('RequestId')} HTTPStatusCode={meta.get('HTTPStatusCode')}")
        print(f"  Claves de response: {list(e.response.keys())}")
        print(f"  Respuesta completa (Error): {e.response.get('Error')}")
        print(f"  ResponseMetadata: {meta}")
        # Si falla el perfil "us.", probar modelo base en la región
        print("\n=== 3) Bedrock ConverseStream (modelo base en región, sin perfil us.) ===")
        try:
            stream2 = bedrock.converse_stream(
                modelId=model_base,
                messages=[{"role": "user", "content": [{"text": "Hi"}]}],
            )
            next(iter(stream2), None)
            print(f"  OK  Modelo base {model_base} funciona. El fallo puede ser del perfil de inferencia 'us.anthropic'.")
        except ClientError as e2:
            err2 = e2.response.get("Error", {})
            meta2 = e2.response.get("ResponseMetadata", {})
            print(f"  ERROR Code={err2.get('Code')} Message={err2.get('Message')} RequestId={meta2.get('RequestId')}")
        return 1
    except Exception as e:
        print(f"  ERROR {type(e).__name__}: {e}")
        return 1

    print("\nTodo OK: credenciales y Bedrock ConverseStream responden correctamente.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
