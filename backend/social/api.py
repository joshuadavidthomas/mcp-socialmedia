"""Django Ninja API endpoints for social media"""
from typing import Optional
from uuid import UUID
from django.shortcuts import get_object_or_404
from django.db.models import Q
from ninja import NinjaAPI, Query
from .auth import ApiKeyAuth, get_team_from_request
from .models import Team, Post
from .schemas import PostCreateRequest, PostResponse, PostsListResponse


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
