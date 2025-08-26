# MCP Client for Casino Promotions

This project implements an ADK-powered agent that uses OpenAI's `gpt-5-nano` model and exposes MCP tools for answering players' questions about casino promotions.

- Formal tone, promotions-only scope.
- All answers must be grounded strictly on tool outputs.

## Requirements
- Python 3.10+
- OpenAI API key
- MCP Server running on localhost:8000 (for promotion tools)

## Environment
Create a `.env` file based on `.env.example`:

```env
# OpenAI Configuration
MODEL=gpt-5-nano
OPENAI_API_KEY=your-openai-api-key-here
# Optional: Custom API endpoint
OPENAI_API_BASE=https://api.openai.com/v1

# MCP Server Configuration
MCP_SERVER_URL=http://localhost:8000
```

## Installation & Setup

1. **Clone and setup virtual environment:**
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment  
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -e .[dev]
```

2. **Install ADK (Agent Development Kit):**
```powershell
pip install google-adk litellm
```

3. **Configure environment:**
   - Copy `.env.example` to `.env`
   - Add your OpenAI API key

## Running the Agent

Start the ADK web server:
```powershell
.\.venv\Scripts\Activate.ps1; .\.venv\Scripts\adk.exe web jgl_mcp_client --port 8001
```

Then open your browser to: `http://localhost:8001`

## Testing
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run tests
pytest
```

## Project Structure
```
jgl_mcp_client/
├── jgl_mcp_client/           # ADK agent definition
│   ├── root_agent.py         # Main agent with OpenAI integration
│   └── agent/__init__.py     # ADK export point
├── mcp_client/               # MCP tools
│   ├── tools/                # Promotion tools
│   │   ├── list_promotions_by_country.py
│   │   └── get_promotion_by_id.py
│   └── schemas/              # JSON schemas
├── .env.example              # Environment template
└── pyproject.toml           # Project dependencies
```

## Features
- **ADK Integration**: Uses Google's Agent Development Kit for web UI
- **OpenAI GPT-5-nano**: Powered by latest OpenAI model via LiteLLM
- **MCP Tools**: Structured tools for casino promotion queries
- **Formal Responses**: Agent maintains professional tone
- **Scoped Functionality**: Only answers promotion-related questions

## Notes
- The agent connects to remote MCP tools running on `localhost:8000`
- All promotion data comes from external MCP server endpoints
- Agent refuses to answer non-promotion related questions
- Responses maintain a formal, professional tone suitable for casino players
