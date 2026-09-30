# Rapo v0.8.5 Change Log

## Annotation
The email of a control can be sent on the result of an SQL statement. There is no change to Rapo's own schema. The
upgrade steps are in the [migration instructions](README.md).

1. **Email: Send when *Evaluate SQL*.** A fourth *Send when* option on the editor's *Email* tab (ANL, REP, REC). The
   email is sent only when the *Evaluate SQL* returns a number above 0, whatever the run's status (Done or Error) or
   its result rows; an Error run's email carries the error and no file, as with *Done or error*.
   - The statement is written like the *Prerequisite SQL*: a select returning one number (first column of the first
     row), with the variables `{control_name}`, `{process_id}`, `{control_date}`, `{control_date_from}` and
     `{control_date_to}` (strict formatting: an unknown variable fails). The editor's *Check* validates it as a
     prerequisite, and its *Example* menu offers ready statements.
   - 0 or a negative number: no email (INFO line in the run log). A failing statement, no row, NULL, a non-numeric
     value or an empty statement: no email and a WARNING line in the run log. The run's status never changes.
   - The value is logged (`Email: Evaluate SQL returned N`) and available as the email variable `{evaluate_value}`
     in the subject, the body and the file name.
   - *Resend* (Results menu) and *Send test* (editor) always send; they still evaluate the statement, and a test's
     body notes when a run would not send (`Evaluate SQL returned 0, so a run would not send this email.`).
   - Stored as `rule_config.email.send_when = "evaluate_sql"` with `rule_config.email.evaluate_sql`. The statement is
     kept, and ignored, when another option is chosen. Save is refused while the option is chosen without a statement.
