"""Pydantic schemas for API requests and responses"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID


# ========== Social Media Schemas ==========


class PostCreateRequest(BaseModel):
    """Schema for creating a new post"""
    author: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1, max_length=2000)
    tags: Optional[List[str]] = Field(default_factory=list)
    parentPostId: Optional[str] = Field(None, alias="parentPostId")

    class Config:
        populate_by_name = True


class TimestampSchema(BaseModel):
    """Timestamp in Firebase format"""
    model_config = ConfigDict(populate_by_alias=True)

    seconds: int = Field(..., serialization_alias="_seconds")


class PostResponse(BaseModel):
    """Schema for a single post response"""
    postId: str
    author: str
    content: str
    tags: List[str] = Field(default_factory=list)
    createdAt: dict  # Use dict to have full control over structure
    parentPostId: Optional[str] = None

    class Config:
        populate_by_name = True

    @classmethod
    def from_orm(cls, post):
        """Convert Django Post model to response schema"""
        return cls(
            postId=str(post.id),
            author=post.author,
            content=post.content,
            tags=post.tags or [],
            createdAt={
                "_seconds": int(post.created_at.timestamp())
            },
            parentPostId=str(post.parent_post.id) if post.parent_post else None
        )


class PostsListResponse(BaseModel):
    """Schema for paginated posts list"""
    posts: List[PostResponse]
    totalCount: int
    nextOffset: Optional[str] = None

    class Config:
        populate_by_name = True


# ========== Journal Schemas ==========


class JournalSections(BaseModel):
    """Structured journal sections"""
    feelings: Optional[str] = None
    project_notes: Optional[str] = None
    technical_insights: Optional[str] = None
    user_context: Optional[str] = None
    world_knowledge: Optional[str] = None


class JournalEntryPayload(BaseModel):
    """Request payload for creating journal entry"""
    team_id: str
    timestamp: int
    sections: Optional[JournalSections] = None
    content: Optional[str] = None
    embedding: Optional[List[float]] = None
    
    class Config:
        populate_by_name = True


class JournalEntryResponse(BaseModel):
    """Response for journal entry"""
    id: str
    team_id: str
    timestamp: int
    created_at: str  # ISO 8601
    sections: Optional[dict] = None
    content: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_dimensions: Optional[int] = None
    
    class Config:
        populate_by_name = True
    
    @classmethod
    def from_orm(cls, entry):
        """Convert Django model to response schema"""
        sections = None
        if any([entry.feelings, entry.project_notes, entry.technical_insights,
                entry.user_context, entry.world_knowledge]):
            sections = {
                k: v for k, v in {
                    'feelings': entry.feelings,
                    'project_notes': entry.project_notes,
                    'technical_insights': entry.technical_insights,
                    'user_context': entry.user_context,
                    'world_knowledge': entry.world_knowledge,
                }.items() if v
            }
        
        return cls(
            id=str(entry.id),
            team_id=entry.team.name,
            timestamp=entry.timestamp,
            created_at=entry.created_at.isoformat(),
            sections=sections,
            content=entry.content,
            embedding_model=entry.embedding_model,
            embedding_dimensions=entry.embedding_dimensions
        )


class JournalEntriesListResponse(BaseModel):
    """Response for listing journal entries"""
    entries: List[JournalEntryResponse]
    total_count: int
    has_more: bool
    
    class Config:
        populate_by_name = True


class SearchRequest(BaseModel):
    """Request for semantic search"""
    query: str
    limit: Optional[int] = Field(10, ge=1, le=100)
    offset: Optional[int] = Field(0, ge=0)
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    sections: Optional[List[str]] = None
    similarity_threshold: Optional[float] = Field(0.0, ge=0.0, le=1.0)
    
    class Config:
        populate_by_name = True


class SearchResult(BaseModel):
    """Single search result with similarity score"""
    id: str
    team_id: str
    similarity_score: float
    timestamp: int
    created_at: str
    sections: Optional[dict] = None
    content: Optional[str] = None
    matched_sections: Optional[List[str]] = None
    
    class Config:
        populate_by_name = True
    
    @classmethod
    def from_orm(cls, entry, similarity_score=1.0):
        """Convert search result to response"""
        matched = []
        sections = {}
        for section in ['feelings', 'project_notes', 'technical_insights',
                       'user_context', 'world_knowledge']:
            value = getattr(entry, section, None)
            if value:
                matched.append(section)
                sections[section] = value
        
        return cls(
            id=str(entry.id),
            team_id=entry.team.name,
            similarity_score=similarity_score,
            timestamp=entry.timestamp,
            created_at=entry.created_at.isoformat(),
            sections=sections if sections else None,
            content=entry.content,
            matched_sections=matched if matched else None
        )


class SearchResponse(BaseModel):
    """Response for search query"""
    results: List[SearchResult]
    total_count: int
    query_embedding: Optional[List[float]] = None
    
    class Config:
        populate_by_name = True
