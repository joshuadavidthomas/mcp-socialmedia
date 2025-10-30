import secrets
import uuid
from django.db import models
from django.utils import timezone


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
