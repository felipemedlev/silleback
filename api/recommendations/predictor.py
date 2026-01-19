import pandas as pd
import numpy as np
import logging
from decimal import Decimal
import pickle
import zlib
from functools import lru_cache

# Django imports
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from ..models import Perfume, SurveyResponse, SurveyQuestion, Accord, UserPerfumeMatch
from django.core.cache import cache
from django.db.models import Prefetch

# Setup logger
logger = logging.getLogger(__name__)

User = get_user_model()

# --- In-Memory Cache Layer (reduces Redis calls) ---
# Use LRU cache for frequently accessed data within same process/request
@lru_cache(maxsize=128)
def _get_cached_accord_list():
    """Memory-cached accord list to avoid repeated Redis/DB calls."""
    cache_key = 'accord_list_v1'
    cached = cache.get(cache_key)

    if cached:
        return cached

    # Fetch from DB
    all_accords = list(
        Accord.objects.filter(perfumes__isnull=False)
        .distinct()
        .order_by('name')
        .values_list('name', flat=True)
    )
    all_accords_lower = [name.lower() for name in all_accords if name]

    if all_accords_lower:
        # Cache for 7 days (accords rarely change)
        cache.set(cache_key, all_accords_lower, timeout=60*60*24*7)
        logger.info(f"Cached {len(all_accords_lower)} accords")

    return all_accords_lower

def _get_all_accord_list():
    """
    Fetches ALL distinct accord names with aggressive caching.
    """
    try:
        all_accords = _get_cached_accord_list()

        if not all_accords:
            logger.warning("No accords found associated with any perfumes in the database.")
            return []

        logger.info(f"Fetched {len(all_accords)} distinct accord names.")
        return all_accords
    except Exception as e:
        logger.error(f"Error fetching full accord list: {e}", exc_info=True)
        return []

def _compress_data(data):
    """Compress data for Redis storage."""
    return zlib.compress(pickle.dumps(data), level=6)

def _decompress_data(compressed):
    """Decompress data from Redis."""
    return pickle.loads(zlib.decompress(compressed))

def _get_user_survey_vector_and_gender(user: AbstractUser, all_accords: list):
    """
    Fetches user survey with caching to reduce DB hits.
    """
    # Cache user survey data (relatively static)
    cache_key = f'user_survey_{user.pk}_v1'
    cached = cache.get(cache_key)

    if cached:
        try:
            return _decompress_data(cached)
        except Exception as e:
            logger.warning(f"Cache decompression failed for user {user.pk}: {e}")

    try:
        survey_response = SurveyResponse.objects.get(user=user)
        response_data = survey_response.response_data or {}

        user_gender = response_data.get('gender', '').lower()
        if not user_gender:
            logger.warning(f"Gender preference not found for user {user.pk}.")
            user_gender = None

        surveyed_accords_set = {key.lower() for key in response_data.keys() if key.lower() in all_accords}
        logger.info(f"User {user.pk} rated {len(surveyed_accords_set)} accords.")

        user_survey_vector = np.zeros(len(all_accords), dtype=np.float32)  # Use float32 to reduce size
        for i, accord_name in enumerate(all_accords):
            if accord_name in surveyed_accords_set:
                rating = response_data.get(accord_name, 0)
                try:
                    rating_float = float(rating)
                    if rating_float == -1:
                        user_survey_vector[i] = 0.0
                    elif 0 <= rating_float <= 5:
                        user_survey_vector[i] = rating_float - 2.5
                    else:
                        logger.warning(f"Invalid rating '{rating}' for accord '{accord_name}' for user {user.pk}.")
                        user_survey_vector[i] = 0.0
                except (ValueError, TypeError):
                     logger.warning(f"Non-numeric rating '{rating}' for accord '{accord_name}' for user {user.pk}.")
                     user_survey_vector[i] = 0.0
            else:
                user_survey_vector[i] = 0.0

        result = (user_survey_vector, user_gender)

        # Cache compressed survey data for 30 days (surveys rarely change)
        try:
            cache.set(cache_key, _compress_data(result), timeout=60*60*24*30)
        except Exception as e:
            logger.warning(f"Failed to cache user survey: {e}")

        logger.info(f"Generated survey vector for user {user.pk}. Gender: {user_gender}")
        return result

    except SurveyResponse.DoesNotExist:
        logger.warning(f"SurveyResponse not found for user {user.pk}.")
        return None, None
    except Exception as e:
        logger.error(f"Error fetching user survey vector for user {user.pk}: {e}", exc_info=True)
        return None, None


def _get_perfume_accord_data():
    """
    Optimized perfume data fetching with compressed caching.
    """
    try:
        cache_key = 'perfume_accord_matrix_v2'
        cached = cache.get(cache_key)

        if cached:
            try:
                logger.info("Using cached perfume-accord matrix (compressed).")
                return _decompress_data(cached)
            except Exception as e:
                logger.warning(f"Cache decompression failed: {e}")

        all_accords = _get_all_accord_list()

        # Optimized query: select only needed fields
        perfumes = Perfume.objects.prefetch_related(
            Prefetch('accords', queryset=Accord.objects.only('name'))
        ).only(
            'id', 'external_id', 'name', 'gender',
            'popularity', 'rating_count', 'overall_rating'
        )

        if not perfumes.exists():
            logger.warning("No perfumes found in the database.")
            return pd.DataFrame(), pd.DataFrame()

        perfume_data = []
        perfume_accords_map = {}

        # Not using iterator() to ensure prefetch_related works efficiently.
        # Loading all into memory is acceptable as we build a DataFrame anyway.
        perfume_count = 0

        for p in perfumes:
            perfume_data.append({
                'perfume_id': p.id,
                'external_id': p.external_id,
                'name': p.name,
                'gender': str(p.gender).lower() if p.gender else 'unisex',
                'recent_magnitude': p.popularity if p.popularity is not None else 0,
                'rating_count': p.rating_count if p.rating_count is not None else 0,
                'overall_rating': p.overall_rating if p.overall_rating is not None else 0,
            })
            ordered_perfume_accords = [a.name.lower() for a in p.accords.all() if a.name]
            perfume_accords_map[p.id] = ordered_perfume_accords
            perfume_count += 1

        logger.info(f"Processed {perfume_count} perfumes")

        perfumes_df = pd.DataFrame(perfume_data)
        if perfumes_df.empty:
            logger.warning("Perfume DataFrame is empty after processing.")
            return pd.DataFrame(), pd.DataFrame()

        perfumes_df.set_index('perfume_id', inplace=True)

        # Create sparse-friendly matrix (use float32 to reduce size)
        accord_matrix_df = pd.DataFrame(
            0.0,
            index=perfumes_df.index,
            columns=all_accords,
            dtype=np.float32  # Half the size of float64
        )

        # Populate matrix with weights
        for perfume_id, ordered_perfume_accords in perfume_accords_map.items():
            if perfume_id in accord_matrix_df.index:
                for idx, accord_name in enumerate(ordered_perfume_accords):
                    if accord_name in accord_matrix_df.columns:
                        weight_index = min(idx, 5)
                        weight = 1.0 - (0.2 * weight_index) if weight_index < 5 else 0.1
                        accord_matrix_df.loc[perfume_id, accord_name] = weight

        logger.info(f"Created perfume DataFrame ({len(perfumes_df)}) and accord matrix ({accord_matrix_df.shape}).")

        result = (perfumes_df, accord_matrix_df)

        # Cache compressed data for 6 hours (balance between freshness and cache hits)
        try:
            compressed = _compress_data(result)
            cache.set(cache_key, compressed, timeout=60*60*6)
            logger.info(f"Cached perfume data (compressed size: {len(compressed)} bytes)")
        except Exception as e:
            logger.warning(f"Failed to cache perfume data: {e}")

        return result

    except Exception as e:
        logger.error(f"Error fetching weighted perfume/accord data: {e}", exc_info=True)
        return pd.DataFrame(), pd.DataFrame()


def generate_recommendations(user: AbstractUser, alpha: float = 0.7):
    """
    Generates perfume recommendations with optimized caching for Upstash.
    """
    logger.info(f"Starting recommendation generation for user {user.pk} (alpha={alpha}).")

    # Check if we have cached recommendations (optional - for frequently requesting users)
    rec_cache_key = f'recommendations_{user.pk}_a{int(alpha*100)}_v1'
    cached_recs = cache.get(rec_cache_key)
    if cached_recs:
        try:
            logger.info(f"Returning cached recommendations for user {user.pk}")
            return _decompress_data(cached_recs)
        except Exception as e:
            logger.warning(f"Cache decompression failed for recommendations: {e}")

    perfumes_df, accord_matrix_df = _get_perfume_accord_data()
    if perfumes_df.empty or accord_matrix_df.empty:
        logger.warning("Perfume data or accord matrix is empty.")
        return None

    all_accords = accord_matrix_df.columns.tolist()

    user_survey_vector, user_gender = _get_user_survey_vector_and_gender(user, all_accords)
    if user_survey_vector is None or user_gender is None:
        logger.warning(f"Could not retrieve survey vector or gender for user {user.pk}.")
        return None

    logger.info(f"Filtering perfumes by gender: '{user_gender}'")
    if user_gender == 'male':
        candidate_perfumes_df = perfumes_df[perfumes_df['gender'].isin(['male', 'unisex'])].copy()
    elif user_gender == 'female':
        candidate_perfumes_df = perfumes_df[perfumes_df['gender'].isin(['female', 'unisex'])].copy()
    elif user_gender == 'unisex':
        candidate_perfumes_df = perfumes_df[perfumes_df['gender'] == 'unisex'].copy()
    else:
        logger.warning(f"Unknown gender '{user_gender}' for user {user.pk}.")
        candidate_perfumes_df = perfumes_df.copy()

    candidate_perfumes_df = candidate_perfumes_df[candidate_perfumes_df.index.isin(accord_matrix_df.index)]

    if candidate_perfumes_df.empty:
        logger.warning(f"No candidate perfumes for gender '{user_gender}'.")
        return []

    logger.info(f"Found {len(candidate_perfumes_df)} candidate perfumes.")

    candidate_accord_vectors = accord_matrix_df.loc[candidate_perfumes_df.index]

    logger.info("Calculating similarity scores...")
    try:
        similarity_scores = candidate_accord_vectors.values.dot(user_survey_vector)
        candidate_perfumes_df['similarity_score'] = similarity_scores
    except ValueError as e:
         logger.error(f"Shape mismatch during similarity calculation: {e}", exc_info=True)
         return None

    logger.info("Applying popularity boosting...")
    candidate_perfumes_df['rating_count'] = pd.to_numeric(candidate_perfumes_df['rating_count'], errors='coerce').fillna(0)
    candidate_perfumes_df['recent_magnitude'] = pd.to_numeric(candidate_perfumes_df['recent_magnitude'], errors='coerce').fillna(0)
    candidate_perfumes_df['overall_rating'] = pd.to_numeric(candidate_perfumes_df['overall_rating'], errors='coerce').fillna(0)

    rating_count_boost = np.log1p(np.maximum(0, candidate_perfumes_df['rating_count'].values))
    recent_magnitude_boost = np.log1p(np.maximum(0, candidate_perfumes_df['recent_magnitude'].values))
    overall_rating_boost = np.log1p(np.maximum(0, candidate_perfumes_df['overall_rating'].values))
    perfumes_boost = rating_count_boost + recent_magnitude_boost + overall_rating_boost

    alpha_float = float(alpha)
    candidate_perfumes_df['boosted_score'] = candidate_perfumes_df['similarity_score'] + (alpha_float * perfumes_boost)

    logger.info("Normalizing scores...")
    min_score = candidate_perfumes_df['boosted_score'].min()
    max_score = candidate_perfumes_df['boosted_score'].max()

    if max_score > min_score:
        candidate_perfumes_df['final_score'] = (candidate_perfumes_df['boosted_score'] - min_score) / (max_score - min_score)
    elif max_score == min_score and max_score is not None:
         candidate_perfumes_df['final_score'] = 0.5
    else:
        logger.warning("Could not normalize scores. Assigning 0.")
        candidate_perfumes_df['final_score'] = 0.0

    candidate_perfumes_df['final_score'] = candidate_perfumes_df['final_score'].apply(lambda x: Decimal(str(x)))

    results_df = candidate_perfumes_df.sort_values(by='final_score', ascending=False)
    recommendations = list(zip(results_df.index, results_df['final_score']))

    logger.info(f"Generated {len(recommendations)} recommendations for user {user.pk}.")

    # Cache recommendations for 1 hour (balance between freshness and performance)
    try:
        cache.set(rec_cache_key, _compress_data(recommendations), timeout=60*60)
    except Exception as e:
        logger.warning(f"Failed to cache recommendations: {e}")

    return recommendations