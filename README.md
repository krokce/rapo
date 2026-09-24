# Rapo

[![python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Revenue Assurance Processes Optimizer
Rapo is a Python instrument based on relational databases to build Revenue Assurance controls and, as a result, cover critical business risks and detect revenue leaks.

## About this repository
This is a **fork** of the original [Rapo project](https://github.com/t3eHawk/rapo) by Timur Faradzhov, taken at
its v0.6.15, and it would not exist without it: the control engine, the reconciliation algorithm, the
configuration model and the database schema are its work, and this fork builds on all of them.

It also **merges in the [rapo-ui](https://github.com/krokce/rapo-ui) project**, the Vue web interface for Rapo,
which used to live in a repository of its own and be deployed next to the backend. Here the UI source is
`rapo-ui/` and its production build is committed as `rapo/web/ui/`, which the server itself serves, so backend and
UI are versioned, released and installed as one thing and no Node is needed to install Rapo.

On top of that the fork adds the FastAPI web server, live updates over socket.io, a scheduler that runs inside
the server with a lease, an event history and missed-fire handling, a run manager that gives every run its own
process, per-run log files shown in the UI, a documented web API, an optional Oracle-side execution engine
for reconciliation controls, results sent per email, and a KPI catalogue editor. The releases are described in
[migrations/v0.7.0](migrations/v0.7.0/README.md),
[migrations/v0.8.0](migrations/v0.8.0/CHANGELOG.md),
[migrations/v0.8.1](migrations/v0.8.1/CHANGELOG.md) and
[migrations/v0.8.2](migrations/v0.8.2/CHANGELOG.md).

Both upstream projects are MIT-licensed, and so is this one. [NOTICE](NOTICE) records what comes from where.

Releases of the fork carry a local version segment - `0.8.2+fork` - because the original project keeps its own
numbering and is at v0.6.15; the two version lines say nothing about each other.

## Prologue
If you are part of the Revenue Assurance Team, then you probably know that the core is a system of controls that allows you to perform your daily responsibilities and generate reports required by business.

Usually, this system is implemented using third-party software.
Sometimes it is provided by special vendors, and sometimes it is packed with the billing system.

Anyway, the license purchase is required, as is probably the recruitment of the integration team.
This causes an additional investment, which could not be confirmed by the business sponsors.

In addition, such software is usually used in part because many of features are outdated or not required. Outdated design is also often encountered and can be a problem.

So Rapo is created by RA engineers to solve such problems and provides a modern and simple alternative solution for the RA system.

## Advantages
If you are a young RA Team or looking for some alternatives, try Rapo because:
* Free to use right now and here.
* Easy start with low installation efforts.
* Easy control preparation based on SQL, which should not be a problem for RA experts.
* Open-source Python technology, so it won't be an issue to find an expert who can maintain or even improve the solution for your specific needs.
* Built-in Python interface that allows you to integrate the system, including control results, with some popular data science tools or machine learning modules.
* Ready-to-use REST API that allows you to interact with controls or send the control results to some Dashboard or reporting tool.
* This is a developing project with an open feature list and many plans.
* Last but not least, Rapo is created by RA specialists with more than 10 years of expiriens, hundreds of found incidents, and, in turn, millions in saved revenue for their company and investors.

## What you get
* **Controls of four types** - analysis (`ANL`), reconciliation (`REC`), comparison (`CMP`) and report (`REP`).
  A control is a row in the `rapo_config` table: its sources, SQL filters, matching rules, output and schedule.
  The Python package is the generic engine that reads that row and runs its SQL against the database.
* **A web UI** to write and edit those controls, to follow their runs day by day, to read the log of a single run
  and to watch and steer the scheduler - served by the server itself, on the same port as the API. The editor
  saves in place (Apply), so a control can be changed, run and checked without leaving it.
* **One server process**. `rapo-server` serves the API, the UI and the scheduler. Several servers may run against
  the same database: they share the scheduler through a lease with a heartbeat, and each of them performs its own
  runs.
* **A run manager**. Every run, scheduled or started by hand, is initiated at once (visible and cancellable),
  queued under `control_parallelism` and performed in its own process, with its `timeout` enforced and its
  iterations and cascade following it in the same process.
* **A scheduler that accounts for itself**. Schedule changes apply without a restart, fires are never dropped
  silently, and a fire that fell into a downtime is recorded as missed and can be run later for its original
  moment. Every run request is kept in `rapo_scheduler_event` with its trigger and its outcome.
* **Live updates**. The server diffs the relevant tables and pushes the changes over socket.io, so the UI reacts
  to what happens in the database rather than polling.
* **Results per email**. A control can mail its results when a run finishes: recipients, a subject and body with
  run variables, and an Excel file of the run's rows, filtered and with the fields you choose. SMTP is set once in
  the `[EMAIL]` section of `rapo.ini`.
* **Logs you can read**. One file per control run under `controls/<control_id>/<process_id>.log`, everything else
  in `rapo-server_YYYYMMDD.log`, both cleaned up on a retention of their own and both reachable from the UI.
* **A documented web API** ([reference](docs/api/README.md)) for reports, dashboards and scripts outside this
  repository.

## Repository layout
| Path            | What it is                                                                              |
|-----------------|-----------------------------------------------------------------------------------------|
| `rapo/`         | the Python package: engine, algorithms, scheduler, run manager, FastAPI app              |
| `rapo/web/ui/`  | the built UI bundle that the server serves and `setup.py` packages - generated, never edited by hand |
| `rapo-ui/`      | the Vue 3 + Quasar source of that bundle (Node only needed to rebuild it)                |
| `schema/`       | the database schema (`oracle.sql`)                                                       |
| `migrations/`   | one folder per release: the upgrade SQL and the instructions                              |
| `docs/api/`     | the web API reference                                                                     |

## Installation
Rapo runs from its own folder (the application folder) with a virtual environment inside it. It is not published
on PyPI.

1. Get the source into the application folder and install it. Python 3.10 or newer and the
   [Oracle Instant Client](https://www.oracle.com/database/technologies/instant-client.html) are required.
    ```bash
    git clone https://github.com/krokce/rapo.git rapo
    cd rapo
    ./install.sh
    ```
   `install.sh` creates the virtual environment `.venv` in the application folder, lets you choose the Python it is
   built with (or name it: `./install.sh --python python3.12`), installs the requirements and Rapo, creates
   _rapo.ini_ from _rapo.ini.example_ when there is none, and checks that the Oracle Instant Client can be loaded.
   Run it as the user that runs Rapo (`--allow-root` otherwise). Run again, it updates the packages of the existing
   environment, which is also how an upgrade reinstalls them; `--force` deletes the environment and creates it anew,
   and is refused while Rapo runs from it. `RAPO_HOME`, `RAPO_VENV` and `RAPO_CONFIG` override the paths, as for
   `rapoctl.sh`. The built web UI is part of the source, and the Oracle driver (`oracledb`) needs no compiler, so
   neither Node nor build tools are needed.

   The same by hand:
    ```bash
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/pip install --no-build-isolation -e .
    ```

1. Deploy the database schema using the [scripts](schema/oracle.sql).

1. Prepare the configuration file _rapo.ini_ (`install.sh` creates it from _rapo.ini.example_; fill in the credentials and token, and set `client_path` to the Instant Client folder so that a start from cron finds it) and place it in the application folder (next to the `rapo` package), or point the `RAPO_CONFIG` environment variable to it.

1. Start the server. It serves the API and the web UI on `[API] port` and runs the scheduler.
    ```bash
    .venv/bin/rapo-server start
    ```
   `rapo-server stop` stops it. The `rapo-scheduler` command is deprecated: the scheduler is part of the server.

   To start, stop, restart or inspect the server from outside the application folder, use the `rapoctl.sh start [dev] | stop | restart | status` wrapper in it. It resolves its own paths and virtual environment, so it needs no environment of its own, which makes it the command to start Rapo on boot:
    ```cron
    @reboot /path/to/rapo/rapoctl.sh start --wait 600
    ```
   `--wait` keeps retrying for that many seconds while the database is still coming up, and every action is logged to `rapoctl.log` in the log directory.

Upgrading from an earlier version? Follow the instructions of each release in [migrations](migrations/), in order.

## Usage
Prepare your controls using the configuration table as described in the documentation. Controls are created and edited in the web UI, which also shows their runs, their logs and the schedule.

To drive Rapo from your own tools - running controls, reading their results, following the scheduler - see the [web API reference](docs/api/README.md).

## Working on the UI
The bundle in `rapo/web/ui/` is generated. To change the interface, edit `rapo-ui/src`, rebuild, and commit the
bundle together with the source change (Node 22 / npm 10):
```bash
cd rapo-ui
npm ci
npm run build        # empties and rebuilds ../rapo/web/ui/
npm run lint         # eslint + prettier
```
For development, run the server without the scheduler and the UI with hot reload against it:
```bash
.venv/bin/rapo-server start dev
cd rapo-ui && RAPO_API_URL=http://localhost:<API.port> npm run serve
```

## Credits
* [Timur Faradzhov](https://github.com/t3eHawk) - author of [Rapo](https://github.com/t3eHawk/rapo), the engine
  this project is built on.
* [Kostadin Taneski](https://github.com/krokce) - author of [rapo-ui](https://github.com/krokce/rapo-ui) and
  maintainer of this fork.

## License
MIT, as the upstream projects. See [LICENSE](LICENSE) for the terms and [NOTICE](NOTICE) for the provenance of
the parts.
