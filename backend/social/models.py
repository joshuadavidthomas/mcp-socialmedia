import secrets
import uuid
from django.db import models
from django.utils import timezone
from pgvector.django import VectorField


class Team(models.Model):
    """Team model for multi-tenancy"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ApiKey(models.Model):
    """API Key for authentication"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=64, unique=True, db_index=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=255, help_text="Friendly name for this key")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.team.name})"

    @classmethod
    def generate_key(cls):
        """Generate a secure random API key"""
        return secrets.token_urlsafe(48)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        super().save(*args, **kwargs)


class Post(models.Model):
    """Social media post model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='posts', db_index=True)
    author = models.CharField(max_length=255, db_index=True, help_text="Agent/user name")
    content = models.TextField(max_length=2000)
    tags = models.JSONField(default=list, blank=True)
    parent_post = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        db_index=True,
        help_text="Parent post for threaded conversations"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['team', '-created_at']),
            models.Index(fields=['team', 'author', '-created_at']),
            models.Index(fields=['team', 'parent_post']),
        ]

    def __str__(self):
        return f"{self.author}: {self.content[:50]}..."

    def get_thread_root(self):
        """Get the root post of this thread"""
        if self.parent_post is None:
            return self
        current = self
        while current.parent_post is not None:
            current = current.parent_post
        return current

    def get_thread_posts(self):
        """Get all posts in this thread"""
        root = self.get_thread_root()
        return Post.objects.filter(
            models.Q(id=root.id) |
            models.Q(parent_post__in=self._get_all_descendants(root))
        ).order_by('created_at')

    def _get_all_descendants(self, post):
        """Recursively get all descendant posts"""
        descendants = [post]
        for reply in post.replies.all():
            descendants.extend(self._get_all_descendants(reply))
        return descendants


class JournalEntry(models.Model):
    """Journal entry model with semantic search capability"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='journal_entries', db_index=True)
    timestamp = models.BigIntegerField(db_index=True, help_text="Unix timestamp in milliseconds")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Structured sections (all optional)
    feelings = models.TextField(null=True, blank=True, help_text="Personal emotional content")
    project_notes = models.TextField(null=True, blank=True, help_text="Project-specific technical notes")
    technical_insights = models.TextField(null=True, blank=True, help_text="General technical learnings")
    user_context = models.TextField(null=True, blank=True, help_text="User interaction observations")
    world_knowledge = models.TextField(null=True, blank=True, help_text="General domain knowledge")
    
    # Alternative simple content
    content = models.TextField(null=True, blank=True, help_text="Simple text content (alternative to sections)")
    
    # Embedding for semantic search
    embedding = VectorField(dimensions=384, null=True, blank=True)
    embedding_model = models.CharField(max_length=255, null=True, blank=True)
    embedding_dimensions = models.IntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['team', '-timestamp']),
            models.Index(fields=['team', '-created_at']),
        ]
        verbose_name_plural = "Journal entries"
    
    def __str__(self):
        return f"Journal entry {self.id} at {self.timestamp}"
    
    @classmethod
    def search_similar(cls, team, query_embedding, limit=10, threshold=0.0, sections=None, date_from=None, date_to=None):
        """
        Search for similar entries using cosine similarity.
        
        Args:
            team: Team to search within
            query_embedding: Vector embedding of search query
            limit: Maximum number of results
            threshold: Minimum similarity score (0.0-1.0)
            sections: List of section names to filter by
            date_from: Minimum timestamp (Unix milliseconds)
            date_to: Maximum timestamp (Unix milliseconds)
        
        Returns:
            QuerySet of JournalEntry objects annotated with 'similarity' field
        """
        from django.db.models import Q
        from pgvector.django import CosineDistance
        
        queryset = cls.objects.filter(team=team, embedding__isnull=False)
        
        # Apply date filters
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
        
        # Apply section filters
        if sections:
            section_filters = Q()
            for section in sections:
                section_filters |= Q(**{f"{section}__isnull": False})
            queryset = queryset.filter(section_filters)
        
        # Calculate similarity and filter
        results = queryset.annotate(
            similarity=1 - CosineDistance('embedding', query_embedding)
        ).filter(
            similarity__gte=threshold
        ).order_by('-similarity')[:limit]
        
        return results
