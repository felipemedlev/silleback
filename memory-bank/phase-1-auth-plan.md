# Finalized Plan: Phase 1 - Authentication &amp; Core User Setup

**Goal:** Implement user registration, login, logout, and profile management API endpoints using `djoser` for token-based authentication.

**Confirmed Choices:**
*   Authentication Library: `djoser`
*   Frontend Development Origin: `http://localhost:8081`

---

## Implementation Steps:

1.  **Install Dependencies:**
    *   Activate virtual environment (`venv`).
    *   Install: `pip install djangorestframework django-cors-headers djoser djangorestframework-simplejwt`

2.  **Configure `silleconfig/settings.py`:**
    *   Add to `INSTALLED_APPS`: `'rest_framework'`, `'rest_framework.authtoken'`, `'corsheaders'`, `'djoser'`, `'api'`
    *   Set `AUTH_USER_MODEL = 'api.User'`
    *   Configure `REST_FRAMEWORK`:
        ```python
        REST_FRAMEWORK = {
            'DEFAULT_AUTHENTICATION_CLASSES': (
                'rest_framework.authentication.TokenAuthentication',
            ),
            'DEFAULT_PERMISSION_CLASSES': (
                'rest_framework.permissions.IsAuthenticatedOrReadOnly',
            )
        }
        ```
    *   Add `corsheaders.middleware.CorsMiddleware` to `MIDDLEWARE` (high up, before `CommonMiddleware`).
    *   Configure CORS:
        ```python
        CORS_ALLOWED_ORIGINS = [
            'http://localhost:8081',
            'http://127.0.0.1:8081', # Include loopback IP
        ]
        # Or temporarily: CORS_ALLOW_ALL_ORIGINS = True
        ```
    *   Add `DJOSER` settings:
        ```python
        DJOSER = {
            'PASSWORD_RESET_CONFIRM_URL': '#/password/reset/confirm/{uid}/{token}',
            'USERNAME_RESET_CONFIRM_URL': '#/username/reset/confirm/{uid}/{token}',
            'ACTIVATION_URL': '#/activate/{uid}/{token}',
            'SEND_ACTIVATION_EMAIL': False,
            'USER_ID_FIELD': 'id',
            'LOGIN_FIELD': 'email',
            'SERIALIZERS': {
                 'user_create': 'api.serializers.UserCreateSerializer',
                 'user': 'api.serializers.UserSerializer',
                 'current_user': 'api.serializers.UserSerializer',
            },
        }
        ```

3.  **Define Custom User Model (`api/models.py`):**
    *   Create `User(AbstractUser)` with `email` as `USERNAME_FIELD` (unique), `phone`, `address`. Make `username` optional.
        ```python
        from django.contrib.auth.models import AbstractUser
        from django.db import models

        class User(AbstractUser):
            REQUIRED_FIELDS = ['username'] # Still needed by createsuperuser if username is used
            USERNAME_FIELD = 'email'

            email = models.EmailField(unique=True)
            phone = models.CharField(max_length=20, blank=True, null=True)
            address = models.TextField(blank=True, null=True)

            # Make username optional if email is the primary identifier
            username = models.CharField(
                max_length=150,
                unique=False, # Allow multiple users to potentially have no username or same placeholder
                blank=True,
                null=True
            )

            def __str__(self):
                return self.email
        ```

4.  **Create User Serializers (`api/serializers.py`):**
    *   Create `UserCreateSerializer(BaseUserCreateSerializer)` including `id`, `email`, `username`, `password`, `phone`, `address`.
    *   Create `UserSerializer(BaseUserSerializer)` including `id`, `email`, `username`, `phone`, `address`.
        ```python
        from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
        from djoser.serializers import UserSerializer as BaseUserSerializer
        from django.contrib.auth import get_user_model

        User = get_user_model()

        class UserCreateSerializer(BaseUserCreateSerializer):
            class Meta(BaseUserCreateSerializer.Meta):
                model = User
                fields = ('id', 'email', 'username', 'password', 'phone', 'address')

        class UserSerializer(BaseUserSerializer):
            class Meta(BaseUserSerializer.Meta):
                model = User
                fields = ('id', 'email', 'username', 'phone', 'address')
                read_only_fields = ('email',)
        ```

5.  **Configure URLs:**
    *   **`silleconfig/urls.py`:** Include `djoser.urls` and `djoser.urls.authtoken`. Ensure `api/` is included. Remove duplicate `admin/`.
        ```python
        from django.contrib import admin
        from django.urls import path, include

        urlpatterns = [
            path('admin/', admin.site.urls),
            path('api/', include('api.urls')),
            path('api/auth/', include('djoser.urls')),
            path('api/auth/', include('djoser.urls.authtoken')),
        ]
        ```
    *   **`api/urls.py`:** Create if it doesn't exist, keep empty for now.
        ```python
        # api/urls.py
        from django.urls import path
        from . import views

        urlpatterns = [
            # App-specific endpoints will go here later
        ]
        ```

6.  **Apply Migrations:**
    *   `python manage.py makemigrations api`
    *   `python manage.py migrate`

7.  **Initial Testing (API Client):**
    *   Test endpoints: `POST /api/auth/users/`, `POST /api/auth/token/login/`, `POST /api/auth/token/logout/`, `GET /api/auth/users/me/`, `PUT /api/auth/users/me/`.

---

## Mermaid Diagram (Registration):

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant RooCode as Roo (Code Mode)
    participant Django as Django Backend
    participant DB as Database

    Dev->>RooCode: Request Phase 1 Implementation (via Architect Plan)
    RooCode->>Django: Install djangorestframework, django-cors-headers, djoser, etc.
    RooCode->>Django: Configure settings.py (INSTALLED_APPS, REST_FRAMEWORK, CORS, DJOSER, AUTH_USER_MODEL)
    RooCode->>Django: Define api.models.User(AbstractUser)
    RooCode->>Django: Define api.serializers.UserCreateSerializer/UserSerializer
    RooCode->>Django: Configure silleconfig/urls.py (include djoser.urls)
    RooCode->>Django: Run python manage.py makemigrations api
    Django->>DB: Create/Update migrations table
    RooCode->>Django: Run python manage.py migrate
    Django->>DB: Apply migrations (create api_user table, etc.)
    Note over Dev, Django: Manual Testing Step
    Dev->>Django: POST /api/auth/users/ (Register Request: email, username?, password, phone?, address?)
    Django->>Django: Validate registration data via UserCreateSerializer
    alt Data Valid
        Django->>DB: Create User record in api_user table
        DB-->>Django: User created (ID assigned)
        Django-->>Dev: 201 Created (User data: id, email, username, phone, address)
    else Data Invalid
        Django-->>Dev: 400 Bad Request (Validation errors)
    end