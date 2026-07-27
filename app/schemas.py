from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    model: str | None = None
    system_prompt: str | None = None
    user_id: str | None = Field(default=None, description="End-user ID for abuse detection")


class ChatResponse(BaseModel):
    answer: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float


class ProductQuery(BaseModel):
    """Week 6 — RAG search request with hybrid search + metadata filters."""
    query: str = Field(min_length=2, max_length=512)
    top_k: int = Field(default=5, ge=1, le=20)
    user_id: str | None = Field(default=None, description="End-user ID for abuse detection")

    # Metadata filters (pre-filter before vector/BM25 search)
    category: str | None = None
    min_price: float | None = Field(default=None, ge=0, description="Minimum price in USD")
    max_price: float | None = Field(default=None, ge=0, description="Maximum price in USD")

    # Search strategy flags
    use_hyde: bool = Field(
        default=False,
        description="Use Hypothetical Document Embeddings instead of raw query embedding",
    )
    use_query_expansion: bool = Field(
        default=False,
        description="Expand query into N alternatives via LLM for multi-query retrieval",
    )


class ProductHit(BaseModel):
    sku: str
    title: str
    category: str
    price_usd: float
    score: float


class ProductSearchResponse(BaseModel):
    query: str
    hits: list[ProductHit]
    answer: str | None = None
    cost_usd: float


class DescriptionRequest(BaseModel):
    product_name: str = Field(min_length=2, max_length=200)
    features: str | None = Field(default=None, max_length=1000)


class DescriptionResponse(BaseModel):
    description: str
    model: str
