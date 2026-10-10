-- Rapo v0.8.5 -> v0.8.6
-- Adds the settings of the file viewer (ASN.1 grammars, per-datasource
-- delimiter and decoding), the Dashboard's summary of the PDI Core file log
-- and the stored instance health. Re-runnable.

declare
  v_count number;
begin
  select count(*) into v_count from user_tables
   where table_name = 'RAPO_VIEWER_CONFIG';
  if v_count = 0 then
    execute immediate q'[
      create table rapo_viewer_config (
        config_type  varchar2(10 char) not null,
        config_name  varchar2(128 char) not null,
        content      clob not null,
        created_date date default sysdate not null,
        updated_date date default sysdate not null,
        constraint rapo_viewer_config_pk primary key (config_type, config_name)
      )]';
  end if;
end;
/

declare
  v_count number;
begin
  select count(*) into v_count from user_tables
   where table_name = 'RAPO_FILE_SUMMARY';
  if v_count = 0 then
    execute immediate q'[
      create table rapo_file_summary (
        load_day        date not null,
        load_hour       number(2) not null,
        sourceid        number not null,
        sourcename      varchar2(50 char),
        filestatus      varchar2(50 char) not null,
        duplicate       number(1) not null,
        files           number not null,
        records_read    number,
        records_write   number,
        records_reject  number,
        error_count     number,
        file_bytes      number,
        runtime_seconds number,
        summarized      date not null,
        constraint rapo_file_summary_pk
          primary key (load_day, load_hour, sourceid, filestatus, duplicate)
      )]';
  end if;
end;
/

declare
  v_count number;
begin
  select count(*) into v_count from user_tables
   where table_name = 'RAPO_HEALTH_MINUTE';
  if v_count = 0 then
    execute immediate q'[
      create table rapo_health_minute (
        server       varchar2(200 char) not null,
        sample_group varchar2(10 char) not null,
        minute       date not null,
        content      varchar2(4000 char) not null,
        constraint rapo_health_minute_pk primary key (server, sample_group, minute)
      )]';
  end if;
end;
/
