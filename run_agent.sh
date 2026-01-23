#!/bin/bash
# Script para ejecutar el agente y guardar todos los logs en un archivo

# Crear directorio de logs si no existe
mkdir -p logs

# Ejecutar el agente y redirigir stderr a un archivo mientras se muestra en consola
uv run python src/agent.py 2>&1 | tee logs/pipeline_debug.log
