# Rapo

[![python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Revenue Assurance Processes Optimizer
Rapo is a Python instrument based on relational databases to build Revenue Assurance controls and, as a result, cover critical business risks and detect revenue leaks.

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

## Installation
Rapo runs from its own folder (the application folder) with a virtual environment inside it. It is no longer published on PyPI.

1. Get the source into the application folder and install it. Python 3.10 or newer is required.
    ```bash
    git clone <rapo-repository-url> rapo
    cd rapo
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/pip install --no-build-isolation -e .
    ```
   The built web UI is part of the source, so Node is not needed to install Rapo.

1. Deploy the database schema using the [scripts](schema/oracle.sql).

1. Prepare the configuration file _rapo.ini_ (start from `cp rapo.ini.example rapo.ini` and fill in the credentials and token) and place it in the application folder (next to the `rapo` package), or point the `RAPO_CONFIG` environment variable to it.

1. Start the server. It serves the API and the web UI on `[API] port` and runs the scheduler.
    ```bash
    .venv/bin/rapo-server start
    ```
   `rapo-server stop` stops it. The `rapo-scheduler` command is deprecated: the scheduler is part of the server.

   To start, stop, restart or inspect the server from outside the application folder, use the `rapo-ctl.sh start [dev] | stop | restart | status` wrapper in it. It resolves its own paths and virtual environment, so it needs no environment of its own, which makes it the command to start Rapo on boot:
    ```cron
    @reboot /path/to/rapo/rapo-ctl.sh start --wait 600
    ```
   `--wait` keeps retrying for that many seconds while the database is still coming up, and every action is logged to `rapo-ctl.log` in the log directory.

Upgrading from an earlier version? Follow the instructions of each release in [migrations](migrations/), in order.

## Usage
Prepare your controls using the configuration table as described in the documentation. Controls are created and edited in the web UI, which also shows their runs, their logs and the schedule.

To drive Rapo from your own tools - running controls, reading their results, following the scheduler - see the [web API reference](docs/api/README.md).
