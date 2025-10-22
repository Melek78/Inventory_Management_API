from django.shortcuts import render
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import CustomUser
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.tokens import RefreshToken

from .models import InventoryItem, InventoryChangeLog
from .serializers import InventoryItemSerializer, UserSerializer, LoginSerializer
from .permissions import IsOwner

class InventoryItemViewSet(viewsets.ModelViewSet):
    serializer_class = InventoryItemSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = {
        'category': ['exact'],
        'price': ['gte', 'lte'],
    }
    search_fields = ['name', 'category']
    ordering_fields = ['name', 'quantity', 'price', 'date_added', 'last_updated']
    ordering = ['-last_updated']

    def get_queryset(self):
        qs = InventoryItem.objects.all()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        low_stock = self.request.query_params.get('low_stock')
        if low_stock is not None:
            try:
                threshold = int(low_stock)
                qs = qs.filter(quantity__lt=threshold)
            except ValueError:
                pass
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        before = instance.quantity
        item = serializer.save()
        after = item.quantity
        if before != after:
            InventoryChangeLog.objects.create(
                item=item,
                performed_by=self.request.user,
                quantity_before=before,
                quantity_after=after,
                delta=after - before,
                reason=self.request.data.get('reason', '')
            )

    @action(detail=False, methods=['get'])
    def levels(self, request):
        qs = self.filter_queryset(self.get_queryset()).only('id', 'name', 'category', 'price', 'quantity')
        data = [{'id': o.id, 'name': o.name, 'category': o.category, 'price': str(o.price), 'quantity': o.quantity} for o in qs]
        return Response(data)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        item = self.get_object()
        data = [
            {
                'id': change.id,
                'quantity_before': change.quantity_before,
                'quantity_after': change.quantity_after,
                'delta': change.delta,
                'reason': change.reason,
                'performed_by': change.performed_by.username if change.performed_by else None,
                'created_at': change.created_at,
            }
            for change in item.changes.all()
        ]
        return Response(data)

    @action(detail=True, methods=['post'])
    def adjust_quantity(self, request, pk=None):
        item = self.get_object()
        try:
            delta = int(request.data.get('delta'))
        except (TypeError, ValueError):
            return Response({'detail': 'delta must be an integer'}, status=status.HTTP_400_BAD_REQUEST)
        reason = request.data.get('reason', '')
        before = item.quantity
        after = max(0, before + delta)
        item.quantity = after
        item.save(update_fields=['quantity', 'last_updated'])
        InventoryChangeLog.objects.create(
            item=item,
            performed_by=request.user,
            quantity_before=before,
            quantity_after=after,
            delta=after - before,
            reason=reason
        )
        return Response({'id': item.id, 'quantity': item.quantity})

class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action in ["user_login", "user_logout"]:
            return []
        if self.action in ['create']:  # registration
            return [permissions.AllowAny()]
        if self.action in ['list', 'destroy']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if self.request.user.is_staff:
            return CustomUser.objects.all()
        return CustomUser.objects.filter(id=self.request.user.id)

    @action(detail=False, methods=['POST'], permission_classes=[permissions.AllowAny])
    @csrf_exempt
    def user_login(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            # Create JWT tokens
            refresh = RefreshToken.for_user(user)
            return Response({
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # -------- Logout Action --------
    @action(detail=False, methods=['POST'], permission_classes=[permissions.IsAuthenticated])
    @csrf_exempt
    def user_logout(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logged out successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)

