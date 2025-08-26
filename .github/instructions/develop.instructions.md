---
applyTo: '**'
---

# 📌 Project Context
We are building an **MCP Client** that connects to **`gpt-oss:20b`** running with **Ollama**.  
This client will serve as an agent that answers **casino players' questions about promotions**.  

---

# 🎯 Goals
- Connect to `gpt-oss:20b` through Ollama.
- Expose and manage the predefined **promotion-related tools**.
- Ensure the agent:
  - Responds **only** using data provided by the tools.
  - Uses a **formal tone** when addressing players.
  - Refuses to answer any request outside the scope of promotions.

---

# 🔐 Configuration
Environment variables (example):
OLLAMA_HOST=http://localhost:11434
MODEL=gpt-oss:20b

yaml
Copy
Edit

---

# 🧩 Architecture
mcp_client/
init.py
main.py # MCP Client entrypoint
config.py # load ENV (OLLAMA_HOST, MODEL)
connection.py # manages connection to Ollama + MCP
tools/
list_promotions_by_country.py
get_promotion_by_id.py
schemas/
list_promotions_by_country.json
get_promotion_by_id.json
logging.py

markdown
Copy
Edit

- **main.py** → starts MCP Client, connects to Ollama.
- **connection.py** → manages streaming requests/responses.
- **tools/** → Python modules implementing each tool.
- **schemas/** → JSON Schemas for tool input/output validation.

---

# 🛠️ Tools

## Tool: `list_promotions_by_country`
- **Description:** Returns a paginated list of promotions available for a given country (ISO-2 code).
- **Parameters:**
  - `country` (string, required, ISO-2).
  - `page` (integer, default: 1).
  - `limit` (integer, default: 50).
  - `include` (array<string>, optional).
  - `sort` (string, optional).
- **Output:** A list of promotions with details (id, title, slug, startDate, endDate, etc.).

---

## Tool: `get_promotion_by_id`
- **Description:** Returns the details of a single promotion by its ID.
- **Parameters:**
  - `id` (integer, required).
  - `include` (array<string>, optional).
- **Output:** A promotion object with attributes, or an empty result if not found.

---

# 🔄 Communication Flow
1. MCP Client initializes and connects to `gpt-oss:20b` via Ollama.
2. Tools (`list_promotions_by_country`, `get_promotion_by_id`) are registered with their JSON Schemas.
3. During interaction, the model **must only use these tools** to answer player queries.
4. All responses must be **formal**, limited strictly to promotion information.

---

# ⚙️ Implementation Guidelines
- **HTTP Client:** `httpx` for calling Ollama API (`/api/generate` or `/api/chat`).
- **Validation:** `pydantic` or JSON Schema for parameters and responses.
- **Logging:** JSON structured logs for each tool call (`tool`, `params`, `duration_ms`, `success/error`).
- **Security:** never log `STRAPI_TOKEN` or sensitive values.

---

# 🧪 Testing
- **Unit tests:** validation of tool parameters and schema outputs.
- **Integration:** confirm MCP Client <-> Ollama connection.
- **E2E:** ensure that player queries about promotions are answered with:
  - Data **only** from tools.
  - A **formal tone**.
  - Rejection if the query is unrelated to promotions.

---

# 📝 Example Prompts
- **Valid:**
  - *“Could you please provide me with the promotions available in Chile?”*  
    → Call `list_promotions_by_country` with `{ "country": "CL" }`.
  - *“I would like to know the details of promotion ID 123.”*  
    → Call `get_promotion_by_id` with `{ "id": 123 }`.

- **Invalid:**
  - *“What is the weather today?”*  
    → Agent must respond: *“I am only able to provide information regarding casino promotions.”*

---

# ✅ Acceptance Criteria
- MCP Client connects successfully to `gpt-oss:20b` (Ollama).
- Only **promotion-related tools** are exposed and usable.
- Agent answers strictly about promotions, using a **formal tone**.
- Any unrelated queries are rejected gracefully.
