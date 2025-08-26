# MCP Client for Casino Promotions

This project implements an MCP client that connects to an Ollama-hosted `gpt-oss:20b` model and exposes two tools for answering players' questions about casino promotions.

- Formal tone, promotions-only scope.
- All answers must be grounded strictly on tool outputs.

## Requirements
- Python 3.10+
- Ollama running locally with the `gpt-oss:20b` model pulled.

## Environment
Create a `.env` file or set environment variables:

- OLLAMA_HOST=http://localhost:11434
- MODEL=gpt-oss:20b
- STRAPI_TOKEN=... (optional if your tools call remote APIs; not used in this offline sample)
 - OLLAMA_API_BASE=http://localhost:11434  # Requerido por ADK/LiteLLM (ollama_chat)

## Run (with uv)
Use uv for fast, reproducible environments on Windows PowerShell:

```powershell
# Install uv if needed
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { iwr https://astral.sh/uv/install.ps1 -UseBasicParsing | iex }

# Create virtual env and install deps
uv venv
uv pip install -e .[dev]

# Run tests (optional)
uv run -m pytest

# Start the MCP client REPL
uv run -m mcp_client.main
```

## Tests
```powershell
uv run -m pytest
```

## Ejecutar con ADK (ollama_chat)
ADK puede cargar el agente desde `jgl_mcp_client/root_agent.py` (símbolo `root_agent`). Asegúrate de:

- Tener Ollama en ejecución y el modelo con soporte de tools.
- Tener `OLLAMA_API_BASE` apuntando a tu servidor Ollama.

```powershell
# Opcional: activar venv si usas uno externo
$venv = "$env:USERPROFILE\.venvs\jgl_mcp_client"
& "$venv\Scripts\python.exe" -m pip show google-adk | Out-Null; if ($LASTEXITCODE -ne 0) { uv pip install -p "$venv\Scripts\python.exe" google-adk litellm }

# Ejecutar el servidor web de ADK desde el directorio padre que contiene el paquete
$Env:OLLAMA_API_BASE = "http://localhost:11434"
adk web jgl_mcp_client
```

## Notes
- This sample ships with in-memory mock data to demonstrate tool behavior without external APIs.
- Replace the mock data layer with real integrations as needed.
