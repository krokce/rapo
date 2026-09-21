-- Rapo v0.8.0 -> v0.8.1
-- Adds the Oracle-side PL-SQL execution engine for REC controls.

insert into rapo_ref_engines values ('PL', 'PL-SQL procedure');
commit;

-- Log lines emitted by the PL-SQL engine while it runs. The control process
-- drains them into the run's own log file, so they are transport only.
create table rapo_engine_log (
  process_id    number(*, 0),
  record_number number(*, 0),
  logged        date,
  log_level     varchar2(10),
  message       clob,
  constraint rapo_engine_log_pk primary key (process_id, record_number)
);

-- The engine itself is schema/rapo_usage_rule.sql. Deploy it after this script:
--   @../../schema/rapo_usage_rule.sql
