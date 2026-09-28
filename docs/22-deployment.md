# Deployment

## Environments
Development -> Staging -> Production

## Recommended containers
- frontend
- backend
- postgres
- redis
- chromadb/vector service as selected
- ollama/local model service where appropriate

## Configuration
Use environment variables/secrets management.

Required examples:
LLM_PROVIDER
LLM_BASE_URL
LLM_MODEL
DATABASE_URL
REDIS_URL
JWT_SECRET

## Production
- HTTPS
- Backups
- Health checks
- Monitoring
- Log aggregation
- Resource limits
- Database migrations
- Rollback plan
