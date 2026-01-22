import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv


def main():
    # ─────────────────────────────────────────────
    # Cargar .env desde la carpeta raíz
    # ─────────────────────────────────────────────
    BASE_DIR = Path(__file__).resolve().parent.parent
    load_dotenv(BASE_DIR / ".env")

    voice_model = os.getenv("CURRENT_VOICE")
    voice_config = os.getenv("CURRENT_VOICE_CONFIG")
    port = os.getenv("PIPER_PORT", "5002")

    if not voice_model or not voice_config:
        raise RuntimeError(
            "Faltan variables en el .env: CURRENT_VOICE y/o CURRENT_VOICE_CONFIG"
        )

    voice_model = BASE_DIR / "voice" / voice_model
    voice_config = BASE_DIR / "voice" / voice_config

    print("Usando modelo de voz:", voice_model)
    print("Usando config de voz:", voice_config)

    cmd = [
        "uv",
        "run",
        "python3",
        "-m",
        "piper.http_server",
        "--model",
        str(voice_model),
        "--data-dir",
        str(voice_config),
        "--port",
        str(port),
    ]

    print("🚀 Levantando Piper TTS")
    print("▶", " ".join(cmd))

    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
