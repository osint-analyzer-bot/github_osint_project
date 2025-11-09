from django.contrib import admin
from .models import ScanRequest, ScanResult

@admin.register(ScanRequest)
class ScanRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'repository_url', 'scan_type', 'scan_depth', 'get_status', 'has_local_path', 'created_at']
    list_filter = ['scan_type', 'scan_depth', 'status', 'created_at']
    search_fields = ['repository_url', 'user__username', 'local_path']
    readonly_fields = ['created_at', 'updated_at', 'local_path_display']
    list_select_related = ['user']

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'repository_url', 'scan_type', 'scan_depth', 'include_history')
        }),
        ('Статус', {
            'fields': ('status', 'local_path_display', 'error_message')
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_status(self, obj):
        return obj.get_status_display()
    get_status.short_description = 'Статус'

    def has_local_path(self, obj):
        return bool(obj.local_path)
    has_local_path.boolean = True
    has_local_path.short_description = 'Локальный путь'

    def local_path_display(self, obj):
        if obj.local_path:
            return obj.local_path
        return "Не сохранен"
    local_path_display.short_description = 'Локальный путь'

@admin.register(ScanResult)
class ScanResultAdmin(admin.ModelAdmin):
    list_display = ['id', 'scan_request', 'status', 'bug_type', 'secret_type', 'confidence', 'file_path']
    list_filter = ['status', 'bug_type', 'confidence', 'created_at']
    search_fields = ['file_path', 'scan_request__repository_url', 'description']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['scan_request']