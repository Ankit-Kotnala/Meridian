"""Stable Phase 9 worker task names.

Keeping delivery names in the deployable composition root prevents product
modules from depending on Celery while still giving routing and publishing one
allowlist to share.
"""

PROCESS_CAREER_ANALYTICS_REFRESH_TASK = "rezumi.worker.career_analytics.process_refresh"
DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK = "rezumi.worker.career_analytics.dispatch_outbox"
RECONCILE_CAREER_ANALYTICS_TASK = "rezumi.worker.career_analytics.reconcile"
PROCESS_NETWORKING_LOCAL_REMINDERS_TASK = "rezumi.worker.networking.process_local_reminders"
RECONCILE_NETWORKING_REMINDERS_TASK = "rezumi.worker.networking.reconcile_local_reminders"
PROCESS_RESUME_EXPORT_TASK = "rezumi.worker.resume_builder.process_export"
DISPATCH_RESUME_EXPORT_OUTBOX_TASK = "rezumi.worker.resume_builder.dispatch_outbox"
RECONCILE_RESUME_EXPORTS_TASK = "rezumi.worker.resume_builder.reconcile_exports"
SYNC_JOB_CATALOG_TASK = "rezumi.worker.job_match.sync_job_catalog"
