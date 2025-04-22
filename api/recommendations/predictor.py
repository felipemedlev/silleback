import pandas as pd
import numpy as np
import logging
from decimal import Decimal

# Django imports (assuming this file is within the Django project structure)
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from ..models import Perfume, SurveyResponse, SurveyQuestion, Accord, UserPerfumeMatch

# Setup logger
logger = logging.getLogger(__name__)

User = get_user_model()

# --- Placeholder Database Interaction Functions ---

def _get_ordered_accord_list():
    """
    Fetches the active accord names from SurveyQuestions in a consistent order.
    This defines the columns/dimensions of the dynamic accord matrix.
    """
    # Example implementation (adjust based on actual SurveyQuestion usage)
    try:
        active_accord_questions = SurveyQuestion.objects.filter(
            is_active=True,
            question_type='accord'
        ).select_related('accord').order_by('order') # Order is important!

        if not active_accord_questions.exists():
            logger.warning("No active accord survey questions found. Cannot generate recommendations.")
            return []

        ordered_accords = [q.accord.name.lower() for q in active_accord_questions if q.accord]
        logger.info(f"Fetched {len(ordered_accords)} ordered accord names from SurveyQuestions.")
        return ordered_accords
    except Exception as e:
        logger.error(f"Error fetching ordered accord list: {e}", exc_info=True)
        return []

def _get_user_survey_vector_and_gender(user: AbstractUser, ordered_accords: list):
    """
    Fetches the user's survey response, extracts gender preference,
    and creates the survey vector aligned with the ordered_accords list.
    """
    try:
        survey_response = SurveyResponse.objects.get(user=user)
        response_data = survey_response.response_data or {}

        # Extract gender (case-insensitive)
        user_gender = response_data.get('gender', '').lower()
        if not user_gender:
            logger.warning(f"Gender preference not found in survey response for user {user.pk}.")
            # Decide fallback behavior: maybe default to 'unisex' or raise error?
            # For now, let's return None for gender if not found.
            user_gender = None

        # Create survey vector
        user_survey_vector = np.zeros(len(ordered_accords))
        for i, accord_name in enumerate(ordered_accords):
            # Use .get(accord_name, 0) to handle missing accords in response, default to 0 rating
            rating = response_data.get(accord_name, 0)
            # Validate rating (0-5 scale, -1 for 'I don't know') and map to centered scale (-2.5 to +2.5)
            try:
                rating_float = float(rating)
                if rating_float == -1: # "I don't know" maps to neutral 0
                    user_survey_vector[i] = 0.0
                elif 0 <= rating_float <= 5: # Map 0-5 to -2.5 to +2.5
                    user_survey_vector[i] = rating_float - 2.5
                else:
                    logger.warning(f"Invalid rating '{rating}' (expected 0-5 or -1) for accord '{accord_name}' for user {user.pk}. Using neutral 0.")
                    user_survey_vector[i] = 0.0 # Default invalid ratings to neutral 0
            except (ValueError, TypeError):
                 logger.warning(f"Non-numeric rating '{rating}' for accord '{accord_name}' for user {user.pk}. Using neutral 0.")
                 user_survey_vector[i] = 0.0 # Default non-numeric ratings to neutral 0

        logger.info(f"Generated survey vector for user {user.pk}. Gender: {user_gender}")
        return user_survey_vector, user_gender

    except SurveyResponse.DoesNotExist:
        logger.warning(f"SurveyResponse not found for user {user.pk}. Cannot generate recommendations.")
        return None, None
    except Exception as e:
        logger.error(f"Error fetching user survey vector for user {user.pk}: {e}", exc_info=True)
        return None, None


def _get_perfume_accord_data(ordered_accords: list):
    """
    Fetches perfume data including IDs, gender, popularity, and their accords.
    Creates a DataFrame and a dynamic perfume-accord matrix (binary).
    """
    try:
        # Fetch all perfumes with necessary fields, prefetching accords
        perfumes_qs = Perfume.objects.prefetch_related('accords').values(
            'id',
            'external_id', # Keep external_id if needed for mapping or reference
            'name',
            'gender',
            'popularity',
            'accords__name' # Get the names of related accords
        )

        if not perfumes_qs:
            logger.warning("No perfumes found in the database.")
            return pd.DataFrame(), pd.DataFrame() # Return empty DataFrames

        # Convert queryset to DataFrame - might need optimization for large datasets
        # Using list comprehension for potentially better performance than direct values()
        perfume_data = []
        perfume_accords_map = {} # {perfume_id: set(accord_names)}

        # Process queryset efficiently
        for p in perfumes_qs:
            pid = p['id']
            if pid not in perfume_accords_map:
                 perfume_accords_map[pid] = set()
                 # Store main perfume data only once per perfume
                 perfume_data.append({
                     'perfume_id': pid,
                     'external_id': p['external_id'],
                     'name': p['name'],
                     'gender': str(p['gender']).lower() if p['gender'] else 'unisex', # Handle None gender
                     'popularity': p['popularity'] if p['popularity'] is not None else 0, # Handle None popularity
                 })
            if p['accords__name']:
                perfume_accords_map[pid].add(p['accords__name'].lower())

        perfumes_df = pd.DataFrame(perfume_data)
        if perfumes_df.empty:
             logger.warning("Perfume DataFrame is empty after processing queryset.")
             return pd.DataFrame(), pd.DataFrame()

        perfumes_df.set_index('perfume_id', inplace=True)

        # Create the dynamic perfume-accord matrix (binary: 1 if accord present, 0 otherwise)
        # Initialize with zeros
        accord_matrix_df = pd.DataFrame(0, index=perfumes_df.index, columns=ordered_accords)

        # Populate the matrix
        for perfume_id, accord_set in perfume_accords_map.items():
            if perfume_id in accord_matrix_df.index: # Check if perfume_id exists in index
                for accord_name in accord_set:
                    if accord_name in accord_matrix_df.columns: # Check if accord_name exists as column
                        accord_matrix_df.loc[perfume_id, accord_name] = 1

        logger.info(f"Created perfume DataFrame ({len(perfumes_df)} perfumes) and accord matrix ({accord_matrix_df.shape}).")
        return perfumes_df, accord_matrix_df

    except Exception as e:
        logger.error(f"Error fetching perfume/accord data: {e}", exc_info=True)
        return pd.DataFrame(), pd.DataFrame() # Return empty DataFrames on error


# --- Core Recommendation Logic ---
def generate_recommendations(user: AbstractUser, alpha: float = 0.5):
    """
    Generates perfume recommendations for a given user based on their survey response.

    Args:
        user: The Django User object.
        alpha: Weight factor for popularity boost.

    Returns:
        A list of tuples: [(perfume_id, final_score), ...] sorted by score,
        or None if recommendations cannot be generated.
    """
    logger.info(f"Starting recommendation generation for user {user.pk} (alpha={alpha}).")

    # 1. Get the consistent list of accords
    ordered_accords = _get_ordered_accord_list()
    if not ordered_accords:
        return None # Error logged in helper

    # 2. Get user's survey vector and gender preference
    user_survey_vector, user_gender = _get_user_survey_vector_and_gender(user, ordered_accords)
    if user_survey_vector is None or user_gender is None:
        # Error logged in helper, or user has no survey/gender pref
        # Handle case where gender is missing but vector exists? For now, require both.
        logger.warning(f"Could not retrieve survey vector or gender for user {user.pk}.")
        return None

    # 3. Get perfume data and the dynamic accord matrix
    perfumes_df, accord_matrix_df = _get_perfume_accord_data(ordered_accords)
    if perfumes_df.empty or accord_matrix_df.empty:
        logger.warning("Perfume data or accord matrix is empty. Cannot generate recommendations.")
        return None # Error logged in helper

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
    # Ensure popularity is numeric, handle potential NaNs just in case (though handled in helper)
    candidate_perfumes_df['popularity'] = pd.to_numeric(candidate_perfumes_df['popularity'], errors='coerce').fillna(0)

    # Apply boosting formula (log scale)
    # Use Decimal for alpha to avoid potential float precision issues if needed, though likely fine here
    rating_count_boost = np.log1p(np.maximum(0, candidate_perfumes_df['popularity'].values))
    # Convert Decimal to float before multiplying with numpy array, then convert back for consistency
    alpha_float = float(alpha)
    candidate_perfumes_df['boosted_score'] = candidate_perfumes_df['similarity_score'] + (alpha_float * rating_count_boost)

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