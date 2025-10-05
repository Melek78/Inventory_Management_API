from django.contrib import admin
from .models import InventoryItem

@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'quantity', 'category', 'price', 'last_updated')
    search_fields = ('name', 'category', 'user__username')