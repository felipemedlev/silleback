from rest_framework import viewsets, permissions, generics, status, mixins
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from rest_framework import filters as drf_filters
from django_filters.rest_framework import DjangoFilterBackend
from .filters import PerfumeFilter, UserPerfumeMatchFilter
from django.db import transaction
from django.utils import timezone
from .models import (
    Brand, Occasion, Accord, Perfume, User, SurveyResponse, UserPerfumeMatch,
    Cart, CartItem, PredefinedBox, SubscriptionTier, UserSubscription,
    Order, OrderItem, Rating, Favorite, SurveyQuestion, Coupon
)
from .serializers import (
    BrandSerializer, OccasionSerializer, AccordSerializer, PerfumeSerializer,
    UserSerializer, SurveyResponseSerializer, CartSerializer, CartItemSerializer, CartItemAddSerializer,
    PredefinedBoxSerializer, SubscriptionTierSerializer, UserSubscriptionSerializer, SubscribeSerializer,
    OrderSerializer, OrderItemSerializer, OrderCreateSerializer,
    RatingSerializer, FavoriteSerializer, FavoriteListSerializer, CouponSerializer
)
from decimal import Decimal, InvalidOperation
import logging

from .tasks import update_user_recommendations

logger = logging.getLogger(__name__)


class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [permissions.AllowAny]

class OccasionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Occasion.objects.all()
    serializer_class = OccasionSerializer
    permission_classes = [permissions.AllowAny]

class AccordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Accord.objects.all()
    serializer_class = AccordSerializer
    permission_classes = [permissions.AllowAny]

class PerfumeViewSet(viewsets.ReadOnlyModelViewSet):
    # Base queryset defined in get_queryset now, but we can set a fallback or move logic there completely.
    # We'll set a basic one here but override it in get_queryset
    queryset = Perfume.objects.select_related('brand').prefetch_related('occasions', 'accords').all()
    serializer_class = PerfumeSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [drf_filters.SearchFilter, DjangoFilterBackend, drf_filters.OrderingFilter]
    filterset_class = PerfumeFilter
    search_fields = ['name', 'description', 'brand__name']
    ordering_fields = ['price_per_ml', 'overall_rating', 'longevity_rating', 'sillage_rating', 'price_value_rating', 'match_percentage', 'name']

    @action(detail=False, methods=['get'], url_path='by_external_ids')
    def by_external_ids(self, request):
        external_ids_str = request.query_params.get('external_ids', None)
        if not external_ids_str:
            return Response({"detail": "Missing 'external_ids' query parameter."}, status=status.HTTP_400_BAD_REQUEST)

        external_ids_list = [pid.strip() for pid in external_ids_str.split(',') if pid.strip()]
        if not external_ids_list:
            return Response({"detail": "'external_ids' query parameter cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset().filter(external_id__in=external_ids_list)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_queryset(self):
        queryset = Perfume.objects.select_related('brand').prefetch_related('occasions', 'accords')

        user = self.request.user
        if user.is_authenticated:
            # Subquery to get match_percentage for this user and perfume
            from django.db.models import Subquery, OuterRef, Value, DecimalField
            from django.db.models.functions import Coalesce

            match_qs = UserPerfumeMatch.objects.filter(
                user=user,
                perfume=OuterRef('pk')
            ).values('match_percentage')[:1]

            queryset = queryset.annotate(
                match_percentage=Coalesce(
                    Subquery(match_qs),
                    Value(0, output_field=DecimalField(max_digits=4, decimal_places=3))
                )
            )
        else:
             # Annotate with 0 for anonymous users so sorting behaves like 0%
            from django.db.models import Value, DecimalField
            queryset = queryset.annotate(
                match_percentage=Value(0, output_field=DecimalField(max_digits=4, decimal_places=3))
            )

        return queryset

# --- Survey Questions API View ---
from rest_framework import generics

class SurveyQuestionsView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    queryset = SurveyQuestion.objects.filter(is_active=True)

    def get(self, request, *args, **kwargs):
        question_id = kwargs.get('question_id')

        if question_id:
            try:
                question = SurveyQuestion.objects.select_related('accord').get(pk=question_id)
            except SurveyQuestion.DoesNotExist:
                return Response({"detail": "Question not found."}, status=status.HTTP_404_NOT_FOUND)

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
                result = {
                    "id": str(question.pk),
                    "type": question.question_type,
                    "question": question.text
                }

            return Response(result)
        else:
            questions_qs = SurveyQuestion.objects.filter(is_active=True).select_related('accord').order_by('order')
            formatted_questions = []

            for question in questions_qs:
                if question.question_type == 'gender':
                    formatted_questions.append({
                        "id": str(question.pk),
                        "type": "gender",
                        "question": question.text,
                        "options": question.options
                    })
                elif question.question_type == 'accord' and question.accord:
                    formatted_questions.append({
                        "id": str(question.pk),
                        "accord": question.accord.name,
                        "description": question.accord.description or "",
                        "question": question.text
                    })

            return Response(formatted_questions)


class SurveyQuestionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SurveyQuestion.objects.all().select_related('accord')
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        return None

    def retrieve(self, request, *args, **kwargs):
        question = self.get_object()

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
            result = {
                "id": str(question.pk),
                "type": question.question_type,
                "question": question.text
            }

        return Response(result)


class SurveyResponseSubmitView(generics.GenericAPIView):
    serializer_class = SurveyResponseSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        # Debug Logging
        logger.info(f"Survey Submission Request: User={request.user}, IsAuth={request.user.is_authenticated}")
        logger.info(f"Survey Submission Headers: Auth={request.headers.get('Authorization', 'None')}")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if request.user.is_authenticated:
            logger.info(f"Processing authenticated survey for user {request.user.pk}")
            survey_response, created = SurveyResponse.objects.update_or_create(
                user=request.user,
                defaults={'response_data': serializer.validated_data['response_data']}
            )

            logger.info(f"Survey saved in DB. Created={created}, ResponseID={survey_response.pk}")
            logger.info(f"Triggering recommendation update task for user {request.user.pk}")

            # Race condition fix: Do NOT synchronously delete existing matches.
            # Let the background task update/replace them to ensure the user always sees *something* while calculating.
            # with transaction.atomic():
            #     deleted_count, _ = UserPerfumeMatch.objects.filter(user=request.user).delete()
            #     logger.info(f"Deleted {deleted_count} existing perfume matches for user {request.user.pk} before recalculation.")

            update_user_recommendations.delay(user_pk=request.user.pk)

            response_serializer = self.get_serializer(survey_response)
            status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
            return Response(response_serializer.data, status=status_code)
        else:
            logger.warning("Request processed as anonymous (not saving to DB)")
            return Response(serializer.validated_data, status=status.HTTP_200_OK)



# --- Cart ViewSet ---
class CartViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_cart(self, user):
        cart, created = Cart.objects.get_or_create(user=user)
        return cart

    def list(self, request):
        cart = self.get_cart(request.user)
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='items')
    def add_item(self, request):
        cart = self.get_cart(request.user)
        input_serializer = CartItemAddSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        validated_data = input_serializer.validated_data
        product_type = validated_data['product_type']
        quantity = validated_data['quantity']

        perfume = None
        decant_size = None
        price = None
        box_configuration = None
        item_defaults = {'quantity': quantity}

        if product_type == 'perfume':
            perfume = validated_data['perfume_id']
            decant_size = validated_data['decant_size']

            if perfume.price_per_ml and decant_size:
                price = (Decimal(str(perfume.price_per_ml)) * Decimal(decant_size))
            elif not perfume.price_per_ml:
                 return Response({"detail": f"Price per ml not set for perfume {perfume.name}."}, status=status.HTTP_400_BAD_REQUEST)
            else:
                 return Response({"detail": "Could not determine price for perfume item."}, status=status.HTTP_400_BAD_REQUEST)

            item_defaults.update({
                'perfume': perfume,
                'name': perfume.name,
                'decant_size': decant_size,
                'price_at_addition': price,
                'product_type': 'perfume'
            })
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                perfume=perfume,
                decant_size=decant_size,
                product_type='perfume',
                defaults=item_defaults
            )

        elif product_type == 'box':
            price = validated_data['price']
            box_configuration = validated_data['box_configuration']
            name = validated_data['name']

            box_decant_size = None
            if isinstance(box_configuration, dict) and 'decantSize' in box_configuration:
                box_decant_size = box_configuration.get('decantSize')

            item_defaults.update({
                'name': name,
                'price_at_addition': price,
                'box_configuration': box_configuration,
                'product_type': 'box',
                'decant_size': box_decant_size
            })
            cart_item = CartItem.objects.create(cart=cart, **item_defaults)
            created = True

        else:
            return Response({"detail": "Invalid product_type processing."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not created and product_type == 'perfume':
            cart_item.quantity += quantity
            cart_item.save()

        cart_serializer = CartSerializer(cart, context={'request': request})
        return Response(cart_serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


    @action(detail=False, methods=['delete'], url_path='items/(?P<item_pk>[^/.]+)')
    def remove_item(self, request, item_pk=None):
         cart = self.get_cart(request.user)
         cart_item = get_object_or_404(CartItem, pk=item_pk, cart=cart)
         cart_item.delete()
         return Response(status=status.HTTP_204_NO_CONTENT)


    @action(detail=False, methods=['delete'], url_path='clear')
    def clear_cart(self, request):
        cart = self.get_cart(request.user)
        cart.items.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# --- Box ViewSets ---

class PredefinedBoxViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PredefinedBox.objects.prefetch_related('perfumes').all()
    serializer_class = PredefinedBoxSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['gender']

class SubscriptionViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='tiers', permission_classes=[permissions.AllowAny])
    def list_tiers(self, request):
        tiers = SubscriptionTier.objects.all()
        serializer = SubscriptionTierSerializer(tiers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='status')
    def get_status(self, request):
        try:
            subscription = UserSubscription.objects.get(user=request.user)
            serializer = UserSubscriptionSerializer(subscription)
            return Response(serializer.data)
        except UserSubscription.DoesNotExist:
            return Response({"detail": "No active subscription found."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='subscribe')
    def subscribe(self, request):
        input_serializer = SubscribeSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        tier = input_serializer.validated_data['tier_id']

        subscription, created = UserSubscription.objects.update_or_create(
            user=request.user,
            defaults={'tier': tier, 'is_active': True}
        )


        response_serializer = UserSubscriptionSerializer(subscription)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(response_serializer.data, status=status_code)

    @action(detail=False, methods=['post'], url_path='unsubscribe')
    def unsubscribe(self, request):
        try:
            subscription = UserSubscription.objects.get(user=request.user, is_active=True)
            subscription.is_active = False
            subscription.save()


            serializer = UserSubscriptionSerializer(subscription)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except UserSubscription.DoesNotExist:
            return Response({"detail": "No active subscription found to unsubscribe."}, status=status.HTTP_404_NOT_FOUND)

class OrderViewSet(viewsets.GenericViewSet,
                   mixins.ListModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.CreateModelMixin):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items', 'items__perfume')

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def perform_create(self, serializer):
        user = self.request.user
        shipping_address = serializer.validated_data['shipping_address']

        try:
            cart = Cart.objects.prefetch_related('items', 'items__perfume').get(user=user)
        except Cart.DoesNotExist:
            raise serializers.ValidationError("Cart not found or is empty.")

        cart_items = cart.items.all()
        if not cart_items.exists():
            raise serializers.ValidationError("Cannot create an order from an empty cart.")

        with transaction.atomic():
            total_price = Decimal('0.00')
            for item in cart_items:
                if item.price_at_addition is not None:
                    try:
                        total_price += (Decimal(item.price_at_addition) * Decimal(item.quantity))
                    except (TypeError, InvalidOperation):
                         raise serializers.ValidationError(f"Invalid price or quantity found for cart item {item.id}.")
                else:
                    raise serializers.ValidationError(f"Missing price for cart item {item.id}. Cannot create order.")


            order = Order.objects.create(
                user=user,
                total_price=total_price,
                shipping_address=shipping_address,
                status='pending'
            )

            order_items_to_create = []
            for cart_item in cart_items:
                item_name = "Box Item"
                item_description = "Predefined/Custom Box"
                if cart_item.product_type == 'perfume' and cart_item.perfume:
                    item_name = cart_item.perfume.name
                    item_description = cart_item.perfume.description

                # Fix box configuration to use actual external_ids instead of database IDs
                fixed_box_configuration = cart_item.box_configuration
                if cart_item.product_type == 'box' and cart_item.box_configuration and 'perfumes' in cart_item.box_configuration:
                    fixed_box_configuration = cart_item.box_configuration.copy()
                    fixed_perfumes = []

                    for perfume_data in cart_item.box_configuration['perfumes']:
                        if 'external_id' in perfume_data:
                            # The external_id field actually contains the database ID, we need to get the real external_id
                            try:
                                db_id = perfume_data['external_id']
                                perfume_obj = Perfume.objects.get(id=db_id)
                                # Update the perfume data with the correct external_id
                                fixed_perfume_data = perfume_data.copy()
                                fixed_perfume_data['external_id'] = perfume_obj.external_id
                                fixed_perfumes.append(fixed_perfume_data)
                            except Perfume.DoesNotExist:
                                # If perfume doesn't exist, keep the original data
                                fixed_perfumes.append(perfume_data)
                        else:
                            # Keep perfume data as is if no external_id field
                            fixed_perfumes.append(perfume_data)

                    fixed_box_configuration['perfumes'] = fixed_perfumes

                order_items_to_create.append(
                    OrderItem(
                        order=order,
                        perfume=cart_item.perfume,
                        product_type=cart_item.product_type,
                        quantity=cart_item.quantity,
                        decant_size=cart_item.decant_size,
                        price_at_purchase=cart_item.price_at_addition,
                        box_configuration=fixed_box_configuration,
                        item_name=item_name,
                        item_description=item_description
                    )
                )
            OrderItem.objects.bulk_create(order_items_to_create)

            cart.items.all().delete()


            serializer.instance = order

class PerfumeRatingView(generics.GenericAPIView):
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_perfume(self):
        perfume_id = self.kwargs.get('perfume_id')
        return get_object_or_404(Perfume, pk=perfume_id)

    def get(self, request, *args, **kwargs):
        perfume = self.get_perfume()
        try:
            rating = Rating.objects.get(user=request.user, perfume=perfume)
            serializer = self.get_serializer(rating)
            return Response(serializer.data)
        except Rating.DoesNotExist:
            return Response({"detail": "No rating found for this perfume by the user."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, *args, **kwargs):
        perfume = self.get_perfume()
        try:
            instance = Rating.objects.get(user=request.user, perfume=perfume)
            serializer = self.get_serializer(instance, data=request.data)
        except Rating.DoesNotExist:
            instance = None
            serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        rating_instance, created = Rating.objects.update_or_create(
            user=request.user,
            perfume=perfume,
            defaults={'rating': serializer.validated_data['rating']}
        )


        response_serializer = self.get_serializer(rating_instance)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(response_serializer.data, status=status_code)

class UserRatingsView(generics.ListAPIView):
    """
    View to get all ratings for the authenticated user.
    """
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Rating.objects.filter(user=self.request.user).select_related('perfume', 'perfume__brand')

class FavoriteViewSet(mixins.ListModelMixin,
                      mixins.CreateModelMixin,
                      viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).select_related('perfume', 'perfume__brand')

    def get_serializer_class(self):
        if self.action == 'list':
            return FavoriteListSerializer
        return FavoriteSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


    @action(detail=False, methods=['delete'], url_path='perfume/(?P<perfume_pk>[^/.]+)')
    def remove_by_perfume(self, request, perfume_pk=None):
        user = request.user
        perfume = get_object_or_404(Perfume, pk=perfume_pk)
        favorite = get_object_or_404(Favorite, user=user, perfume=perfume)
        favorite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Coupon ViewSet ---
class CouponViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Coupon.objects.filter(is_active=True)
    serializer_class = CouponSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'code'


    @action(detail=False, methods=['post'], url_path='validate', permission_classes=[permissions.AllowAny])
    def validate_coupon(self, request):
        coupon_code = request.data.get('code')
        cart_total_str = request.data.get('cart_total')

        if not coupon_code:
            return Response({"detail": "Coupon code is required."}, status=status.HTTP_400_BAD_REQUEST)

        coupon_code = coupon_code.upper()

        try:
            coupon = Coupon.objects.get(code=coupon_code, is_active=True)
        except Coupon.DoesNotExist:
            return Response({"detail": "Invalid or expired coupon code."}, status=status.HTTP_404_NOT_FOUND)

        if coupon.expiry_date and coupon.expiry_date < timezone.now():
            coupon.is_active = False
            coupon.save()
            return Response({"detail": "Coupon has expired."}, status=status.HTTP_400_BAD_REQUEST)

        if coupon.max_uses is not None and coupon.uses_count >= coupon.max_uses:
            return Response({"detail": "Coupon has reached its maximum usage limit."}, status=status.HTTP_400_BAD_REQUEST)

        if coupon.min_purchase_amount is not None and cart_total_str is not None:
            try:
                cart_total = Decimal(cart_total_str)
                if cart_total < coupon.min_purchase_amount:
                    return Response(
                        {"detail": f"Minimum purchase of ${coupon.min_purchase_amount} required for this coupon."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except InvalidOperation:
                 return Response({"detail": "Invalid cart_total provided."}, status=status.HTTP_400_BAD_REQUEST)
            except TypeError:
                pass

        serializer = self.get_serializer(coupon)
        return Response(serializer.data, status=status.HTTP_200_OK)

# --- End Coupon ViewSet ---


# --- Recommendation View ---
from rest_framework.pagination import PageNumberPagination
from .serializers import UserPerfumeMatchSerializer # Import the new serializer

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class RecommendationView(generics.ListAPIView):
    serializer_class = UserPerfumeMatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, drf_filters.OrderingFilter]
    filterset_class = UserPerfumeMatchFilter

    def get_queryset(self):
        user = self.request.user
        return UserPerfumeMatch.objects.filter(user=user)\
                                       .select_related('perfume', 'perfume__brand')\
                                       .order_by('-match_percentage')

# --- End Recommendation View ---
