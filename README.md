# AI Engineer Starter Repo
**Stack:** FastAPI + Pydantic + Postgres (pgvector) + Docker + Caddy
**Purpose:** Month 1 flagship project base. E-commerce RAG service that grows into a 4-project portfolio.

## What's inside

```
starter-repo/
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI entrypoint
│   ├── config.py          # env-driven settings (Pydantic Settings)
│   ├── logger.py          # LLM-call logger + cost tracker (the thing you write by hand)
│   ├── db.py              # SQLAlchemy async engine, session
│   ├── models.py          # SQLAlchemy ORM: Interaction, Product
│   ├── schemas.py         # Pydantic request/response models
│   ├── llm.py             # Thin OpenAI/Anthropic wrappers (no LangChain)
│   └── routers/
│       ├── __init__.py
│       ├── health.py
│       └── chat.py        # /chat endpoint
├── tests/
│   ├── test_health.py
│   └── test_logger.py
├── alembic/               # migrations (optional, init after first run)
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

## Quick start

```bash
cp .env.example .env
# fill in OPENAI_API_KEY
docker-compose up --build
# open http://localhost:8000/docs
```

## Rules you agreed to

1. **Every LLM call goes through `app/logger.py`**. If a call doesn't log cost, PR gets rejected (even if the PR is from you).
2. **No LangChain.** Direct SDK calls wrapped in `app/llm.py`.
3. **Write `app/logger.py` by hand.** It's deliberately left as a stub for you.
4. **Tests are mandatory.** No endpoint without a test.

## Month 1 weekly checkpoints

- **Week 1:** Logger + health + first `/chat` endpoint + 5 tests
- **Week 2:** pgvector + embeddings + `/search` endpoint (RAG)
- **Week 3:** Deploy to VPS with Caddy HTTPS + rate limiting
- **Week 4:** Model selection matrix + 4-model benchmark
