from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model
from .models import Perfume, Brand, Occasion, UserPerfumeMatch
from decimal import Decimal

User = get_user_model()

class RecommendationViewFilteringTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a user
        cls.user = User.objects.create_user(username='testuser', password='password123')

        # Create Brands
        cls.brand1 = Brand.objects.create(name='Brand A')
        cls.brand2 = Brand.objects.create(name='Brand B')

        # Create Occasions
        cls.occasion_day = Occasion.objects.create(name='Daytime')
        cls.occasion_night = Occasion.objects.create(name='Night Out')
        cls.occasion_office = Occasion.objects.create(name='Office')

        # Create Perfumes
        cls.perfume1 = Perfume.objects.create(
            name='Perfume Low Price Day',
            brand=cls.brand1,
            price_per_ml=Decimal('10.00'), # Correct field name
            external_id='p1'
        )
        cls.perfume1.occasions.add(cls.occasion_day)

        cls.perfume2 = Perfume.objects.create(
            name='Perfume Mid Price Day Night',
            brand=cls.brand1,
            price_per_ml=Decimal('50.00'), # Correct field name
            external_id='p2'
        )
        cls.perfume2.occasions.add(cls.occasion_day, cls.occasion_night)

        cls.perfume3 = Perfume.objects.create(
            name='Perfume High Price Office',
            brand=cls.brand2,
            price_per_ml=Decimal('100.00'), # Correct field name
            external_id='p3'
        )
        cls.perfume3.occasions.add(cls.occasion_office)

        cls.perfume4 = Perfume.objects.create(
            name='Perfume Mid Price Office Day',
            brand=cls.brand2,
            price_per_ml=Decimal('60.00'), # Correct field name
            external_id='p4'
        )
        cls.perfume4.occasions.add(cls.occasion_office, cls.occasion_day)

        # Create Recommendations (Matches) - Higher score = better match
        UserPerfumeMatch.objects.create(user=cls.user, perfume=cls.perfume1, match_percentage=Decimal('0.9')) # Correct field name
        UserPerfumeMatch.objects.create(user=cls.user, perfume=cls.perfume2, match_percentage=Decimal('0.8')) # Correct field name
        UserPerfumeMatch.objects.create(user=cls.user, perfume=cls.perfume3, match_percentage=Decimal('0.7')) # Correct field name
        UserPerfumeMatch.objects.create(user=cls.user, perfume=cls.perfume4, match_percentage=Decimal('0.85'))# Correct field name

    def setUp(self):
        # Authenticate the client for each test
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('user-recommendations') # Correct URL name from urls.py

    def test_no_filters(self):
        """Test retrieving recommendations without any filters."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', []) # Handle pagination
        self.assertEqual(len(results), 4)
        # Check default ordering by score descending
        self.assertEqual(results[0]['perfume']['external_id'], 'p1') # score 0.9
        self.assertEqual(results[1]['perfume']['external_id'], 'p4') # score 0.85
        self.assertEqual(results[2]['perfume']['external_id'], 'p2') # score 0.8
        self.assertEqual(results[3]['perfume']['external_id'], 'p3') # score 0.7

    def test_filter_by_price_min(self):
        """Test filtering recommendations by minimum price."""
        response = self.client.get(self.url, {'price_min': 55})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        self.assertEqual(len(results), 2)
        perfume_ids = {p['perfume']['external_id'] for p in results}
        self.assertEqual(perfume_ids, {'p4', 'p3'}) # p4 (60), p3 (100)
        # Check ordering is still by score
        self.assertEqual(results[0]['perfume']['external_id'], 'p4') # score 0.85
        self.assertEqual(results[1]['perfume']['external_id'], 'p3') # score 0.7

    def test_filter_by_price_max(self):
        """Test filtering recommendations by maximum price."""
        response = self.client.get(self.url, {'price_max': 55})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        self.assertEqual(len(results), 2)
        perfume_ids = {p['perfume']['external_id'] for p in results}
        self.assertEqual(perfume_ids, {'p1', 'p2'}) # p1 (10), p2 (50)
        # Check ordering is still by score
        self.assertEqual(results[0]['perfume']['external_id'], 'p1') # score 0.9
        self.assertEqual(results[1]['perfume']['external_id'], 'p2') # score 0.8

    def test_filter_by_price_range(self):
        """Test filtering recommendations by a price range."""
        response = self.client.get(self.url, {'price_min': 40, 'price_max': 70})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        self.assertEqual(len(results), 2)
        perfume_ids = {p['perfume']['external_id'] for p in results}
        self.assertEqual(perfume_ids, {'p2', 'p4'}) # p2 (50), p4 (60)
        # Check ordering is still by score
        self.assertEqual(results[0]['perfume']['external_id'], 'p4') # score 0.85
        self.assertEqual(results[1]['perfume']['external_id'], 'p2') # score 0.8

    def test_filter_by_single_occasion(self):
        """Test filtering recommendations by a single occasion ID."""
        response = self.client.get(self.url, {'occasions': self.occasion_office.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        self.assertEqual(len(results), 2)
        perfume_ids = {p['perfume']['external_id'] for p in results}
        self.assertEqual(perfume_ids, {'p3', 'p4'}) # p3 (office), p4 (office, day)
        # Check ordering is still by score
        self.assertEqual(results[0]['perfume']['external_id'], 'p4') # score 0.85
        self.assertEqual(results[1]['perfume']['external_id'], 'p3') # score 0.7

    def test_filter_by_multiple_occasions(self):
        """Test filtering recommendations by multiple occasion IDs (OR logic)."""
        occasion_ids = f"{self.occasion_night.id},{self.occasion_office.id}"
        response = self.client.get(self.url, {'occasions': occasion_ids})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        self.assertEqual(len(results), 3)
        perfume_ids = {p['perfume']['external_id'] for p in results}
        # p2 (day, night), p3 (office), p4 (office, day)
        self.assertEqual(perfume_ids, {'p2', 'p3', 'p4'})
        # Check ordering is still by score
        self.assertEqual(results[0]['perfume']['external_id'], 'p4') # score 0.85
        self.assertEqual(results[1]['perfume']['external_id'], 'p2') # score 0.8
        self.assertEqual(results[2]['perfume']['external_id'], 'p3') # score 0.7

    def test_filter_by_price_and_occasion(self):
        """Test filtering recommendations by both price range and occasions."""
        occasion_ids = f"{self.occasion_day.id},{self.occasion_office.id}"
        response = self.client.get(self.url, {
            'price_min': 55, # p3 (100), p4 (60)
            'price_max': 110,
            'occasions': occasion_ids # p1(day), p2(day,night), p3(office), p4(office,day)
        })
        # Expected intersection: p3 (100, office), p4 (60, office/day)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        self.assertEqual(len(results), 2)
        perfume_ids = {p['perfume']['external_id'] for p in results}
        self.assertEqual(perfume_ids, {'p3', 'p4'})
        # Check ordering is still by score
        self.assertEqual(results[0]['perfume']['external_id'], 'p4') # score 0.85
        self.assertEqual(results[1]['perfume']['external_id'], 'p3') # score 0.7

    def test_filter_by_price_and_occasion_no_match(self):
        """Test filtering where price and occasion filters result in no matches."""
        response = self.client.get(self.url, {
            'price_max': 20, # Only p1 (10)
            'occasions': self.occasion_office.id # p3, p4
        })
        # Expected intersection: None
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        self.assertEqual(len(results), 0)
