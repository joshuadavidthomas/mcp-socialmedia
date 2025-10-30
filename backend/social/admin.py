from django.contrib import admin
from .models import Team, ApiKey, Post, JournalEntry


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


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ['id', 'team', 'timestamp_display', 'created_at', 'has_embedding', 'sections_preview']
    list_filter = ['team', 'created_at']
    search_fields = ['feelings', 'project_notes', 'technical_insights', 'user_context', 'world_knowledge', 'content']
    readonly_fields = ['id', 'created_at', 'embedding_model', 'embedding_dimensions']
    
    def timestamp_display(self, obj):
        from datetime import datetime
        return datetime.fromtimestamp(obj.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
    timestamp_display.short_description = 'Timestamp'
    
    def has_embedding(self, obj):
        return bool(obj.embedding)
    has_embedding.boolean = True
    has_embedding.short_description = 'Embedded'
    
    def sections_preview(self, obj):
        sections = []
        if obj.feelings: sections.append('feelings')
        if obj.project_notes: sections.append('project_notes')
        if obj.technical_insights: sections.append('technical_insights')
        if obj.user_context: sections.append('user_context')
        if obj.world_knowledge: sections.append('world_knowledge')
        return ', '.join(sections) if sections else 'content only'
    sections_preview.short_description = 'Sections'
