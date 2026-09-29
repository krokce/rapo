# Rapo v0.8.4 Migration Instructions

Upgrades Rapo from v0.8.3 to v0.8.4. Commands run in the application folder.
What the release contains is in the [change log](CHANGELOG.md).

There is **no database schema change**; the `PL` engine's procedure `RAPO_USAGE_RULE` is redeployed.

1. Wait until all your Rapo controls are completed or cancel them. Stop the web server.
    ```bash
    .venv/bin/rapo-server stop
    ```
1. Update the source in the application folder and reinstall it.
    ```bash
    git fetch
    git checkout v0.8.4
    ./install.sh
    ```
1. If you deployed the `PL` engine, redeploy its procedure as the Rapo schema owner, so that its runs warn about a
   key field that is not unique.
    ```bash
    sqlplus <user>/<password>@<database> @schema/rapo_usage_rule.sql
    ```
1. After the upgrade, look at *Results* for runs with the warning icon: a reconciliation flagged *Key field ... is not
   unique* has repeated results; choose a unique key field for it.
1. For the Datasources page, where PDI Core is installed:
    * Rapo's database user needs `SELECT` on `PDI_CORE_DS_CONFIG`, `PDI_CORE_DS_TABLES` and `PDI_CORE_FILE_LOG`,
      plus `INSERT`, `UPDATE` on the first two to edit and `DELETE` to delete datasources and remove their tables.
      In another schema, give Rapo's user a private or public synonym of each. Without `SELECT` the menu items do
      not show.
    * For the Files page: `UPDATE` on `PDI_CORE_FILE_LOG` to recycle, reload or delete files, and `SELECT`, `INSERT`,
      `DELETE` on `PDI_CORE_STATE` to see, set and remove the lane locks (PDI Core's own grants have no `DELETE` on it).
    * The input, archive, error and duplicate directories are read from the server running `rapo-server`: run it
      on the ETL server, or mount the directories at the same paths. Directories created from the UI get the mode
      of `[DATASOURCES] dir_mode` (2775): the Pentaho server's user must be in their group.
    * Optionally add the `[DATASOURCES]` section to `rapo.ini` (see `rapo.ini.example`); every option has a default.
1. Start the web server.
    ```bash
    .venv/bin/rapo-server start
    ```
   Reload open browser tabs, so they load the new UI.
