-- ============================================================================
-- Migration scripts from Rapo v0.7.0 to v0.8.0
-- ============================================================================

-- ------------------------------------
-- Scheduler table migration.

-- Lease of the web server instance that runs the scheduler, and the
-- scheduler Stop/Start switch of the UI.
alter table rapo_scheduler add (
  heartbeat   date,
  instance_id varchar2(64 char),
  disabled    varchar2(1) default 'N' not null
);

-- ------------------------------------
-- Scheduler event table.

-- One row per control run request (scheduled, manual, cascade or catch-up)
-- and per scheduled fire missed while no scheduler was running.
create table rapo_scheduler_event (
  event_id       number(*, 0),
  control_id     number(*, 0),
  trigger_type   varchar2(10 char),
  event_type     varchar2(10 char),
  scheduled_time date,
  event_time     date,
  start_time     date,
  updated        date,
  process_id     number(*, 0),
  message        varchar2(4000 char),
  runner         varchar2(255 char),
  constraint rapo_scheduler_event_pk primary key (event_id)
);

create index rapo_scheduler_event_ctl_ix on rapo_scheduler_event (control_id, event_time);
create index rapo_scheduler_event_time_ix on rapo_scheduler_event (event_time);
create index rapo_scheduler_event_prc_ix on rapo_scheduler_event (process_id);
create index rapo_scheduler_event_upd_ix on rapo_scheduler_event (updated);

create sequence rapo_scheduler_event_seq
increment by 1
start with 1
nocache;

create or replace trigger rapo_scheduler_event_id_trg
before insert on rapo_scheduler_event
for each row
begin
  select rapo_scheduler_event_seq.nextval
    into :new.event_id
    from dual;
end;
/
