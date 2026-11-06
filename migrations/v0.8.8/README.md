# Rapo v0.8.8 Migration Instructions

Upgrades Rapo from v0.8.7 to v0.8.8. Commands run in the application folder.
What the release contains is in the [change log](CHANGELOG.md).

The release changes no table and adds no option or package.

1. Wait until all your Rapo controls are completed or cancel them. Stop the web server.
    ```bash
    .venv/bin/rapo-server stop
    ```
1. Update the source in the application folder and reinstall it.
    ```bash
    git fetch
    git checkout v0.8.8
    ./install.sh
    ```
1. Start the web server.
    ```bash
    .venv/bin/rapo-server start
    ```
1. Check the controls whose Preparation, Prerequisite or Completion SQL, email *Evaluate SQL* or case definition
   holds a q-quoted literal with a quote inside (`q'[... 'ABC' ...]'`) or a literal ending in a backslash (`'C:\'`):
   up to v0.8.7 parts of such statements were lower-cased before they ran (see the [change log](CHANGELOG.md)).
   Re-run those controls, or recreate the views and other objects their scripts create, so the objects get the
   literals as written.
