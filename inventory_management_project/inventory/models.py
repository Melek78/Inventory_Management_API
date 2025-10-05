from django.db import models
from django.contrib.auth.models import User

class InventoryItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name= 'inventory_items')
    name = models.CharField(max_length= 100)
    description = models.TextField(blank= True)
    quantity = models.PositiveIntegerField(default= 0)
    price = models.DecimalField(max_digits= 10, decimal_places= 2)
    category = models.CharField(max_length= 50, blank= True)
    date_added = models.DateTimeField(auto_now_add= True)
    last_updated = models.DateTimeField(auto_now= True)

    def __str__(self):
        return f"{self.name} ({self.quantity} pcs)"