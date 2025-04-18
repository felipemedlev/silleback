from rest_framework import viewsets, permissions, generics, status, mixins # Add generics, status, mixins
from rest_framework.response import Response # Add Response
from rest_framework import serializers
from rest_framework.decorators import action # Import action decorator
from django.shortcuts import get_object_or_404 # Import get_object_or_404
from rest_framework import filters as drf_filters
from django_filters.rest_framework import DjangoFilterBackend
from .filters import PerfumeFilter # Import the custom filterset
from django.db import transaction # Import transaction
# Q object import removed as it's no longer used in this view
from .models import ( # Add Cart, CartItem, PredefinedBox, SubscriptionTier, UserSubscription, Order, OrderItem, Rating, Favorite
    Brand, Occasion, Accord, Perfume, User, SurveyResponse, UserPerfumeMatch,
    Cart, CartItem, PredefinedBox, SubscriptionTier, UserSubscription,
    Order, OrderItem, Rating, Favorite, SurveyQuestion # Added SurveyQuestion
)
from .serializers import ( # Add CartSerializer, CartItemSerializer, CartItemAddSerializer, PredefinedBoxSerializer, SubscriptionTierSerializer, UserSubscriptionSerializer, SubscribeSerializer, OrderSerializer, OrderItemSerializer, OrderCreateSerializer, RatingSerializer, FavoriteSerializer, FavoriteListSerializer
    BrandSerializer, OccasionSerializer, AccordSerializer, PerfumeSerializer,
    UserSerializer, SurveyResponseSerializer, CartSerializer, CartItemSerializer, CartItemAddSerializer,
    PredefinedBoxSerializer, SubscriptionTierSerializer, UserSubscriptionSerializer, SubscribeSerializer,
    OrderSerializer, OrderItemSerializer, OrderCreateSerializer,
    RatingSerializer, FavoriteSerializer, FavoriteListSerializer
)
from decimal import Decimal, InvalidOperation # Import InvalidOperation

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
    # Add filter backends for searching and filtering
    filter_backends = [drf_filters.SearchFilter, DjangoFilterBackend]
    filterset_class = PerfumeFilter # Use the custom filterset class
    search_fields = ['name', 'description', 'brand__name'] # Fields for ?search=...

    @action(detail=False, methods=['get'], url_path='by_external_ids')
    def by_external_ids(self, request):
        """
        Retrieve a list of perfumes based on their external IDs.
        Expects a comma-separated list of IDs in the 'external_ids' query parameter.
        e.g., /api/perfumes/by_external_ids/?external_ids=id1,id2,id3
        """
        external_ids_str = request.query_params.get('external_ids', None)
        if not external_ids_str:
            return Response({"detail": "Missing 'external_ids' query parameter."}, status=status.HTTP_400_BAD_REQUEST)

        external_ids_list = [pid.strip() for pid in external_ids_str.split(',') if pid.strip()]
        if not external_ids_list:
            return Response({"detail": "'external_ids' query parameter cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset().filter(external_id__in=external_ids_list)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

# --- Survey Questions API View ---
from rest_framework import generics

class SurveyQuestionsView(generics.GenericAPIView):
    """
    API endpoint to fetch the list of survey questions (gender + selected accords).
    """
    permission_classes = [permissions.AllowAny]
    queryset = SurveyQuestion.objects.filter(is_active=True) # Use the new model

    def get(self, request, *args, **kwargs):
        """
        Fetch active survey questions from the database.
        If question_id is provided in kwargs, return that specific question.
        """
        # Check if we're fetching a specific question
        question_id = kwargs.get('question_id')

        if question_id:
            # Fetch single question by ID
            try:
                question = SurveyQuestion.objects.select_related('accord').get(pk=question_id)
            except SurveyQuestion.DoesNotExist:
                return Response({"detail": "Question not found."}, status=status.HTTP_404_NOT_FOUND)

            # Format response based on question type
            if question.question_type == 'gender':
                result = {
                    "id": str(question.pk),
                    "type": "gender",
                    "question": question.text,
                    "options": question.options
                }
            elif question.question_type == 'accord' and question.accord:
                result = {
                    "id": str(question.pk),
                    "accord": question.accord.name,
                    "description": question.accord.description or "",
                    "question": question.text
                }
            else:
                # Generic format for other types
                result = {
                    "id": str(question.pk),
                    "type": question.question_type,
                    "question": question.text
                }

            return Response(result)
        else:
            # Fetch all active questions, ordered correctly, prefetching related accord if present
            questions_qs = SurveyQuestion.objects.filter(is_active=True).select_related('accord').order_by('order')
            formatted_questions = []

            for question in questions_qs:
                if question.question_type == 'gender':
                    # Format gender question using its text and options JSON
                    formatted_questions.append({
                        "id": str(question.pk), # Use primary key as ID
                        "type": "gender",
                        "question": question.text,
                        "options": question.options # Assumes options JSON is correctly formatted in DB
                    })
                elif question.question_type == 'accord' and question.accord:
                     # Format accord question using its text and related accord info
                    formatted_questions.append({
                        "id": str(question.pk), # Use primary key as ID
                        "accord": question.accord.name,
                        "description": question.accord.description or "",
                        # Include the question text itself, as the frontend might need it
                        "question": question.text
                    })
                # Add elif blocks here for other question types if they are added later

            return Response(formatted_questions)
# Removed search_fields from SurveyQuestionsView as it belongs in PerfumeViewSet
    # filterset_fields = ['gender', 'brand', 'occasions', 'accords'] # Replaced by filterset_class
# Removed filterset_class from SurveyQuestionsView as it belongs in PerfumeViewSet

# Add SurveyQuestionViewSet for accessing individual questions
class SurveyQuestionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows individual survey questions to be viewed.
    """
    queryset = SurveyQuestion.objects.all().select_related('accord')
    permission_classes = [permissions.AllowAny]  # Allow anyone to view questions

    def get_serializer_class(self):
        """
        Custom serialization based on the question type.
        """
        # We'll implement serialization directly in the retrieve method
        return None

    def retrieve(self, request, *args, **kwargs):
        question = self.get_object()

        # Format response based on question type
        if question.question_type == 'gender':
            result = {
                "id": str(question.pk),
                "type": "gender",
                "question": question.text,
                "options": question.options
            }
        elif question.question_type == 'accord' and question.accord:
            result = {
                "id": str(question.pk),
                "accord": question.accord.name,
                "description": question.accord.description or "",
                "question": question.text
            }
        else:
            # Generic format for other types
            result = {
                "id": str(question.pk),
                "type": question.question_type,
                "question": question.text
            }

        return Response(result)

# Note: User views (register, login, me, etc.) are handled by Djoser URLs

class SurveyResponseSubmitView(generics.GenericAPIView):
    """
    API endpoint for submitting or updating the user's survey response.
    Requires authentication. Accepts POST requests with survey data in the body.
    """
    serializer_class = SurveyResponseSerializer
    permission_classes = [permissions.AllowAny] # Allow anonymous POST, but logic will check auth

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True) # Validate incoming data

        # Only save if the user is authenticated
        if request.user.is_authenticated:
            # Use update_or_create to handle both initial submission and updates
            survey_response, created = SurveyResponse.objects.update_or_create(
                user=request.user,
                defaults={'response_data': serializer.validated_data['response_data']}
            )
            # Return the saved data with appropriate status code
            response_serializer = self.get_serializer(survey_response)
            status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
            return Response(response_serializer.data, status=status_code)
        else:
            # For anonymous users, just validate and return success without saving
            # Or return a specific status/message if needed, but 200 OK is fine for now
            # as the frontend will handle the actual saving post-login.
            return Response(serializer.validated_data, status=status.HTTP_200_OK)



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


# --- Box ViewSets ---

class PredefinedBoxViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows predefined boxes to be viewed.
    """
    queryset = PredefinedBox.objects.prefetch_related('perfumes').all() # Prefetch perfumes for efficiency
    serializer_class = PredefinedBoxSerializer
    permission_classes = [permissions.AllowAny] # Allow anyone to view predefined boxes
    filter_backends = [DjangoFilterBackend] # Add filter backend
    filterset_fields = ['gender'] # Enable filtering by gender

# --- End Box ViewSets ---


# --- Subscription ViewSet ---

class SubscriptionViewSet(viewsets.ViewSet):
    """
    ViewSet for managing user subscriptions.
    """
    permission_classes = [permissions.IsAuthenticated] # Default to authenticated

    @action(detail=False, methods=['get'], url_path='tiers', permission_classes=[permissions.AllowAny])
    def list_tiers(self, request):
        """
        List available subscription tiers.
        Corresponds to GET /api/subscriptions/tiers/
        """
        tiers = SubscriptionTier.objects.all()
        serializer = SubscriptionTierSerializer(tiers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='status')
    def get_status(self, request):
        """
        Get the current user's subscription status.
        Corresponds to GET /api/subscriptions/status/
        """
        try:
            subscription = UserSubscription.objects.get(user=request.user)
            serializer = UserSubscriptionSerializer(subscription)
            return Response(serializer.data)
        except UserSubscription.DoesNotExist:
            return Response({"detail": "No active subscription found."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='subscribe')
    def subscribe(self, request):
        """
        Subscribe the current user to a selected tier.
        Corresponds to POST /api/subscriptions/subscribe/
        Expects: {"tier_id": <id>}
        (Payment integration to be added later)
        """
        input_serializer = SubscribeSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        tier = input_serializer.validated_data['tier_id']

        # Use update_or_create to handle new subscriptions or changing tiers/reactivating
        subscription, created = UserSubscription.objects.update_or_create(
            user=request.user,
            defaults={'tier': tier, 'is_active': True} # Ensure subscription is active
        )

        # Placeholder: Add payment processing logic here in a real application

        response_serializer = UserSubscriptionSerializer(subscription)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(response_serializer.data, status=status_code)

    @action(detail=False, methods=['post'], url_path='unsubscribe')
    def unsubscribe(self, request):
        """
        Unsubscribe (deactivate) the current user's subscription.
        Corresponds to POST /api/subscriptions/unsubscribe/
        """
        try:
            subscription = UserSubscription.objects.get(user=request.user, is_active=True)
            subscription.is_active = False
            # Optionally set tier to None or keep it for history
            # subscription.tier = None
            subscription.save()

            # Placeholder: Add logic to cancel payment provider subscription here

            serializer = UserSubscriptionSerializer(subscription)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except UserSubscription.DoesNotExist:
            return Response({"detail": "No active subscription found to unsubscribe."}, status=status.HTTP_404_NOT_FOUND)

# --- End Subscription ViewSet ---


# --- Order ViewSet ---

class OrderViewSet(viewsets.GenericViewSet, # Mixin for standard actions
                   mixins.ListModelMixin,    # Handles GET /api/orders/
                   mixins.RetrieveModelMixin, # Handles GET /api/orders/{id}/
                   mixins.CreateModelMixin):  # Handles POST /api/orders/
    """
    ViewSet for creating and viewing user orders.
    """
    serializer_class = OrderSerializer # Default serializer for list/retrieve
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """ Ensure users only see their own orders. """
        # Eager load related items and perfumes to optimize DB queries for list/retrieve
        return Order.objects.filter(user=self.request.user).prefetch_related('items', 'items__perfume')

    def get_serializer_class(self):
        """ Use OrderCreateSerializer for the create action. """
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer # Use default for list/retrieve

    def perform_create(self, serializer):
        """
        Custom logic to create an order from the user's cart.
        Handles transaction atomicity, copies cart items to order items, and clears the cart.
        """
        user = self.request.user
        # shipping_address is validated by OrderCreateSerializer
        shipping_address = serializer.validated_data['shipping_address']
        # Payment details would be handled here later

        try:
            # Prefetch items and related perfumes for efficiency
            cart = Cart.objects.prefetch_related('items', 'items__perfume').get(user=user)
        except Cart.DoesNotExist:
            # Use DRF's validation error for consistency
            raise serializers.ValidationError("Cart not found or is empty.")

        cart_items = cart.items.all()
        if not cart_items.exists():
            raise serializers.ValidationError("Cannot create an order from an empty cart.")

        # Use a database transaction to ensure all steps succeed or fail together
        with transaction.atomic():
            # 1. Calculate total price from cart items
            total_price = Decimal('0.00')
            for item in cart_items:
                # Use price_at_addition stored in CartItem
                if item.price_at_addition is not None:
                    try:
                        # Ensure calculation uses Decimals
                        total_price += (Decimal(item.price_at_addition) * Decimal(item.quantity))
                    except (TypeError, InvalidOperation):
                         # Log this error in a real application
                         raise serializers.ValidationError(f"Invalid price or quantity found for cart item {item.id}.")
                else:
                    # This indicates an issue during cart addition - price should always be set.
                    # Log this error
                    raise serializers.ValidationError(f"Missing price for cart item {item.id}. Cannot create order.")


            # 2. Create the Order instance
            order = Order.objects.create(
                user=user,
                total_price=total_price,
                shipping_address=shipping_address,
                status='pending' # Initial status, update after payment success later
                # Add payment details reference here later (e.g., payment_intent_id)
            )

            # 3. Create OrderItem instances from CartItems
            order_items_to_create = []
            for cart_item in cart_items:
                # Determine item name and description based on type
                item_name = "Box Item" # Default for boxes
                item_description = "Predefined/Custom Box"
                if cart_item.product_type == 'perfume' and cart_item.perfume:
                    item_name = cart_item.perfume.name
                    item_description = cart_item.perfume.description

                order_items_to_create.append(
                    OrderItem(
                        order=order,
                        perfume=cart_item.perfume, # Link to perfume if applicable
                        product_type=cart_item.product_type,
                        quantity=cart_item.quantity,
                        decant_size=cart_item.decant_size,
                        price_at_purchase=cart_item.price_at_addition, # Crucial: Use the price stored at time of cart addition
                        box_configuration=cart_item.box_configuration, # Copy box config if it was a box item
                        item_name=item_name, # Store name at time of purchase
                        item_description=item_description # Store description at time of purchase
                    )
                )
            # Use bulk_create for efficiency if creating many items
            OrderItem.objects.bulk_create(order_items_to_create)

            # 4. Clear the user's cart after successful order creation
            # It's important this happens *within* the transaction
            cart.items.all().delete()

            # 5. Placeholder: Trigger payment processing here.
            # If payment fails, the transaction rollback would undo order creation.
            # If payment is async, update order status later via webhook/callback.

            # Set the instance on the serializer for the response in CreateModelMixin
            # This ensures the response contains the data of the *created* order.
            serializer.instance = order


# --- End Order ViewSet ---


# --- Rating & Favorite Views ---

class PerfumeRatingView(generics.GenericAPIView):
    """
    View for retrieving or creating/updating the authenticated user's rating
    for a specific perfume.
    Accessed via /api/perfumes/{perfume_id}/rating/
    """
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_perfume(self):
        """ Helper to get the perfume object from URL kwargs. """
        perfume_id = self.kwargs.get('perfume_id')
        return get_object_or_404(Perfume, pk=perfume_id)

    def get(self, request, *args, **kwargs):
        """ Handle GET requests to retrieve the user's rating for the perfume. """
        perfume = self.get_perfume()
        try:
            rating = Rating.objects.get(user=request.user, perfume=perfume)
            serializer = self.get_serializer(rating)
            return Response(serializer.data)
        except Rating.DoesNotExist:
            # It's okay if no rating exists yet, return 404 as per REST principles
            return Response({"detail": "No rating found for this perfume by the user."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, *args, **kwargs):
        """ Handle POST requests to create or update the user's rating. """
        perfume = self.get_perfume()
        # Check if a rating already exists to pass it to the serializer for update
        try:
            instance = Rating.objects.get(user=request.user, perfume=perfume)
            serializer = self.get_serializer(instance, data=request.data)
        except Rating.DoesNotExist:
            instance = None
            serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        # Use update_or_create for atomicity and simplicity
        rating_instance, created = Rating.objects.update_or_create(
            user=request.user,
            perfume=perfume,
            defaults={'rating': serializer.validated_data['rating']}
        )

        # Placeholder: Trigger ML prediction recalculation here (future phase)
        # Example: trigger_ml_recalculation.delay(user_id=request.user.id)

        # Return the saved/updated rating instance
        response_serializer = self.get_serializer(rating_instance)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(response_serializer.data, status=status_code)

class FavoriteViewSet(mixins.ListModelMixin,
                      mixins.CreateModelMixin,
                      # mixins.DestroyModelMixin, # Using custom delete action instead
                      viewsets.GenericViewSet):
    """
    ViewSet for managing user favorites.
    - GET /api/favorites/ : List user's favorites
    - POST /api/favorites/ : Add a favorite (expects {"perfume_id": id})
    - DELETE /api/favorites/perfume/{perfume_id}/ : Remove favorite by perfume ID (custom action)
    - DELETE /api/favorites/{favorite_id}/ : Remove favorite by favorite ID (standard, if DestroyModelMixin used)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """ Ensure users only see their own favorites, prefetch related data. """
        return Favorite.objects.filter(user=self.request.user).select_related('perfume', 'perfume__brand')

    def get_serializer_class(self):
        """ Use different serializers for list vs create. """
        if self.action == 'list':
            return FavoriteListSerializer # Shows perfume details
        # Use FavoriteSerializer for create action
        return FavoriteSerializer

    def perform_create(self, serializer):
        """ Set the user automatically when creating a favorite. """
        # Pass request context to serializer for user assignment and get_or_create logic
        serializer.save(user=self.request.user) # Serializer's create method handles get_or_create

    # If using DestroyModelMixin, it handles DELETE /api/favorites/{pk}/
    # def destroy(self, request, *args, **kwargs):
    #     instance = self.get_object()
    #     self.perform_destroy(instance)
    #     return Response(status=status.HTTP_204_NO_CONTENT)
    #
    # def perform_destroy(self, instance):
    #     instance.delete()

    @action(detail=False, methods=['delete'], url_path='perfume/(?P<perfume_pk>[^/.]+)')
    def remove_by_perfume(self, request, perfume_pk=None):
        """
        Custom action to remove a favorite based on the perfume ID.
        Corresponds to DELETE /api/favorites/perfume/{perfume_id}/
        """
        user = request.user
        perfume = get_object_or_404(Perfume, pk=perfume_pk)
        # Find the specific favorite entry for this user and perfume
        favorite = get_object_or_404(Favorite, user=user, perfume=perfume)
        favorite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- End Rating & Favorite Views ---
