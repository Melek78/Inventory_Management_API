from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import InventoryItem, InventoryChangeLog

try:
    from rest_framework_simplejwt.tokens import RefreshToken
    SIMPLEJWT_AVAILABLE = True
except Exception:
    SIMPLEJWT_AVAILABLE = False

User = get_user_model()


class BaseAPITest(APITestCase):
    def create_user(self, username='user1', password='pass12345', email='user1@example.com', is_staff=False):
        return User.objects.create_user(username=username, password=password, email=email, is_staff=is_staff)

    def authenticate(self, user):
        if SIMPLEJWT_AVAILABLE:
            refresh = RefreshToken.for_user(user)
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')
        else:
            # Fallback for environments without SimpleJWT installed
            self.client.force_authenticate(user=user)

    def url(self, path):
        # Helper to keep base path consistent
        if not path.startswith('/'):
            path = '/' + path
        return f'/api{path}' if not path.startswith('/api') else path


class AuthAndUserTests(BaseAPITest):
    def test_register_user(self):
        payload = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'newpass123',
            'first_name': 'New',
            'last_name': 'User',
        }
        resp = self.client.post(self.url('/users/'), payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertIn('id', resp.data)
        self.assertNotIn('password', resp.data)

    def test_register_user_duplicate_email_rejected(self):
        self.create_user(username='u1', email='dup@example.com')
        payload = {'username': 'u2', 'email': 'dup@example.com', 'password': 'pass12345'}
        resp = self.client.post(self.url('/users/'), payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)

    def test_jwt_obtain_and_refresh_tokens_if_available(self):
        if not SIMPLEJWT_AVAILABLE:
            self.skipTest("SimpleJWT not installed")
        user = self.create_user()
        resp = self.client.post(self.url('/token/'), {'username': user.username, 'password': 'pass12345'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)

        refresh = resp.data['refresh']
        resp2 = self.client.post(self.url('/token/refresh/'), {'refresh': refresh}, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_200_OK, resp2.data)
        self.assertIn('access', resp2.data)

    def test_custom_login_and_logout(self):
        user = self.create_user(username='loginuser', email='login@example.com', password='pass12345')
        # Login
        r1 = self.client.post(self.url('/users/user_login/'), {'username': 'loginuser', 'password': 'pass12345'}, format='json')
        self.assertEqual(r1.status_code, status.HTTP_200_OK, r1.data)
        self.assertIn('access', r1.data)
        self.assertIn('refresh', r1.data)
        refresh = r1.data['refresh']

        # Logout (blacklist)
        self.authenticate(user)  # ensure Authorization header for logout endpoint
        r2 = self.client.post(self.url('/users/user_logout/'), {'refresh': refresh}, format='json')
        self.assertEqual(r2.status_code, status.HTTP_200_OK, r2.data)

        # Optional: verify blacklisted refresh cannot be used to obtain a new access
        if SIMPLEJWT_AVAILABLE:
            r3 = self.client.post(self.url('/token/refresh/'), {'refresh': refresh}, format='json')
            self.assertIn(r3.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED))


class InventoryCrudTests(BaseAPITest):
    def setUp(self):
        self.user = self.create_user(username='owner', email='owner@example.com')
        self.other = self.create_user(username='other', email='other@example.com')
        self.authenticate(self.user)

    def test_unauthenticated_access_denied(self):
        self.client.credentials()  # clear auth
        resp = self.client.get(self.url('/inventory/'))
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_create_item_success(self):
        payload = {
            'name': 'Apple',
            'description': 'Green',
            'quantity': 10,
            'price': '1.99',
            'category': 'produce',
            'user': self.other.id,  # should be ignored due to read-only
        }
        resp = self.client.post(self.url('/inventory/'), payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        item = InventoryItem.objects.get(id=resp.data['id'])
        self.assertEqual(item.user, self.user)
        self.assertEqual(item.quantity, 10)
        self.assertEqual(item.price, Decimal('1.99'))

    def test_create_item_validation_errors(self):
        # Negative quantity
        resp = self.client.post(self.url('/inventory/'), {
            'name': 'BadQty',
            'quantity': -1,
            'price': '5.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # Non-positive price
        resp = self.client.post(self.url('/inventory/'), {
            'name': 'BadPrice',
            'quantity': 1,
            'price': '0.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_only_own_items(self):
        mine = InventoryItem.objects.create(user=self.user, name='Mine', quantity=1, price='1.00')
        InventoryItem.objects.create(user=self.other, name='Theirs', quantity=5, price='2.00')
        resp = self.client.get(self.url('/inventory/'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data.get('results', resp.data)  # handle pagination/no pagination
        ids = {it['id'] for it in data}
        self.assertIn(mine.id, ids)

    def test_retrieve_own_and_forbid_others(self):
        mine = InventoryItem.objects.create(user=self.user, name='Mine', quantity=1, price='1.00')
        other_item = InventoryItem.objects.create(user=self.other, name='Theirs', quantity=5, price='2.00')

        r1 = self.client.get(self.url(f'/inventory/{mine.id}/'))
        self.assertEqual(r1.status_code, status.HTTP_200_OK)

        r2 = self.client.get(self.url(f'/inventory/{other_item.id}/'))
        # If queryset is user-scoped, not found; else object permission may 403
        self.assertIn(r2.status_code, (status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN))

    def test_update_logs_quantity_change(self):
        item = InventoryItem.objects.create(user=self.user, name='A', quantity=2, price='1.00')
        # Update name only: no log for quantity
        r1 = self.client.patch(self.url(f'/inventory/{item.id}/'), {'name': 'A1'}, format='json')
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(InventoryChangeLog.objects.filter(item=item).count(), 0)

        # Update quantity: log created
        r2 = self.client.patch(self.url(f'/inventory/{item.id}/'), {'quantity': 7, 'reason': 'restock'}, format='json')
        self.assertEqual(r2.status_code, status.HTTP_200_OK, r2.data)
        logs = InventoryChangeLog.objects.filter(item=item).order_by('-created_at')
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs[0].quantity_before, 2)
        self.assertEqual(logs[0].quantity_after, 7)
        self.assertEqual(logs[0].delta, 5)

    def test_adjust_quantity_endpoint(self):
        item = InventoryItem.objects.create(user=self.user, name='B', quantity=3, price='2.50')
        # Decrement
        resp = self.client.post(self.url(f'/inventory/{item.id}/adjust_quantity/'),
                                {'delta': -2, 'reason': 'sale'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 1)
        self.assertEqual(InventoryChangeLog.objects.filter(item=item).count(), 1)

        # Floor at zero
        resp = self.client.post(self.url(f'/inventory/{item.id}/adjust_quantity/'),
                                {'delta': -10, 'reason': 'correction'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 0)

    def test_history_endpoint(self):
        item = InventoryItem.objects.create(user=self.user, name='C', quantity=1, price='3.00')
        self.client.post(self.url(f'/inventory/{item.id}/adjust_quantity/'), {'delta': 4}, format='json')
        self.client.post(self.url(f'/inventory/{item.id}/adjust_quantity/'), {'delta': -1}, format='json')
        resp = self.client.get(self.url(f'/inventory/{item.id}/history/'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(resp.data, list))
        self.assertGreaterEqual(len(resp.data), 2)

    def test_levels_endpoint_and_filters(self):
        InventoryItem.objects.create(user=self.user, name='D1', quantity=2, price='5.00', category='cat1')
        InventoryItem.objects.create(user=self.user, name='D2', quantity=9, price='15.00', category='cat2')
        # Levels
        r = self.client.get(self.url('/inventory/levels/'))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(all(set(['id', 'name', 'category', 'price', 'quantity']).issubset(d.keys()) for d in r.data))

        # Category filter
        r2 = self.client.get(self.url('/inventory/?category=cat1'))
        data2 = r2.data.get('results', r2.data)
        self.assertTrue(all(d['category'] == 'cat1' for d in data2))

        # Price range filter
        r3 = self.client.get(self.url('/inventory/?price__gte=10&price__lte=20'))
        data3 = r3.data.get('results', r3.data)
        self.assertTrue(all(Decimal(d['price']) >= Decimal('10') and Decimal(d['price']) <= Decimal('20') for d in data3))

        # Low stock filter
        r4 = self.client.get(self.url('/inventory/?low_stock=5'))
        data4 = r4.data.get('results', r4.data)
        self.assertTrue(all(d['quantity'] < 5 for d in data4))

    def test_search_and_ordering(self):
        InventoryItem.objects.create(user=self.user, name='Banana', quantity=5, price='3.00', category='fruit')
        InventoryItem.objects.create(user=self.user, name='Apple', quantity=1, price='1.00', category='fruit')
        InventoryItem.objects.create(user=self.user, name='Zucchini', quantity=10, price='2.50', category='veggie')

        # Search
        r = self.client.get(self.url('/inventory/?search=App'))
        data = r.data.get('results', r.data)
        names = [d['name'] for d in data]
        self.assertIn('Apple', names)

        # Ordering by price desc
        r2 = self.client.get(self.url('/inventory/?ordering=-price'))
        data2 = r2.data.get('results', r2.data)
        prices = [Decimal(d['price']) for d in data2]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_pagination(self):
        for i in range(12):
            InventoryItem.objects.create(user=self.user, name=f'Item{i}', quantity=i, price='1.00')
        r = self.client.get(self.url('/inventory/'))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsInstance(r.data, dict)
        self.assertIn('count', r.data)
        self.assertIn('results', r.data)
        self.assertEqual(r.data['count'], 12)
        self.assertEqual(len(r.data['results']), 10)

    def test_cannot_modify_or_delete_others(self):
        item = InventoryItem.objects.create(user=self.other, name='OtherItem', quantity=2, price='1.00')
        r1 = self.client.patch(self.url(f'/inventory/{item.id}/'), {'name': 'Hacked'}, format='json')
        r2 = self.client.delete(self.url(f'/inventory/{item.id}/'))
        self.assertIn(r1.status_code, (status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN))
        self.assertIn(r2.status_code, (status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN))
