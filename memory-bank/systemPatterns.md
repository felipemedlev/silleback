# System Patterns *Optional*

This file documents recurring patterns and standards used in the project.
It is optional, but recommended to be updated as the project evolves.
2025-04-01 21:48:54 - Log of updates made.

*

## Coding Patterns

*

## Architectural Patterns

*

## Testing Patterns

*
---
[2025-04-21 17:51:30] - **Pattern:** Asynchronous Task Processing via Celery.
    - **Context:** Used for potentially long-running operations like calculating user recommendations after survey submission.
    - **Implementation:** Defined Celery app instance, created shared tasks (`@shared_task`), configured broker (Redis).
    - **Rationale:** Improves user experience by offloading heavy computation from the request-response cycle.

[2025-04-21 17:51:30] - **Pattern:** Post-Transaction Task Triggering.
    - **Context:** Used when Celery tasks depend on database state modified within the same request (e.g., reading a newly saved `SurveyResponse`).
    - **Implementation:** Utilized `task.delay_on_commit(pk)` to trigger the Celery task.
    - **Rationale:** Prevents race conditions by ensuring the database transaction is committed before the task executes.