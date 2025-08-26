# MCP Client for Casino Promotions

This project implements an **ADK-powered agent** that uses OpenAI's `gpt-5-nano` model and exposes MCP tools for answering players' questions about casino promotions.

## 🎯 **What it does**
- **Formal Customer Service**: Maintains professional tone when responding to casino players
- **Promotion-Focused**: Only answers questions related to casino promotions
- **Data-Driven**: All answers are grounded strictly on real promotion data from MCP tools
- **Multi-Country Support**: Can provide promotions filtered by country (ISO-2 codes)
- **Detailed Promotion Info**: Fetches specific promotion details by ID

## 🏗️ **Architecture**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Casino Player │───▶│  ADK Web Agent   │───▶│  MCP Server     │
│                 │    │  (gpt-5-nano)    │    │  (localhost:8000│
│  Asks Questions │    │  Formal Responses│    │  Real Data)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🛠️ **Available Tools**
1. **`list_promotions_by_country`**: Get paginated list of promotions for a specific country
   - **Parameters**: `country` (ISO-2), `page`, `limit`, `include`, `sort`
   - **Returns**: Paginated list with promotion metadata
   
2. **`get_promotion_by_id`**: Fetch detailed information for a specific promotion
   - **Parameters**: `id` (integer), `include` (optional array)
   - **Returns**: Complete promotion details or not found message

## 📊 **Data Schema**
The MCP tools expect and return standardized promotion data:
```json
{
  "data": {
    "id": 123,
    "attributes": {
      "title": "Welcome Bonus",
      "content": "Get 100% match on your first deposit",
      "startDate": "2025-01-01",
      "endDate": "2025-12-31",
      "country": "CL",
      "slug": "welcome-bonus-cl"
    }
  }
}
```

## 🔌 **MCP Server Requirements**
The agent expects an MCP server running on `localhost:8000` with these endpoints:
- `POST /tools/list_promotions_by_country`
- `POST /tools/get_promotion_by_id`
- `POST /api/tools/list_promotions_by_country` (alternative)
- `POST /api/tools/get_promotion_by_id` (alternative)

## 🎮 **Example Interactions**
**Player**: *"Could you please provide me with the promotions available in Chile?"*  
**Agent**: *Calls `list_promotions_by_country` with `{"country": "CL"}` and provides formal response*

**Player**: *"I would like to know the details of promotion ID 123."*  
**Agent**: *Calls `get_promotion_by_id` with `{"id": 123}` and provides detailed information*

**Player**: *"What is the weather today?"*  
**Agent**: *"I am only able to provide information regarding casino promotions."*

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
.\.venv\Scripts\Activate.ps1; .\.venv\Scripts\adk.exe web casino_agent --port 8001
```

Then open your browser to: `http://localhost:8001`

## Testing
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run tests
pytest
```

## 📁 **Project Structure**
```
jgl_mcp_client/
├── .env.example              # Environment configuration template
├── .gitignore               # Git ignore rules (excludes .env, __pycache__, etc.)
├── pyproject.toml           # Python project dependencies and metadata
├── README.md                # This file
│
├── jgl_mcp_client/          # 🤖 ADK Agent Module
│   ├── root_agent.py        # Main agent: OpenAI config + conversation logic
│   └── agent/
│       └── __init__.py      # ADK export point (imports root_agent)
│
├── mcp_client/              # 🔧 MCP Tools Module  
│   ├── __init__.py          # Python package marker
│   ├── tools/               # Individual tool implementations
│   │   ├── __init__.py      # Python package marker
│   │   ├── data.py          # Mock data structures (for testing)
│   │   ├── list_promotions_by_country.py  # Tool: List promotions by country
│   │   └── get_promotion_by_id.py         # Tool: Get specific promotion
│   └── schemas/             # 📋 JSON Schema definitions
│       ├── list_promotions_by_country.json
│       └── get_promotion_by_id.json
│
└── tests/                   # 🧪 Unit tests (if any)
```

### 🔍 **Key Files Explained**
- **`root_agent.py`**: Contains the main agent logic, OpenAI model configuration, and conversation instructions
- **`tools/*.py`**: HTTP clients that connect to the MCP server and format responses
- **`schemas/*.json`**: Define the expected input/output structure for each tool
- **`.env`**: Contains sensitive configuration (API keys, server URLs) - not in git

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

## 🚀 **Getting Started Quickly**
1. Clone this repository
2. Copy `.env.example` to `.env` and add your OpenAI API key
3. Run the setup commands above
4. Start with: `.\.venv\Scripts\Activate.ps1; .\.venv\Scripts\adk.exe web casino_agent --port 8001`
5. Open `http://localhost:8001` in your browser

## 🔧 **Troubleshooting**
- **"Import errors"**: Make sure you've installed with `pip install -e .[dev]`
- **"Connection refused"**: Ensure MCP Server is running on `localhost:8000`
- **"Authentication failed"**: Check your OpenAI API key in `.env`
- **"Agent not responding"**: Verify ADK installation with `adk --version`

## 🤝 **Contributing**
This is a specialized agent for casino promotion queries. When contributing:
- Maintain the formal tone requirement
- Ensure all responses are data-driven from MCP tools
- Test with various country codes and promotion IDs
- Keep the scope strictly to promotion-related functionality

## 📄 **License**
This project is for internal use in casino customer service operations.
