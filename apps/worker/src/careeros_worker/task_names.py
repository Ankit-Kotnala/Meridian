"""Stable Phase 9 worker task names.

Keeping delivery names in the deployable composition root prevents product
modules from depending on Celery while still giving routing and publishing one
allowlist to share.
"""

PROCESS_CAREER_ANALYTICS_REFRESH_TASK = "careeros.worker.career_analytics.process_refresh"
DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK = "careeros.worker.career_analytics.dispatch_outbox"
RECONCILE_CAREER_ANALYTICS_TASK = "careeros.worker.career_analytics.reconcile"
PROCESS_NETWORKING_LOCAL_REMINDERS_TASK = "careeros.worker.networking.process_local_reminders"
RECONCILE_NETWORKING_REMINDERS_TASK = "careeros.worker.networking.reconcile_local_reminders"
