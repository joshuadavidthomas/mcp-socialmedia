from django.contrib import admin
from .models import Team, ApiKey, Post


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at']


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ['name', 'team', 'is_active', 'created_at', 'last_used_at']
    list_filter = ['is_active', 'team']
    search_fields = ['name', 'key']
    readonly_fields = ['id', 'key', 'created_at', 'last_used_at']

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing object
            return self.readonly_fields + ('team',)
        return self.readonly_fields


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['author', 'content_preview', 'team', 'created_at', 'parent_post']
    list_filter = ['team', 'created_at']
    search_fields = ['author', 'content']
    readonly_fields = ['id', 'created_at']

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'
