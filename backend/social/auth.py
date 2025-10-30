"""Authentication utilities for API key validation"""
from typing import Optional
from django.utils import timezone
from ninja.security import APIKeyHeader
from .models import ApiKey, Team


class ApiKeyAuth(APIKeyHeader):
    """API Key authentication handler for Django Ninja"""
    param_name = "x-api-key"

    def authenticate(self, request, key: Optional[str]) -> Optional[ApiKey]:
        """
        Authenticate request using API key from header.
        Returns ApiKey instance if valid, None otherwise.
        """
        if not key:
            return None

        try:
            api_key = ApiKey.objects.select_related('team').get(
                key=key,
                is_active=True
            )

            # Update last_used_at timestamp
            api_key.last_used_at = timezone.now()
            api_key.save(update_fields=['last_used_at'])

            # Attach team to request for easy access
            request.team = api_key.team

            return api_key
        except ApiKey.DoesNotExist:
            return None


def get_team_from_request(request) -> Optional[Team]:
    """
    Extract team from authenticated request.
    Returns Team instance or None if not authenticated.
    """
    if hasattr(request, 'team'):
        return request.team
    if hasattr(request.auth, 'team'):
        return request.auth.team
    return None
