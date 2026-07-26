"""Stable phase-owned worker task names.

Keeping delivery names in the deployable composition root prevents product
modules from depending on Celery while still giving routing and publishing one
allowlist to share.
"""

PROCESS_ORGANIZATION_INVITATIONS_TASK = "careeros.worker.organizations.deliver_invitations"
PROCESS_CAREER_ANALYTICS_REFRESH_TASK = "careeros.worker.career_analytics.process_refresh"
DISPATCH_CAREER_ANALYTICS_OUTBOX_TASK = "careeros.worker.career_analytics.dispatch_outbox"
RECONCILE_CAREER_ANALYTICS_TASK = "careeros.worker.career_analytics.reconcile"
PROCESS_NETWORKING_LOCAL_REMINDERS_TASK = "careeros.worker.networking.process_local_reminders"
RECONCILE_NETWORKING_REMINDERS_TASK = "careeros.worker.networking.reconcile_local_reminders"
PROCESS_RESUME_EXPORT_TASK = "careeros.worker.resume_builder.process_export"
DISPATCH_RESUME_EXPORT_OUTBOX_TASK = "careeros.worker.resume_builder.dispatch_outbox"
RECONCILE_RESUME_EXPORTS_TASK = "careeros.worker.resume_builder.reconcile_exports"
