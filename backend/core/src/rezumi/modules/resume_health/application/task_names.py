"""Stable broker-neutral task names shared by API publishers and workers."""

PROCESS_RESUME_TASK = "rezumi.resume_health.process"
DISPATCH_OUTBOX_TASK = "rezumi.resume_health.dispatch_outbox"
RECONCILE_RESUME_TASK = "rezumi.resume_health.reconcile"
CLEANUP_RESUME_TASK = "rezumi.resume_health.cleanup"
