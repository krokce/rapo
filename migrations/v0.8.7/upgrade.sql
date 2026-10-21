-- Rapo v0.8.6 -> v0.8.7
-- Adds the API tokens (rapo_api_token), who asked for a manual run
-- (rapo_scheduler_event.requested_by) and makes the rapo_config triggers record
-- the token's user (client_identifier) instead of the server's OS user.
-- Re-runnable.

declare
  v_count number;
begin
  select count(*) into v_count from user_sequences
   where sequence_name = 'RAPO_API_TOKEN_SEQ';
  if v_count = 0 then
    execute immediate 'create sequence rapo_api_token_seq increment by 1 start with 1 nocache';
  end if;
  select count(*) into v_count from user_tables
   where table_name = 'RAPO_API_TOKEN';
  if v_count = 0 then
    execute immediate q'[
      create table rapo_api_token (
        token_id       number default rapo_api_token_seq.nextval not null,
        token_hash     varchar2(64 char) not null,
        token_prefix   varchar2(16 char) not null,
        user_name      varchar2(128 char) not null,
        user_email     varchar2(256 char) not null,
        label          varchar2(128 char),
        scopes         varchar2(4000 char) not null,
        free_sql       varchar2(1 char) default 'N' not null,
        control_filter varchar2(4000 char),
        expires_at     date,
        revoked_at     date,
        last_used_at   date,
        last_used_ip   varchar2(64 char),
        created_date   date default sysdate not null,
        updated_date   date default sysdate not null,
        constraint rapo_api_token_pk primary key (token_id),
        constraint rapo_api_token_hash_uk unique (token_hash)
      )]';
  end if;
end;
/

declare
  v_count number;
begin
  select count(*) into v_count from user_tab_columns
   where table_name = 'RAPO_SCHEDULER_EVENT' and column_name = 'REQUESTED_BY';
  if v_count = 0 then
    execute immediate 'alter table rapo_scheduler_event add requested_by varchar2(256 char)';
  end if;
end;
/

create or replace trigger rapo_config_ins_trg
before insert on rapo_config
for each row
begin
  select coalesce(sys_context('userenv', 'client_identifier'),
                  sys_context('userenv', 'os_user')) as created_by,
         sysdate as created_date
    into :new.created_by,
         :new.created_date
    from dual;
end;
/

create or replace trigger rapo_config_upd_trg
before update on rapo_config
for each row
begin
  select coalesce(sys_context('userenv', 'client_identifier'),
                  sys_context('userenv', 'os_user')) as updated_by,
         sysdate as updated_date
    into :new.updated_by,
         :new.updated_date
    from dual;
end;
/

create or replace trigger rapo_config_audit
after insert or update or delete on rapo_config
for each row
declare
  v_audit_action rapo_config_bak.audit_action%type;
  v_audit_user   rapo_config_bak.audit_user%type  :=
    coalesce(sys_context('userenv', 'client_identifier'), sys_context('userenv', 'os_user'));
  v_audit_date   rapo_config_bak.audit_date%type  := sysdate;
begin
  if inserting then
    v_audit_action := 'INSERT';
    insert into rapo_config_bak values (
      :new.control_id,
      :new.control_name,
      :new.control_description,
      :new.control_alias,
      :new.control_group,
      :new.control_type,
      :new.control_engine,
      :new.source_name,
      :new.source_date_field,
      :new.source_filter,
      :new.output_table,
      :new.source_name_a,
      :new.source_date_field_a,
      :new.source_key_field_a,
      :new.source_filter_a,
      :new.source_type_a,
      :new.output_table_a,
      :new.source_name_b,
      :new.source_date_field_b,
      :new.source_key_field_b,
      :new.source_filter_b,
      :new.source_type_b,
      :new.output_table_b,
      :new.rule_config,
      :new.case_config,
      :new.case_definition,
      :new.error_definition,
      :new.need_a,
      :new.need_b,
      :new.schedule_config,
      :new.period_back,
      :new.period_number,
      :new.period_type,
      :new.iteration_config,
      :new.timeout,
      :new.instance_limit,
      :new.output_limit,
      :new.days_retention,
      :new.with_deletion,
      :new.with_drop,
      :new.parallelism,
      :new.need_hook,
      :new.need_prerun_hook,
      :new.need_postrun_hook,
      :new.preparation_sql,
      :new.prerequisite_sql,
      :new.completion_sql,
      :new.status,
      :new.updated_by,
      :new.updated_date,
      :new.created_by,
      :new.created_date,
      v_audit_action,
      v_audit_user,
      v_audit_date
    );
  else
    if updating then
      v_audit_action := 'UPDATE';
    elsif deleting then
      v_audit_action := 'DELETE';
    end if;
    insert into rapo_config_bak values (
      :old.control_id,
      :old.control_name,
      :old.control_description,
      :old.control_alias,
      :old.control_group,
      :old.control_type,
      :old.control_engine,
      :old.source_name,
      :old.source_date_field,
      :old.source_filter,
      :old.output_table,
      :old.source_name_a,
      :old.source_date_field_a,
      :old.source_key_field_a,
      :old.source_filter_a,
      :old.source_type_a,
      :old.output_table_a,
      :old.source_name_b,
      :old.source_date_field_b,
      :old.source_key_field_b,
      :old.source_filter_b,
      :old.source_type_b,
      :old.output_table_b,
      :old.rule_config,
      :old.case_config,
      :old.case_definition,
      :old.error_definition,
      :old.need_a,
      :old.need_b,
      :old.schedule_config,
      :old.period_back,
      :old.period_number,
      :old.period_type,
      :old.iteration_config,
      :old.timeout,
      :old.instance_limit,
      :old.output_limit,
      :old.days_retention,
      :old.with_deletion,
      :old.with_drop,
      :old.parallelism,
      :old.need_hook,
      :old.need_prerun_hook,
      :old.need_postrun_hook,
      :old.preparation_sql,
      :old.prerequisite_sql,
      :old.completion_sql,
      :old.status,
      :old.updated_by,
      :old.updated_date,
      :old.created_by,
      :old.created_date,
      v_audit_action,
      v_audit_user,
      v_audit_date
    );
  end if;
end;
/
