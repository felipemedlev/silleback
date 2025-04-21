# Decision Log

This file records architectural and implementation decisions using a list format.
2025-04-01 21:48:48 - Log of updates made.

*

## Decision

*

## Rationale

*

## Implementation Details


---

**[2025-04-01 22:36:57] - Phase 1 Decisions**

*   **Decision:** Use `djoser` for authentication.
    *   **Rationale:** Recommended by Architect mode for its comprehensive feature set out-of-the-box, suitable for handling registration, login, logout, user profiles, etc.
    *   **Implementation:** Installed `djoser`, configured in `settings.py` (`INSTALLED_APPS`, `DJOSER` settings), included URLs in `silleconfig/urls.py`.

*   **Decision:** Set `CORS_ALLOWED_ORIGINS` to `['http://localhost:8081', 'http://127.0.0.1:8081']`.
    *   **Rationale:** Explicitly allow requests from the specified frontend development URL provided by the user.
    *   **Implementation:** Added `CORS_ALLOWED_ORIGINS` setting in `settings.py` and included `corsheaders.middleware.CorsMiddleware` in `MIDDLEWARE`.

*   **Decision:** Reset database and API migrations to resolve `InconsistentMigrationHistory`.
    *   **Rationale:** The error occurred because initial migrations for apps like `admin` were applied before the custom `api.User` model migration was created. Resetting provides a clean slate for correct migration application order.
    *   **Implementation:** Deleted `db.sqlite3`, deleted `api/migrations/0001_initial.py`, ran `makemigrations api`, ran `migrate`.


---

**[2025-04-01 23:01:44] - Phase 2 Decisions**

*   **Decision:** Use `models.JSONField` for the `Perfume.notes` field.
    *   **Rationale:** Provides a structured format (`{"top": [], "middle": [], "base": []}`) which is more suitable for future ML integration compared to a simple `TextField`. User confirmed preference.
    *   **Implementation:** Defined `notes = models.JSONField(...)` in the `Perfume` model in `api/models.py`.
*

---

**[2025-04-13 21:29:17] - Survey Admin Panel Integration**

*   **Decision:** Make survey questions endpoint available in Django admin panel
    *   **Rationale:** User requested ability to view and modify survey questions through admin interface for easier management
    *   **Implementation:** Added SurveyQuestionsView to admin.py with appropriate display fields and search capabilities



---

**[2025-04-16 18:58] - Perfume Filter Fix**

*   **Decision:** Corrected the placement of `filterset_class = PerfumeFilter` in `api/views.py`.
    *   **Rationale:** The `filterset_class` was incorrectly assigned to `SurveyQuestionsView` instead of `PerfumeViewSet`, preventing the custom `PerfumeFilter` from being applied to the `/api/perfumes/` endpoint.
    *   **Implementation:** Moved `filterset_class = PerfumeFilter` from `SurveyQuestionsView` definition to `PerfumeViewSet` definition. Debugged using print statements in `api/filters.py` (subsequently removed).



---

**[2025-04-16 19:04] - Perfume Search Fix**

*   **Decision:** Corrected the placement of `search_fields` in `api/views.py`.
    *   **Rationale:** The `search_fields` attribute was incorrectly assigned to `SurveyQuestionsView` instead of `PerfumeViewSet`, preventing the `SearchFilter` from being applied correctly to the `/api/perfumes/` endpoint.
    *   **Implementation:** Moved `search_fields = [...]` from `SurveyQuestionsView` definition to `PerfumeViewSet` definition.

---
[2025-04-21 17:50:30] - **Decision:** Integrate recommendation logic using Celery for background processing.
    - **Rationale:** Calculating scores for all perfumes per user can be time-consuming. Background processing prevents blocking the user request during survey submission.
    - **Implications:** Requires Celery setup (broker like Redis), task definition, and triggering mechanism.

[2025-04-21 17:50:30] - **Decision:** Trigger Celery task using `delay_on_commit` after `SurveyResponse` save.
    - **Rationale:** Ensures the database transaction for saving the survey is complete before the task attempts to read the data, preventing race conditions. Confirmed via Celery documentation.
    - **Implications:** Task is triggered slightly later, but data consistency is prioritized. Task ID is not immediately available to the caller.

[2025-04-21 17:50:30] - **Decision:** Store calculated scores in `UserPerfumeMatch` table.
    - **Rationale:** Provides a dedicated table for storing the output, allowing efficient retrieval via a separate API endpoint. Avoids recalculating scores on every request.
    - **Implications:** Requires efficient bulk update/create logic within the Celery task.

[2025-04-21 17:50:30] - **Decision:** Create a dedicated `GET /api/recommendations/` endpoint.
    - **Rationale:** Provides a clean interface for the frontend to fetch pre-calculated recommendations for the authenticated user.
    - **Implications:** Requires a new view (`RecommendationView`) and serializer (`UserPerfumeMatchSerializer`).
