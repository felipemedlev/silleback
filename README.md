# SilleBack

SilleBack is a backend API for a personalized perfume subscription and e-commerce platform. It leverages Django, Django REST Framework, Celery, and a custom recommendation engine to deliver tailored perfume recommendations, manage user subscriptions, and handle e-commerce operations such as carts, orders, and coupons.

## Features

- **User Management**: Custom user model with email authentication, profile fields, and integration with Djoser for authentication endpoints.
- **Perfume Catalog**: Rich data model for perfumes, brands, accords, notes, and occasions, supporting advanced filtering and search.
- **Personalized Recommendations**: Machine learning-based recommendation engine using user survey responses and perfume accord profiles, powered by Pandas, NumPy, and a custom algorithm.
- **Survey System**: Dynamic survey questions to capture user scent preferences and gender, feeding into the recommendation engine.
- **Shopping Cart & Orders**: Full e-commerce flow with cart, cart items (individual perfumes or custom boxes), order creation, and order item tracking.
- **Subscription Tiers**: Multiple subscription levels with customizable decant sizes and criteria, managed via API.
- **Predefined & Custom Boxes**: Support for curated and user-configured perfume boxes.
- **Ratings & Favorites**: Users can rate and favorite perfumes, with ratings feeding into popularity metrics.
- **Coupons & Discounts**: Flexible coupon system with percentage/fixed discounts, usage limits, and expiry.
- **Admin & Management Commands**: Django admin integration and custom management commands for data maintenance.
- **Celery Integration**: Asynchronous tasks for updating recommendations and other background jobs, using Redis as a broker.

## Tech Stack

- **Backend**: Python, Django 5.x, Django REST Framework
- **Database**: PostgreSQL (default), SQLite (for development)
- **Task Queue**: Celery with Redis
- **Data Science**: Pandas, NumPy, SciPy
- **Authentication**: Djoser, SimpleJWT, Social Auth
- **API Docs**: OpenAPI/Swagger (via DRF)

## Project Structure

```
api/                # Main Django app with models, views, serializers, tasks, recommendations
silleconfig/        # Django project settings and configuration
management/         # Custom Django management commands
migrations/         # Database migrations
recommendations/    # Recommendation engine logic
requirements.txt    # Python dependencies
manage.py           # Django management script
data/               # Data files for initial import and reference
```

## Getting Started

### Prerequisites
- Python 3.11+
- PostgreSQL (or SQLite for local dev)
- Redis (for Celery tasks)

### Installation
1. **Clone the repository**
2. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```
3. **Configure environment variables** (see `.env.example`):
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
   - `CELERY_BROKER_URL`
4. **Apply migrations**:
   ```
   python manage.py migrate
   ```
5. **Create a superuser**:
   ```
   python manage.py createsuperuser
   ```
6. **Run the development server**:
   ```
   python manage.py runserver
   ```
7. **Start Celery worker** (in a separate terminal):
   ```
   celery -A silleconfig worker --loglevel=info
   ```

### API Usage
- The API is organized under `/api/` endpoints (see `api/urls.py`).
- Authentication via token or JWT (Djoser endpoints).
- Key endpoints:
  - `/api/perfumes/` — Perfume catalog & search
  - `/api/recommendations/` — Personalized recommendations
  - `/api/cart/` — Shopping cart management
  - `/api/orders/` — Order creation and history
  - `/api/subscription/` — Subscription management
  - `/api/coupons/` — Coupon validation
  - `/api/survey/` — Survey questions and responses

### Recommendation Engine
- Users complete a survey about their scent preferences and gender.
- The engine computes a vector representation and matches it against the weighted accord profiles of all perfumes.
- Popularity and ratings are used to boost recommendations.
- Results are normalized and stored for fast retrieval.

### Data Import
- Initial data (perfumes, brands, boxes, etc.) can be loaded from CSV/JSON files in the `data/` directory using custom management commands.

## License
[MIT](LICENSE)

## Author
Felipe Mediavilla

---

*This project is designed to showcase advanced Django backend skills, API design, and recommendation system implementation for recruiters and collaborators.*
