-- ============================================================================
-- Migration scripts from Rapo v0.6.15 to v0.7.0
-- ============================================================================

-- ------------------------------------
-- Control log table migration.

-- Index used by the web API to detect changed control runs for live UI.
create index rapo_log_updated_ix on rapo_log (updated);
