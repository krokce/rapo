# Rapo v0.8.2 Migration Instructions

Upgrades Rapo from v0.8.1 to v0.8.2. Commands run in the application folder.
What the release contains is in the [change log](CHANGELOG.md).

There is **no database schema change**. The release adds one Python dependency (`XlsxWriter`, for the email
attachments) and an optional `[EMAIL]` section in `rapo.ini`. It also ships a corrected `RAPO_USAGE_RULE`
procedure, which only matters where the `PL` engine is deployed.

1. Wait until all your Rapo controls are completed or cancel them. Stop the web server.
    ```bash
    .venv/bin/rapo-server stop
    ```
1. Update the source in the application folder and reinstall it.
    ```bash
    git fetch
    git checkout v0.8.2
    .venv/bin/pip install -r requirements.txt
    .venv/bin/pip install --no-build-isolation -e .
    ```
1. If you deployed the `PL` engine in v0.8.1, redeploy its procedure as the Rapo schema owner. This brings the
   eight engine fixes of this release.
    ```bash
    sqlplus <user>/<password>@<database> @schema/rapo_usage_rule.sql
    ```
1. To send email, add an `[EMAIL]` section to `rapo.ini` (the template is in `rapo.ini.example`). Without it, or
   with `enabled=False`, no email leaves the instance, whatever the controls say.
    ```ini
    [EMAIL]
    enabled=True
    host=smtp.example.com
    # starttls (default), ssl or none
    port=587
    security=starttls
    user=rapo@example.com
    password=...
    sender=rapo@example.com
    sender_name=RAPO
    # upper bounds of one attachment; above them the email goes without the file
    max_attachment_rows=100000
    max_attachment_mb=20
    ```
   `reply_to` and `timeout` (seconds, default 30) are optional. The password is never shown in the UI's
   Instance details.

   A test or development copy of production controls would mail the production recipients. Keep
   `enabled=False` on such instances, or point `host` at a local test mail server.
1. Start the web server.
    ```bash
    .venv/bin/rapo-server start
    ```
   The browser loads the new UI on the next page load. There is nothing to clear.

## Setting up an email

Open a control (analysis, report or reconciliation), set **Send email** to *Yes* in the Main tab, and fill in the
**Email** tab. Then **Apply**, and use **Send test** with your own address. It sends the control's last finished
run with the configuration you just saved.

The configuration is the `email` key of `rule_config`, so it can also be written with SQL. Everything except
`enabled`, `to` and `subject` may be omitted:

```json
{"email": {
  "enabled": true,
  "send_when": "done_with_results",
  "to": ["ra-team@example.com"], "cc": [], "bcc": [],
  "subject": "{control_name} {control_date_from:%Y-%m-%d}",
  "body": "Discrepancies of {control_date_from:%d.%m.%Y} attached.",
  "include_summary": true,
  "attach": true,
  "max_records": 50000,
  "sheets": {"main": {"name": "Discrepancies", "filter": "amount > 0",
                      "fields": [{"column": "MSISDN", "label": "Subscriber"}, {"column": "AMOUNT"}]}}
}}
```

A reconciliation control has `"a"` and `"b"` sheets instead of `"main"`, each with `"enabled"` and
`"result_types"` (a subset of `Loss`, `Discrepancy`, `Match`).

## Callers of the web API

`POST /api/save-control` behaves as before for existing callers. It answers `{"status": 200, "control_id": ...,
"updated_date": ...}` instead of `{"status": 200}`, and accepts an optional `expected_updated_date` that refuses a
stale write with `409`. See the [API reference](../../docs/api/README.md).
