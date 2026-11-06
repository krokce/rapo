# Rapo v0.8.8 Change Log

## Annotation
A control's own SQL now runs exactly as it is written. Up to v0.8.7 the Preparation, Prerequisite and Completion SQL,
the email's *Evaluate SQL* and an analysis' case definition were reformatted before they ran, which lower-cased
parts of some string literals. No schema change; the upgrade steps are in the [migration instructions](README.md).

1. **Control SQL runs verbatim.** Preparation, Prerequisite and Completion SQL, the email's *Evaluate SQL* and the
   case definition of an ANL control are run as written, after their `{variables}` are filled in (with the same
   strict rules as before: `{{` and `}}` are a literal brace). Before, they went through the SQL formatter, which
   upper-cased keywords, lower-cased names and re-indented the text, and which misread two kinds of literal:
   - a q-quoted literal holding a quote, e.g. `q'[create view v as select 'ABC' x from dual]'`, `q'[It's Ok]'`: the
     text after the inner quote was lower-cased (`'abc'`, `It's ok`);
   - a literal ending in a backslash, e.g. `'C:\'`: the literals after it in the statement were lower-cased.
   A view created by such a script got the wrong values, and every view created by a script was stored in the
   formatter's layout. Now the objects a script creates keep the text, case and layout written in the control.
   Plain literals (`'ABC'`, `'It''s'`, doubled quotes inside `execute immediate '...'`) and quoted names were
   never changed.
   - **Check:** controls with such literals (see the [migration instructions](README.md)); re-run them or recreate
     the objects their scripts created.
   - A script holding only blanks is still skipped.
1. **The run log shows the SQL.** The lines *Checking control prerequisite statement*, *Running control preparation
   SQL scripts* and *Running control completion SQL scripts* are followed by the statement as it runs, with its
   variables filled in; an email's *Evaluate SQL* is logged likewise (*Email: running Evaluate SQL*).

The view editor's *Format* button still reformats the query it shows (it lower-cases names and is subject to the same
two literal cases); the text is visible before it is compiled.
