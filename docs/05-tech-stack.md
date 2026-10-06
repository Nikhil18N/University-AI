# Technology Stack

## Initial recommendation
Frontend:
- React
- TypeScript
- Vite
- Tailwind CSS or equivalent component system

Backend:
- Python
- FastAPI
- Pydantic

AI:
- Local LLM through Ollama (llama3.2)
- Cloud LLM through Google Gemini (gemini-3.5-flash / gemini-2.0-flash)
- Cloud LLM through OpenRouter (meta-llama/llama-3.3-70b-instruct, deepseek, mistral, etc.)
- Swappable provider interface (app.providers.base.LLMProvider)

RAG:
- LlamaIndex
- ChromaDB
- Local or approved embedding model

Documents:
- PyMuPDF
- Unstructured
- OCR only where required

Data:
- PostgreSQL
- Redis

Infrastructure:
- Docker / Docker Compose
- GitHub Actions optional

## Rule
Technology choices are defaults, not permission to add unnecessary complexity.
