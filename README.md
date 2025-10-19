# Inventory Management API (Django + DRF)

A RESTful API to manage inventory items with authentication, ownership permissions, filtering, pagination, sorting, and change history tracking.

Key components:
- Models: [`inventory.models.CustomUser`](inventory_management_project/inventory/models.py), [`inventory.models.InventoryItem`](inventory_management_project/inventory/models.py), [`inventory.models.InventoryChangeLog`](inventory_management_project/inventory/models.py)
- Views: [`inventory.views.InventoryItemViewSet`](inventory_management_project/inventory/views.py), [`inventory.views.UserViewSet`](inventory_management_project/inventory/views.py)
- Serializers: [`inventory.serializers.InventoryItemSerializer`](inventory_management_project/inventory/serializers.py), [`inventory.serializers.UserSerializer`](inventory_management_project/inventory/serializers.py), [`inventory.serializers.LoginSerializer`](inventory_management_project/inventory/serializers.py)
- Permissions: [`inventory.permissions.IsOwner`](inventory_management_project/inventory/permissions.py)
- URLs: [inventory_management_project/inventory/urls.py](inventory_management_project/inventory/urls.py), [inventory_management_project/inventory_management_project/urls.py](inventory_management_project/inventory_management_project/urls.py)
- Settings: [inventory_management_project/inventory_management_project/settings.py](inventory_management_project/inventory_management_project/settings.py)

## Features

- Custom user model (`AUTH_USER_MODEL=inventory.CustomUser`) with registration and profile management.
- JWT auth (SimpleJWT) with refresh token rotation and blacklist.
- Optional built-in JWT endpoints and custom login/logout endpoints.
- Inventory CRUD scoped to the authenticated owner.
- Validation: non-negative `quantity`, `price > 0`, and read-only `user`, `date_added`, `last_updated`.
- Filtering (category, price range, low stock threshold), search (name/category), ordering, and pagination (page size 10).
- Change history log on quantity updates and an explicit quantity adjustment endpoint.
- Admin interface for items and change logs.

## Project structure

```
inventory_management_project/
  manage.py
  inventory/
    models.py
    views.py
    serializers.py
    permissions.py
    urls.py
    admin.py
    tests.py
    migrations/
  inventory_management_project/
    settings.py
    urls.py
```

## Requirements

- Python 3.10+
- Django, DRF, django-filter, djangorestframework-simplejwt

Install:
```sh
pip install django djangorestframework django-filter djangorestframework-simplejwt
```

## Setup

1) Migrate and create a superuser
```sh
python manage.py migrate
python manage.py createsuperuser
```

2) Run
```sh
python manage.py runserver
```

3) Admin
- http://127.0.0.1:8000/admin/

## Authentication

SimpleJWT is used with refresh token rotation and blacklist (see [`SIMPLE_JWT`](inventory_management_project/inventory_management_project/settings.py)).

Two ways to obtain tokens:

- Built-in SimpleJWT endpoints (enabled if the package is installed; see [urls.py](inventory_management_project/inventory_management_project/urls.py)):
  - POST `/api/token/` with `{ "username": "...", "password": "..." }`
  - POST `/api/token/refresh/` with `{ "refresh": "<token>" }`

- Custom actions on the users endpoint:
  - POST `/api/users/user_login/` with `{ "username": "...", "password": "..." }` → returns `access` and `refresh`
  - POST `/api/users/user_logout/` with `{ "refresh": "<token>" }` → blacklists refresh token

Use header: `Authorization: Bearer <access_token>`

## API Reference

Base path: `/api/`

- Inventory
  - GET `/inventory/` — list your items (paginated)
  - POST `/inventory/` — create item (owned by you)
  - GET `/inventory/{id}/` — retrieve
  - PUT/PATCH `/inventory/{id}/` — update
  - DELETE `/inventory/{id}/` — delete
  - GET `/inventory/levels/` — compact list of id, name, category, price, quantity
  - GET `/inventory/{id}/history/` — item change history
  - POST `/inventory/{id}/adjust_quantity/` — body: `{ "delta": int, "reason": "optional" }` (floors at 0)

- Users (CustomUser)
  - POST `/users/` — register
  - GET `/users/` — admin only (list)
  - GET `/users/{id}/` — self or admin
  - PUT/PATCH `/users/{id}/` — self or admin
  - DELETE `/users/{id}/` — admin only
  - POST `/users/user_login/` — login, returns JWTs
  - POST `/users/user_logout/` — logout, blacklists refresh token

ViewSets:
- [`inventory.views.InventoryItemViewSet`](inventory_management_project/inventory/views.py)
- [`inventory.views.UserViewSet`](inventory_management_project/inventory/views.py)

## Models

- [`inventory.models.CustomUser`](inventory_management_project/inventory/models.py)
- [`inventory.models.InventoryItem`](inventory_management_project/inventory/models.py)
  - Fields: `user`, `name`, `description`, `quantity`, `price`, `category`, `date_added`, `last_updated`
- [`inventory.models.InventoryChangeLog`](inventory_management_project/inventory/models.py)
  - Fields: `item`, `performed_by`, `quantity_before`, `quantity_after`, `delta`, `reason`, `created_at`

Change logs are created on:
- PUT/PATCH to an item when `quantity` changes
- POST `/inventory/{id}/adjust_quantity/`

## Filtering, Search, Sorting, Pagination

Implemented in [`inventory.views.InventoryItemViewSet`](inventory_management_project/inventory/views.py) and DRF settings:
- Filters:
  - `?category=<value>`
  - `?price__gte=<min>&price__lte=<max>`
  - `?low_stock=<threshold>`
- Search: `?search=<term>` over `name`, `category`
- Ordering: `?ordering=name` or `?ordering=-price` (fields: `name, quantity, price, date_added, last_updated`)
- Pagination: default page size 10; use `?page=2`

## Permissions

- Inventory items: `IsAuthenticated` + owner-only via [`inventory.permissions.IsOwner`](inventory_management_project/inventory/permissions.py). Staff can see all items.
- Users: registration open; list/destroy admin only; retrieve/update self or admin.

## Validation and Serializer behavior

- [`inventory.serializers.InventoryItemSerializer`](inventory_management_project/inventory/serializers.py)
  - `quantity >= 0`, `price > 0`
  - `user`, `date_added`, `last_updated` are read-only
- [`inventory.serializers.UserSerializer`](inventory_management_project/inventory/serializers.py)
  - Unique email enforced (case-insensitive)
  - Password write-only and hashed
- [`inventory.serializers.LoginSerializer`](inventory_management_project/inventory/serializers.py)
  - Validates credentials for custom login action

## Example requests

- Obtain tokens (built-in)
```sh
curl -X POST http://127.0.0.1:8000/api/token/ -H "Content-Type: application/json" \
  -d '{"username":"user","password":"pass"}'
```

- Login (custom)
```sh
curl -X POST http://127.0.0.1:8000/api/users/user_login/ -H "Content-Type: application/json" \
  -d '{"username":"user","password":"pass"}'
```

- Create item
```sh
curl -X POST http://127.0.0.1:8000/api/inventory/ \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"name":"Apples","description":"Green","quantity":20,"price":"1.99","category":"produce"}'
```

- Adjust quantity
```sh
curl -X POST http://127.0.0.1:8000/api/inventory/1/adjust_quantity/ \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"delta": -3, "reason": "sale"}'
```
