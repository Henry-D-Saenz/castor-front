"""
Pydantic schemas for RAG chat functionality.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RAGChatRequest(BaseModel):
    """Request for RAG chat endpoint."""

    message: str = Field(..., min_length=1, max_length=2000, description="User's question")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Previous messages in format [{'role': 'user'|'assistant', 'content': '...'}]"
    )
    top_k: int = Field(5, ge=1, le=20, description="Number of documents to retrieve")
    min_score: float = Field(0.3, ge=0.0, le=1.0, description="Minimum relevance score")
    filter_location: Optional[str] = Field(None, description="Filter by location")
    filter_topic: Optional[str] = Field(None, description="Filter by topic")


class RAGSource(BaseModel):
    """A source document used in the response."""

    id: str
    score: float
    type: str
    topic: Optional[str] = None
    location: Optional[str] = None
    date: Optional[str] = None
    preview: str


class RAGChatResponse(BaseModel):
    """Response from RAG chat endpoint."""

    success: bool = True
    answer: str
    sources: List[RAGSource] = Field(default_factory=list)
    conversation_id: Optional[str] = None
    documents_searched: int = 0
    documents_retrieved: int = 0


class RAGIndexRequest(BaseModel):
    """Request to index an analysis."""

    analysis_id: str = Field(..., description="Unique ID for the analysis")
    analysis_data: Dict[str, Any] = Field(..., description="Analysis data to index")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class RAGIndexResponse(BaseModel):
    """Response from indexing."""

    success: bool = True
    analysis_id: str
    documents_created: int
    document_ids: List[str] = Field(default_factory=list)


class RAGStatsResponse(BaseModel):
    """RAG service statistics."""

    success: bool = True
    documents_indexed: int
    embedding_model: str
    generation_model: str
