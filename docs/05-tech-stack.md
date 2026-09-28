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
- Local LLM through Ollama
- Provider interface allowing a cloud model later

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
