from django.db import models
# from django.contrib.auth.models import User
from django.contrib.auth.models import AbstractUser, Group, Permission


class CustomUser(AbstractUser):
    groups = models.ManyToManyField(
        Group,
        related_name='custom_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='custom_user_permissions_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions'
    )

class InventoryItem(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name= 'inventory_items')
    name = models.CharField(max_length= 100)
    description = models.TextField(blank= True)
    quantity = models.PositiveIntegerField(default= 0)
    price = models.DecimalField(max_digits= 10, decimal_places= 2)
    category = models.CharField(max_length= 50, blank= True)
    date_added = models.DateTimeField(auto_now_add= True)
    last_updated = models.DateTimeField(auto_now= True)

    def __str__(self):
        return f"{self.name} ({self.quantity} pcs)"

class InventoryChangeLog(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='changes')
    performed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='inventory_changes')
    quantity_before = models.PositiveIntegerField()
    quantity_after = models.PositiveIntegerField()
    delta = models.IntegerField()
    reason = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.item.name}: {self.quantity_before} -> {self.quantity_after} by {self.performed_by or 'system'}"
