import pandas as pd
import numpy as np
import logging
from decimal import Decimal

# Django imports (assuming this file is within the Django project structure)
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from ..models import Perfume, SurveyResponse, SurveyQuestion, Accord, UserPerfumeMatch
from django.core.cache import cache

# Setup logger
logger = logging.getLogger(__name__)

User = get_user_model()

# --- Database Interaction Functions ---

def _get_all_accord_list():
    """
    Fetches ALL distinct accord names associated with any Perfume, in a consistent order (by name).
    This defines the columns/dimensions of the full accord matrix.
    """
    try:
        # Fetch distinct accord names linked to perfumes, ordered by name for consistency
        all_accords = list(Accord.objects.filter(perfumes__isnull=False).distinct().order_by('name').values_list('name', flat=True))
        # Convert to lowercase for consistency
        all_accords_lower = [name.lower() for name in all_accords if name]

        if not all_accords_lower:
            logger.warning("No accords found associated with any perfumes in the database.")
            return []

        logger.info(f"Fetched {len(all_accords_lower)} distinct accord names associated with perfumes.")
        return all_accords_lower
    except Exception as e:
        logger.error(f"Error fetching full accord list: {e}", exc_info=True)
        return []

def _get_user_survey_vector_and_gender(user: AbstractUser, all_accords: list):
    """
    Fetches the user's survey response, extracts gender preference,
    and creates the survey vector aligned with the *all_accords* list.
    Assigns neutral preference (0.0) for non-surveyed accords.
    """
    try:
        survey_response = SurveyResponse.objects.get(user=user)
        response_data = survey_response.response_data or {}

        # Extract gender (case-insensitive)
        user_gender = response_data.get('gender', '').lower()
        if not user_gender:
            logger.warning(f"Gender preference not found in survey response for user {user.pk}.")
            user_gender = None # Or default to 'unisex'? For now, None.

        # Get the set of accords the user actually rated in the survey
        # This assumes survey response keys match accord names (lowercase)
        surveyed_accords_set = {key.lower() for key in response_data.keys() if key.lower() in all_accords}
        logger.info(f"User {user.pk} rated {len(surveyed_accords_set)} accords in their survey.")

        # Create survey vector aligned with all_accords
        user_survey_vector = np.zeros(len(all_accords))
        for i, accord_name in enumerate(all_accords):
            if accord_name in surveyed_accords_set:
                # Accord was surveyed, use the user's rating
                rating = response_data.get(accord_name, 0) # Use .get for safety, though it should be present
                try:
                    rating_float = float(rating)
                    if rating_float == -1: # "I don't know" maps to neutral 0
                        user_survey_vector[i] = 0.0
                    elif 0 <= rating_float <= 5: # Map 0-5 to -2.5 to +2.5
                        user_survey_vector[i] = rating_float - 2.5
                    else:
                        logger.warning(f"Invalid rating '{rating}' for surveyed accord '{accord_name}' for user {user.pk}. Using neutral 0.")
                        user_survey_vector[i] = 0.0
                except (ValueError, TypeError):
                     logger.warning(f"Non-numeric rating '{rating}' for surveyed accord '{accord_name}' for user {user.pk}. Using neutral 0.")
                     user_survey_vector[i] = 0.0
            else:
                # Accord exists in perfumes but was not surveyed by this user
                # Assign neutral preference (0.0 on the centered scale)
                user_survey_vector[i] = 0.0

        logger.info(f"Generated survey vector (size {len(all_accords)}) for user {user.pk}. Gender: {user_gender}")
        return user_survey_vector, user_gender

    except SurveyResponse.DoesNotExist:
        logger.warning(f"SurveyResponse not found for user {user.pk}. Cannot generate recommendations.")
        return None, None
    except Exception as e:
        logger.error(f"Error fetching user survey vector for user {user.pk}: {e}", exc_info=True)
        return None, None



def _get_perfume_accord_data():
    """
    Fetches perfume data including IDs, gender, popularity, and their *ordered* accords.
    Creates a DataFrame and a *weighted* perfume-accord matrix based on accord order/predominance.
    """
    try:
        # Check cache
        cache_key = 'perfume_accord_matrix_data'
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info("Using cached perfume-accord matrix.")
            return cached_data

        # Fetch distinct accord names for columns
        all_accords = _get_all_accord_list()

        # Fetch all perfumes with necessary fields.
        # Prefetch related accords. IMPORTANT: Assumes the default ordering
        # of the related 'accords' reflects their predominance. If an explicit
        # 'order' field exists on the through model (e.g., PerfumeAccord),
        # it should be used in an .order_by() clause on the prefetch.
        perfumes = Perfume.objects.prefetch_related('accords').all()

        if not perfumes:
            logger.warning("No perfumes found in the database.")
            return pd.DataFrame(), pd.DataFrame()

        perfume_data = []
        # Store accords as an ordered list: {perfume_id: [ordered_accord_names]}
        perfume_accords_map = {}

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
            # Retrieve accords in the order provided by the ORM/prefetch
            ordered_perfume_accords = [a.name.lower() for a in p.accords.all() if a.name]
            perfume_accords_map[p.id] = ordered_perfume_accords

        perfumes_df = pd.DataFrame(perfume_data)
        if perfumes_df.empty:
            logger.warning("Perfume DataFrame is empty after processing queryset.")
            return pd.DataFrame(), pd.DataFrame()

        perfumes_df.set_index('perfume_id', inplace=True)

        # Create the full perfume-accord matrix (weighted by order)
        # Initialize with zeros, using all_accords as columns
        accord_matrix_df = pd.DataFrame(0.0, index=perfumes_df.index, columns=all_accords) # Use float for weights

        # Populate the matrix with weights
        for perfume_id, ordered_perfume_accords in perfume_accords_map.items():
            if perfume_id in accord_matrix_df.index:
                for idx, accord_name in enumerate(ordered_perfume_accords):
                    if accord_name in accord_matrix_df.columns:
                        # Apply weighting scheme: 1.0, 0.8, 0.6, 0.4, 0.2, then 0.1 for subsequent
                        # Limit index to avoid negative weights if many accords
                        weight_index = min(idx, 5) # 0, 1, 2, 3, 4 map to 1.0->0.2, 5+ maps to 0.1
                        if weight_index < 5:
                             weight = 1.0 - (0.2 * weight_index)
                        else:
                             weight = 0.1
                        # Assign the calculated weight
                        accord_matrix_df.loc[perfume_id, accord_name] = weight
                    # else: accord exists for perfume but not in the global 'all_accords' list (shouldn't happen with current logic)

        logger.info(f"Created perfume DataFrame ({len(perfumes_df)} perfumes) and weighted accord matrix ({accord_matrix_df.shape}).")

        # Cache the result for 24 hours
        cache.set(cache_key, (perfumes_df, accord_matrix_df), timeout=60*60*24)

        return perfumes_df, accord_matrix_df

    except Exception as e:
        logger.error(f"Error fetching weighted perfume/accord data: {e}", exc_info=True)
        return pd.DataFrame(), pd.DataFrame()


# --- Core Recommendation Logic ---
def generate_recommendations(user: AbstractUser, alpha: float = 0.7):
    """
    Generates perfume recommendations for a given user based on their survey response,
    using a weighted accord matrix reflecting predominance and popularity boosting.

    Args:
        user: The Django User object.
        alpha: Weight factor for popularity boost.

    Returns:
        A list of tuples: [(perfume_id, final_score), ...] sorted by score,
        or None if recommendations cannot be generated.
    """
    logger.info(f"Starting recommendation generation for user {user.pk} (alpha={alpha}).")

    # 1. Get perfume data and the full *weighted* accord matrix (Source of Truth for dimensions)
    perfumes_df, accord_matrix_df = _get_perfume_accord_data()
    if perfumes_df.empty or accord_matrix_df.empty:
        logger.warning("Perfume data or the weighted accord matrix is empty. Cannot generate recommendations.")
        return None

    # 2. Get the full list of all accords FROM the matrix columns to ensure alignment
    all_accords = accord_matrix_df.columns.tolist()

    # 3. Get user's survey vector (aligned with all accords) and gender preference
    user_survey_vector, user_gender = _get_user_survey_vector_and_gender(user, all_accords)
    if user_survey_vector is None or user_gender is None:
        # Error logged in helper, or user has no survey/gender pref
        logger.warning(f"Could not retrieve survey vector or gender for user {user.pk}.")
        return None

    # 4. Filter Perfumes by Gender
    logger.info(f"Filtering perfumes by user gender preference: '{user_gender}'")
    if user_gender == 'male':
        # Include 'male' and 'unisex'
        candidate_perfumes_df = perfumes_df[perfumes_df['gender'].isin(['male', 'unisex'])].copy()
    elif user_gender == 'female':
        # Include 'female' and 'unisex'
        candidate_perfumes_df = perfumes_df[perfumes_df['gender'].isin(['female', 'unisex'])].copy()
    elif user_gender == 'unisex':
        # Include ONLY 'unisex'
        candidate_perfumes_df = perfumes_df[perfumes_df['gender'] == 'unisex'].copy()
    else:
        logger.warning(f"Unknown gender preference '{user_gender}' for user {user.pk}. Filtering skipped, using all perfumes.")
        candidate_perfumes_df = perfumes_df.copy() # Or maybe return None?

    # Ensure candidate perfumes exist in the accord matrix
    candidate_perfumes_df = candidate_perfumes_df[candidate_perfumes_df.index.isin(accord_matrix_df.index)]

    if candidate_perfumes_df.empty:
        logger.warning(f"No candidate perfumes found matching gender '{user_gender}' for user {user.pk}.")
        return [] # Return empty list if no perfumes match criteria

    logger.info(f"Found {len(candidate_perfumes_df)} candidate perfumes after gender filtering.")

    # Get the accord vectors for only the candidate perfumes
    candidate_accord_vectors = accord_matrix_df.loc[candidate_perfumes_df.index]

    # 5. Calculate Similarity Scores (Dot product)
    logger.info("Calculating similarity scores...")
    # Ensure user_survey_vector is a column vector for dot product if needed, or handle shapes appropriately
    # Assuming candidate_accord_vectors is (n_perfumes, n_accords) and user_survey_vector is (n_accords,)
    # Result should be (n_perfumes,)
    try:
        # Use .values to ensure numpy array operation
        similarity_scores = candidate_accord_vectors.values.dot(user_survey_vector)
        candidate_perfumes_df['similarity_score'] = similarity_scores
    except ValueError as e:
         logger.error(f"Shape mismatch during similarity calculation: {e}", exc_info=True)
         logger.error(f"Accord Matrix shape: {candidate_accord_vectors.shape}, User Vector shape: {user_survey_vector.shape}")
         return None


    # 6. Apply Popularity Boosting
    logger.info("Applying popularity boosting...")
    # Popularity is already in candidate_perfumes_df from _get_perfume_accord_data
    candidate_perfumes_df['rating_count'] = pd.to_numeric(candidate_perfumes_df['rating_count'], errors='coerce').fillna(0)
    candidate_perfumes_df['recent_magnitude'] = pd.to_numeric(candidate_perfumes_df['recent_magnitude'], errors='coerce').fillna(0)
    candidate_perfumes_df['overall_rating'] = pd.to_numeric(candidate_perfumes_df['overall_rating'], errors='coerce').fillna(0)
    rating_count_boost = np.log1p(np.maximum(0, candidate_perfumes_df['rating_count'].values))
    recent_magnitude_boost = np.log1p(np.maximum(0, candidate_perfumes_df['recent_magnitude'].values))
    overall_rating_boost = np.log1p(np.maximum(0, candidate_perfumes_df['overall_rating'].values))
    perfumes_boost = rating_count_boost + recent_magnitude_boost + overall_rating_boost
    # Convert Decimal to float before multiplying with numpy array, then convert back for consistency
    alpha_float = float(alpha)
    candidate_perfumes_df['boosted_score'] = candidate_perfumes_df['similarity_score'] + (alpha_float * perfumes_boost)

    # 7. Normalize Boosted Score to 0-1 range
    logger.info("Normalizing scores...")
    min_score = candidate_perfumes_df['boosted_score'].min()
    max_score = candidate_perfumes_df['boosted_score'].max()

    if max_score > min_score:
        # Apply Min-Max scaling
        candidate_perfumes_df['final_score'] = (candidate_perfumes_df['boosted_score'] - min_score) / (max_score - min_score)
    elif max_score == min_score and max_score is not None:
         # Handle case where all scores are the same (avoid division by zero)
         # Assign 1.0 if the single score is positive, 0.5 if zero, 0.0 if negative? Or just 0.5?
         candidate_perfumes_df['final_score'] = 0.5 # Assign neutral 0.5 if all scores are identical
    else: # Handle case where scores might be NaN or calculation failed
        logger.warning("Could not normalize scores (min=max or NaN). Assigning 0.")
        candidate_perfumes_df['final_score'] = 0.0

    # Ensure final_score is Decimal for database
    candidate_perfumes_df['final_score'] = candidate_perfumes_df['final_score'].apply(lambda x: Decimal(str(x)))


    # 8. Prepare and Return Results
    # Sort by final_score (descending)
    results_df = candidate_perfumes_df.sort_values(by='final_score', ascending=False)

    # Create list of tuples (perfume_id, final_score)
    recommendations = list(zip(results_df.index, results_df['final_score']))

    logger.info(f"Successfully generated {len(recommendations)} recommendations for user {user.pk}.")

    # Optional: Log top 5 for debugging
    # logger.debug("Top 5 recommendations:")
    # top_5 = pd.merge(results_df.head(5), perfumes_df[['name']], left_index=True, right_index=True)
    # logger.debug(top_5[['name', 'final_score']].to_string())

    return recommendations

# Example Usage (for testing within Django shell, not part of the final task)
# if __name__ == '__main__':
#     # This block would only run if the script is executed directly,
#     # which won't happen in the Celery task context.
#     # You'd typically test this by calling generate_recommendations from the Django shell
#     # after setting up a user and their survey response.
#     try:
#         test_user = User.objects.get(pk=1) # Replace with a valid user ID
#         recs = generate_recommendations(test_user)
#         if recs:
#             print(f"Generated {len(recs)} recommendations.")
#             # print(recs[:10]) # Print top 10
#         else:
#             print("Failed to generate recommendations.")
#     except User.DoesNotExist:
#         print("Test user not found.")
#     except Exception as e:
#         print(f"An error occurred during testing: {e}")