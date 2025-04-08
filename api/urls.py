from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views # Import CartViewSet, PredefinedBoxViewSet, SubscriptionViewSet, OrderViewSet, FavoriteViewSet, PerfumeRatingView

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'brands', views.BrandViewSet, basename='brand')
router.register(r'occasions', views.OccasionViewSet, basename='occasion')
router.register(r'accords', views.AccordViewSet, basename='accord')
router.register(r'perfumes', views.PerfumeViewSet, basename='perfume')
router.register(r'cart', views.CartViewSet, basename='cart') # Register CartViewSet
router.register(r'boxes/predefined', views.PredefinedBoxViewSet, basename='predefinedbox') # Register PredefinedBoxViewSet
router.register(r'subscriptions', views.SubscriptionViewSet, basename='subscription') # Register SubscriptionViewSet
router.register(r'orders', views.OrderViewSet, basename='order') # Register OrderViewSet
router.register(r'favorites', views.FavoriteViewSet, basename='favorite') # Register FavoriteViewSet

# The API URLs are now determined automatically by the router.
# Additionally, we include the login URLs for the browsable API.
urlpatterns = [
    path('', include(router.urls)), # Includes router-generated URLs like /favorites/, /favorites/{pk}/, /favorites/perfume/{perfume_pk}/
    path('survey/', views.SurveyResponseSubmitView.as_view(), name='survey-submit'),
    # Add path for perfume rating view (GET/POST)
    path('perfumes/<int:perfume_id>/rating/', views.PerfumeRatingView.as_view(), name='perfume-rating'),

    # If you need browsable API login/logout views (optional, requires rest_framework urls)
    # path('api-auth/', include('rest_framework.urls', namespace='rest_framework'))
]