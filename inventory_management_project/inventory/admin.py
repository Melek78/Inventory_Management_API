from django.contrib import admin
from .models import InventoryItem, InventoryChangeLog

@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'quantity', 'category', 'price', 'last_updated')
    search_fields = ('name', 'category', 'user__username')

@admin.register(InventoryChangeLog)
class InventoryChangeLogAdmin(admin.ModelAdmin):
    list_display = ('item', 'performed_by', 'quantity_before', 'quantity_after', 'delta', 'reason', 'created_at')
    list_filter = ('reason', 'created_at')