# Rapo v0.7.0 Migration Instructions
This short document describes how to upgrade Rapo from v0.6.15 to v0.7.0:

1. Wait until all your Rapo controls are completed or cancel them. Stop the scheduler and the web server.
    ```bash
    rapo-scheduler stop
    rapo-server stop
    ```
1. Perform module upgrade `pip install --upgrade rapo==0.7.0`. It brings new dependencies `python-socketio` and
   `websockets` used for live UI updates.
1. Execute migration SQL [scripts](upgrade.sql) in database, which include:
    1. Index on `rapo_log.updated`, used by the web server to detect changed control runs and push them to the UI.
1. If the web server is behind a reverse proxy, allow WebSocket upgrades for `/api/socket.io`, e.g. for nginx:
    ```nginx
    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    ```
   Without it the UI still works over HTTP long-polling.
1. Start the scheduler and the web server.
    ```bash
    rapo-scheduler start
    rapo-server start
    ```
