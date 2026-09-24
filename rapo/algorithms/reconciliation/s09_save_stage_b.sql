create table rapo_temp_stage_b_{process_id}
nologging
as
select {parallelism} b.*,
       'Match' as rapo_result_type,
       cast(null as varchar2(4000)) as rapo_discrepancy_id,
       cast(null as varchar2(4000)) as rapo_discrepancy_description
  from rapo_temp_source_b_{process_id} b
       left join rapo_temp_t02_org_b_{process_id} o on {key_field_b} = o.b_id
 where {window_b}
   and o.correlation_indicator is not null
   and not exists (select e.{key_field_name_b} from rapo_temp_error_b_{process_id} e where {key_field_b} = e.{key_field_name_b})
