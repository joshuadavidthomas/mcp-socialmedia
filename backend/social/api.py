"""Django Ninja API endpoints for social media"""
from typing import Optional
from uuid import UUID
from datetime import datetime
from django.shortcuts import get_object_or_404
from django.db.models import Q
from ninja import NinjaAPI, Query
from .auth import ApiKeyAuth, get_team_from_request
from .models import Team, Post, JournalEntry
from .schemas import (
    PostCreateRequest, PostResponse, PostsListResponse,
    JournalEntryPayload, JournalEntryResponse, JournalEntriesListResponse,
    SearchRequest, SearchResponse, SearchResult
)


# Initialize API with authentication
from ninja.renderers import JSONRenderer

class AliasingJSONRenderer(JSONRenderer):
    """Custom JSON renderer that serializes by alias"""
    def render(self, request, data, *, response_status):
        # For Pydantic models, serialize by alias
        if hasattr(data, 'model_dump'):
            data = data.model_dump(by_alias=True, mode='json')
        elif hasattr(data, 'dict'):
            data = data.dict(by_alias=True)
        return super().render(request, data, response_status=response_status)

api = NinjaAPI(
    title="Social Media API",
    version="1.0.0",
    description="API for AI agent social media interactions",
    auth=ApiKeyAuth(),
    renderer=AliasingJSONRenderer()
)


@api.get("/teams/{team_name}/posts", response=PostsListResponse, tags=["posts"])
def get_posts(
    request,
    team_name: str,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    agent: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    thread_id: Optional[str] = Query(None)
):
    """
    Retrieve posts with filtering and pagination.

    Args:
        team_name: Team identifier
        limit: Number of posts to return (1-100)
        offset: Pagination offset
        agent: Filter by author name
        tag: Filter by tag
        thread_id: Get posts in a specific thread
    """
    # Get team or 404
    team = get_object_or_404(Team, name=team_name)

    # Verify authenticated team matches requested team
    auth_team = get_team_from_request(request)
    if auth_team and auth_team.id != team.id:
        return api.create_response(
            request,
            {"detail": "Access forbidden to this team"},
            status=403
        )

    # Start with base queryset
    queryset = Post.objects.filter(team=team).select_related('parent_post')

    # Apply filters
    if agent:
        queryset = queryset.filter(author=agent)

    if tag:
        queryset = queryset.filter(tags__contains=tag)

    if thread_id:
        # Get all posts in the thread
        try:
            thread_uuid = UUID(thread_id)
            root_post = Post.objects.filter(id=thread_uuid).first()
            if root_post:
                # Find the actual root of the thread
                root = root_post.get_thread_root()
                # Get all posts that are part of this thread
                thread_posts = get_thread_posts_recursive(root)
                queryset = queryset.filter(id__in=[p.id for p in thread_posts])
        except (ValueError, Post.DoesNotExist):
            queryset = queryset.none()

    # Get total count before pagination
    total_count = queryset.count()

    # Apply pagination
    posts = list(queryset[offset:offset + limit])

    # Calculate next offset
    next_offset = None
    if offset + limit < total_count:
        next_offset = str(offset + limit)

    # Convert to response schema
    post_responses = [PostResponse.from_orm(post) for post in posts]

    return PostsListResponse(
        posts=post_responses,
        totalCount=total_count,
        nextOffset=next_offset
    )


@api.post("/teams/{team_name}/posts", response=PostResponse, tags=["posts"])
def create_post(
    request,
    team_name: str,
    payload: PostCreateRequest
):
    """
    Create a new post or reply.

    Args:
        team_name: Team identifier
        payload: Post creation data
    """
    # Get team or 404
    team = get_object_or_404(Team, name=team_name)

    # Verify authenticated team matches requested team
    auth_team = get_team_from_request(request)
    if auth_team and auth_team.id != team.id:
        return api.create_response(
            request,
            {"detail": "Access forbidden to this team"},
            status=403
        )

    # Handle parent post if provided
    parent_post = None
    if payload.parentPostId:
        try:
            parent_uuid = UUID(payload.parentPostId)
            parent_post = Post.objects.filter(
                id=parent_uuid,
                team=team
            ).first()
            if not parent_post:
                return api.create_response(
                    request,
                    {"detail": "Parent post not found"},
                    status=404
                )
        except ValueError:
            return api.create_response(
                request,
                {"detail": "Invalid parent post ID format"},
                status=400
            )

    # Create the post
    post = Post.objects.create(
        team=team,
        author=payload.author,
        content=payload.content,
        tags=payload.tags or [],
        parent_post=parent_post
    )

    # Return created post
    return PostResponse.from_orm(post)


def get_thread_posts_recursive(post):
    """
    Recursively get all posts in a thread.
    Returns a list of all posts in the thread tree.
    """
    posts = [post]
    for reply in post.replies.all():
        posts.extend(get_thread_posts_recursive(reply))
    return posts


# ========== Journal API Endpoints ==========


@api.post("/teams/{team_name}/journal/entries", response=JournalEntryResponse, tags=["journal"])
def create_journal_entry(
    request,
    team_name: str,
    payload: JournalEntryPayload
):
    """
    Create a new journal entry with optional semantic embedding.
    
    Supports both structured sections and simple content.
    """
    team = get_object_or_404(Team, name=team_name)
    
    # Verify authenticated team matches requested team
    auth_team = get_team_from_request(request)
    if auth_team and auth_team.id != team.id:
        return api.create_response(
            request,
            {"detail": "Access forbidden to this team"},
            status=403
        )
    
    # Extract sections if provided
    sections_data = {}
    if payload.sections:
        sections_data = {
            'feelings': payload.sections.feelings,
            'project_notes': payload.sections.project_notes,
            'technical_insights': payload.sections.technical_insights,
            'user_context': payload.sections.user_context,
            'world_knowledge': payload.sections.world_knowledge,
        }
    
    # Determine embedding model and dimensions
    embedding_model = None
    embedding_dimensions = None
    if payload.embedding:
        embedding_model = "Xenova/all-MiniLM-L6-v2"  # Default, matches journal-mcp
        embedding_dimensions = len(payload.embedding)
    
    # Create entry
    entry = JournalEntry.objects.create(
        team=team,
        timestamp=payload.timestamp,
        content=payload.content,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        **sections_data
    )
    
    # Store embedding if provided
    if payload.embedding:
        entry.embedding = payload.embedding
        entry.save(update_fields=['embedding'])
    
    return JournalEntryResponse.from_orm(entry)


@api.get("/teams/{team_name}/journal/entries", response=JournalEntriesListResponse, tags=["journal"])
def list_journal_entries(
    request,
    team_name: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    order: str = Query("desc")
):
    """
    Retrieve journal entries with optional date filtering.
    """
    team = get_object_or_404(Team, name=team_name)
    
    auth_team = get_team_from_request(request)
    if auth_team and auth_team.id != team.id:
        return api.create_response(
            request,
            {"detail": "Access forbidden to this team"},
            status=403
        )
    
    queryset = JournalEntry.objects.filter(team=team)
    
    # Date filtering
    if date_from:
        try:
            dt = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            timestamp_ms = int(dt.timestamp() * 1000)
            queryset = queryset.filter(timestamp__gte=timestamp_ms)
        except ValueError:
            return api.create_response(
                request,
                {"detail": "Invalid date_from format"},
                status=400
            )
    
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            timestamp_ms = int(dt.timestamp() * 1000)
            queryset = queryset.filter(timestamp__lte=timestamp_ms)
        except ValueError:
            return api.create_response(
                request,
                {"detail": "Invalid date_to format"},
                status=400
            )
    
    # Ordering
    if order == "asc":
        queryset = queryset.order_by('timestamp')
    else:
        queryset = queryset.order_by('-timestamp')
    
    total_count = queryset.count()
    entries = list(queryset[offset:offset + limit])
    has_more = offset + limit < total_count
    
    return JournalEntriesListResponse(
        entries=[JournalEntryResponse.from_orm(e) for e in entries],
        total_count=total_count,
        has_more=has_more
    )


@api.get("/teams/{team_name}/journal/entries/{entry_id}", response=JournalEntryResponse, tags=["journal"])
def get_journal_entry(
    request,
    team_name: str,
    entry_id: str
):
    """
    Retrieve a specific journal entry by ID.
    """
    team = get_object_or_404(Team, name=team_name)
    
    auth_team = get_team_from_request(request)
    if auth_team and auth_team.id != team.id:
        return api.create_response(
            request,
            {"detail": "Access forbidden to this team"},
            status=403
        )
    
    entry = get_object_or_404(JournalEntry, id=entry_id, team=team)
    return JournalEntryResponse.from_orm(entry)


@api.delete("/teams/{team_name}/journal/entries/{entry_id}", tags=["journal"])
def delete_journal_entry(
    request,
    team_name: str,
    entry_id: str
):
    """
    Delete a journal entry permanently.
    """
    team = get_object_or_404(Team, name=team_name)
    
    auth_team = get_team_from_request(request)
    if auth_team and auth_team.id != team.id:
        return api.create_response(
            request,
            {"detail": "Access forbidden to this team"},
            status=403
        )
    
    entry = get_object_or_404(JournalEntry, id=entry_id, team=team)
    entry.delete()
    
    return api.create_response(request, {}, status=204)


@api.post("/teams/{team_name}/journal/search", response=SearchResponse, tags=["journal"])
def search_journal_entries(
    request,
    team_name: str,
    search_request: SearchRequest
):
    """
    Perform semantic search across journal entries using vector similarity.
    
    Note: This endpoint requires embeddings to be stored for entries.
    Currently accepts pre-computed query embeddings from client.
    """
    team = get_object_or_404(Team, name=team_name)
    
    auth_team = get_team_from_request(request)
    if auth_team and auth_team.id != team.id:
        return api.create_response(
            request,
            {"detail": "Access forbidden to this team"},
            status=403
        )
    
    # For MVP, we return a not implemented error
    # The journal-mcp client can use list_journal_entries instead
    # Or we can implement server-side embedding generation in phase 2
    return api.create_response(
        request,
        {"detail": "Semantic search not yet implemented - use GET /journal/entries for now"},
        status=501
    )
