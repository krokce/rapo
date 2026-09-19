# RAPO UI

Vue based GUI for the RAPO backend. The source lives here; the production build is written straight into
`../rapo/web/ui/`, which Flask serves and `setup.py` packages.

## Project setup
```
npm ci
```

### Compiles and hot-reloads for development
```
npm run serve
```
Requests to `/api` are proxied to `http://localhost:7005` by default; override with
`RAPO_API_URL=http://host:port npm run serve`.

### Compiles and minifies for production
```
npm run build
```
This replaces the contents of `../rapo/web/ui/`. Commit the rebuilt bundle together with the source change so
installs from git (and servers without Node) get the matching UI.
