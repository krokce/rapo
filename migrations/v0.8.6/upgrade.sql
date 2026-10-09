-- Rapo v0.8.5 -> v0.8.6
-- Adds the settings of the file viewer (ASN.1 grammars, per-datasource
-- delimiter and decoding). Re-runnable.

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
