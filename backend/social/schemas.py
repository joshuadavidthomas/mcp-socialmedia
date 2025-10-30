"""Pydantic schemas for API requests and responses"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID


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
