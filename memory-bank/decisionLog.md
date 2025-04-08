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