import logging
from decimal import Decimal

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction

# Assuming predictor is in a sub-directory 'recommendations' within the 'api' app
from .recommendations.predictor import generate_recommendations
from .models import Perfume, UserPerfumeMatch

User = get_user_model()
logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60) # Add retry logic
def update_user_recommendations(self, user_pk: int):
    """
    Celery task to calculate and update perfume match scores for a user.
    """
    try:
        user = User.objects.get(pk=user_pk)
        logger.info(f"Starting recommendation update task for user {user_pk} ({user.email})")

        # Generate recommendations -> list of (perfume_id, final_score)
        recommendations = generate_recommendations(user)

        if recommendations is None:
            # Error occurred during generation (already logged in predictor)
            logger.error(f"Recommendation generation failed for user {user_pk}. Task will not update matches.")
            # You might want specific retry logic here based on the failure type
            # For now, just log and exit.
            return f"Recommendation generation failed for user {user_pk}"

        if not recommendations:
            logger.info(f"No recommendations generated (e.g., no matching perfumes) for user {user_pk}. Clearing existing matches.")
            # If no recommendations, clear existing ones for this user
            UserPerfumeMatch.objects.filter(user=user).delete()
            return f"No recommendations generated for user {user_pk}. Existing matches cleared."

        # --- Efficiently update UserPerfumeMatch ---
        logger.info(f"Updating {len(recommendations)} UserPerfumeMatch entries for user {user_pk}...")

        # Fetch existing matches for this user to determine create vs update
        existing_matches = UserPerfumeMatch.objects.filter(user=user).values_list('perfume_id', flat=True)
        existing_matches_set = set(existing_matches)

        perfume_scores = {pid: score for pid, score in recommendations} # Dict for quick lookup

        # Prepare lists for bulk operations
        matches_to_create = []
        matches_to_update = []
        perfumes_to_fetch_for_update = [] # IDs of perfumes needing update instances

        # Separate into create and update lists
        for perfume_id, final_score in perfume_scores.items():
            # Ensure score is Decimal
            score_decimal = Decimal(str(final_score))

            if perfume_id in existing_matches_set:
                 perfumes_to_fetch_for_update.append(perfume_id)
            else:
                matches_to_create.append(
                    UserPerfumeMatch(
                        user=user,
                        perfume_id=perfume_id, # Directly use perfume_id
                        match_percentage=score_decimal
                    )
                )

        # Fetch instances needed for bulk_update
        update_instances = UserPerfumeMatch.objects.filter(
            user=user,
            perfume_id__in=perfumes_to_fetch_for_update
        )
        for match_instance in update_instances:
             new_score = perfume_scores.get(match_instance.perfume_id)
             if new_score is not None and match_instance.match_percentage != Decimal(str(new_score)):
                 match_instance.match_percentage = Decimal(str(new_score))
                 matches_to_update.append(match_instance)


        # Perform bulk operations within a transaction
        with transaction.atomic():
            # Bulk Create new matches
            if matches_to_create:
                created_matches = UserPerfumeMatch.objects.bulk_create(matches_to_create, batch_size=500)
                logger.info(f"Bulk created {len(created_matches)} new UserPerfumeMatch entries.")

            # Bulk Update existing matches
            if matches_to_update:
                updated_count = UserPerfumeMatch.objects.bulk_update(matches_to_update, ['match_percentage'], batch_size=500)
                logger.info(f"Bulk updated {updated_count} existing UserPerfumeMatch entries.")

            # Optional: Delete matches for perfumes no longer recommended (if applicable)
            # current_recommended_ids = set(perfume_scores.keys())
            # matches_to_delete = existing_matches_set - current_recommended_ids
            # if matches_to_delete:
            #     deleted_count, _ = UserPerfumeMatch.objects.filter(user=user, perfume_id__in=matches_to_delete).delete()
            #     logger.info(f"Deleted {deleted_count} outdated UserPerfumeMatch entries.")


        logger.info(f"Successfully updated recommendations for user {user_pk}")
        return f"Successfully updated {len(recommendations)} recommendations for user {user_pk}"

    except User.DoesNotExist:
        logger.error(f"User with pk={user_pk} not found for recommendation task.")
        # No retry needed if user doesn't exist
        return f"User {user_pk} not found."
    except Exception as exc:
        logger.error(f"Error in update_user_recommendations task for user {user_pk}: {exc}", exc_info=True)
        # Retry the task using Celery's built-in mechanism
        raise self.retry(exc=exc)