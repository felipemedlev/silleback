from rest_framework import viewsets, permissions, generics, status # Add generics, status
from rest_framework.response import Response # Add Response
from rest_framework.decorators import action # Import action decorator
from django.shortcuts import get_object_or_404 # Import get_object_or_404
from django.db import transaction # Import transaction
from .models import ( # Add Cart, CartItem
    Brand, Occasion, Accord, Perfume, User, SurveyResponse, UserPerfumeMatch, # Removed Cart, CartItem from here as they are used in serializers
    Cart, CartItem
)
from .serializers import ( # Add CartSerializer, CartItemSerializer, CartItemAddSerializer
    BrandSerializer, OccasionSerializer, AccordSerializer, PerfumeSerializer,
    UserSerializer, SurveyResponseSerializer, CartSerializer, CartItemSerializer, CartItemAddSerializer
)
from decimal import Decimal # For price calculation

# Create your views here.

class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows brands to be viewed.
    """
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [permissions.AllowAny] # Allow anyone to view brands

class OccasionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows occasions to be viewed.
    """
    queryset = Occasion.objects.all()
    serializer_class = OccasionSerializer
    permission_classes = [permissions.AllowAny] # Allow anyone to view occasions

class AccordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows accords to be viewed.
    """
    queryset = Accord.objects.all()
    serializer_class = AccordSerializer
    permission_classes = [permissions.AllowAny] # Allow anyone to view accords

class PerfumeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows perfumes to be viewed.
    Supports filtering by brand, occasion, accord, gender.
    Supports searching by name and description.
    """
    queryset = Perfume.objects.select_related('brand').prefetch_related('occasions', 'accords').all()
    serializer_class = PerfumeSerializer
    permission_classes = [permissions.AllowAny] # Allow anyone to view perfumes
    # Add filter backends for searching and filtering later if needed
    # filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    # search_fields = ['name', 'description', 'brand__name']
    # filterset_fields = ['gender', 'brand', 'occasions', 'accords']

# Note: User views (register, login, me, etc.) are handled by Djoser URLs



class SurveyResponseSubmitView(generics.GenericAPIView):
    """
    API endpoint for submitting or updating the user's survey response.
    Requires authentication. Accepts POST requests with survey data in the body.
    """
    serializer_class = SurveyResponseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True) # Validate incoming data

        # Use update_or_create to handle both initial submission and updates
        survey_response, created = SurveyResponse.objects.update_or_create(
            user=request.user,
            defaults={'response_data': serializer.validated_data['response_data']}
        )

        # Return the saved data with appropriate status code
        response_serializer = self.get_serializer(survey_response)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(response_serializer.data, status=status_code)



# --- Cart ViewSet ---

# Removed CartItemAddSerializer definition from here - it belongs in serializers.py

class CartViewSet(viewsets.ViewSet):
    """
    ViewSet for managing the user's shopping cart.
    Requires authentication.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_cart(self, user):
        """Helper method to get or create a cart for the user."""
        cart, created = Cart.objects.get_or_create(user=user)
        return cart

    def list(self, request):
        """
        Retrieve the current user's cart.
        Corresponds to GET /api/cart/
        """
        cart = self.get_cart(request.user)
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='items')
    def add_item(self, request):
        """
        Add an item (perfume) to the cart.
        Corresponds to POST /api/cart/items/
        Expects: {"perfume_id": <id>, "quantity": <int>, "decant_size": <int/null>}
        """
        cart = self.get_cart(request.user)
        input_serializer = CartItemAddSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        perfume = input_serializer.validated_data['perfume_id']
        quantity = input_serializer.validated_data['quantity']
        decant_size = input_serializer.validated_data.get('decant_size')

        # Determine price - Use pricePerML if available and decant_size is provided,
        # otherwise maybe a default price or raise error if price cannot be determined.
        # This logic might need refinement based on actual pricing model.
        price = None
        if perfume.pricePerML and decant_size:
             # Ensure pricePerML is treated as Decimal
             price = (Decimal(str(perfume.pricePerML)) * Decimal(decant_size))
        elif perfume.pricePerML: # Fallback if no decant size but pricePerML exists? Needs clarification.
             # price = perfume.pricePerML # Or maybe price of a standard size?
             return Response({"detail": "Decant size required to calculate price."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Handle cases where price cannot be determined (e.g., no pricePerML)
             return Response({"detail": "Could not determine price for this item."}, status=status.HTTP_400_BAD_REQUEST)


        # Use transaction.atomic for safety when modifying cart items
        with transaction.atomic():
            # Check if item already exists (same perfume, same decant size)
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                perfume=perfume,
                decant_size=decant_size, # Match on decant size as well
                product_type='perfume', # Assuming adding perfumes for now
                defaults={'quantity': quantity, 'price_at_addition': price}
            )

            if not created:
                # If item exists, update quantity and potentially price_at_addition if needed
                cart_item.quantity += quantity
                # Optionally update price_at_addition if prices can change while item is in cart
                # cart_item.price_at_addition = price
                cart_item.save()

        # Return the updated cart state
        cart_serializer = CartSerializer(cart, context={'request': request})
        return Response(cart_serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


    @action(detail=True, methods=['delete'], url_path='items/(?P<item_pk>[^/.]+)')
    def remove_item(self, request, pk=None, item_pk=None):
         """
         Remove a specific item from the cart.
         Corresponds to DELETE /api/cart/items/{item_id}/
         Note: The 'pk' from the URL corresponds to the cart, but we ignore it
               as the cart is determined by the authenticated user. We use 'item_pk'.
         """
         cart = self.get_cart(request.user)
         cart_item = get_object_or_404(CartItem, pk=item_pk, cart=cart)
         cart_item.delete()
         return Response(status=status.HTTP_204_NO_CONTENT)


    @action(detail=False, methods=['delete'], url_path='clear') # Changed url_path to avoid conflict with list
    def clear_cart(self, request):
        """
        Remove all items from the cart.
        Corresponds to DELETE /api/cart/clear/ (Adjusted URL)
        """
        cart = self.get_cart(request.user)
        cart.items.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# --- End Cart ViewSet ---
