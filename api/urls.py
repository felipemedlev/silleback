from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views # Import CartViewSet

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'brands', views.BrandViewSet, basename='brand')
router.register(r'occasions', views.OccasionViewSet, basename='occasion')
router.register(r'accords', views.AccordViewSet, basename='accord')
router.register(r'perfumes', views.PerfumeViewSet, basename='perfume')
router.register(r'cart', views.CartViewSet, basename='cart') # Register CartViewSet

# The API URLs are now determined automatically by the router.
# Additionally, we include the login URLs for the browsable API.
urlpatterns = [
    path('', include(router.urls)),
    path('survey/', views.SurveyResponseSubmitView.as_view(), name='survey-submit'),

    # If you need browsable API login/logout views (optional, requires rest_framework urls)
    # path('api-auth/', include('rest_framework.urls', namespace='rest_framework'))
]