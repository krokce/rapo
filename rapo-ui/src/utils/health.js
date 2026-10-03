// The tiles of the instance health (Instance details, Health tab): which sampled fields each one charts, how its
// value reads, which warning rules color it (rapo/health/monitor.py RULES) and which DB views it needs.
import { formatNumber } from "./format";

const percent = (value) => (value === null || value === undefined ? "–" : `${formatNumber(value, value < 10 ? 1 : 0)}%`);
const gb = (value) => (value === null || value === undefined ? "–" : `${formatNumber(value, value < 10 ? 2 : 1)} GB`);
const count = (value) => (value === null || value === undefined ? "–" : formatNumber(value));
// A rate in MB/s, shown in KB/s below 1 MB/s.
const rate = (value) => {
  if (value === null || value === undefined) {
    return "–";
  }
  return value < 1 ? `${formatNumber(value * 1024, value * 1024 < 10 ? 1 : 0)} KB/s` : `${formatNumber(value, value < 10 ? 2 : 1)} MB/s`;
};

// Seconds as "3 d 4 h", "2 h 10 min" or "5 min".
export function formatUptime(seconds) {
  if (seconds === null || seconds === undefined) {
    return null;
  }
  const minutes = Math.floor(seconds / 60);
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  if (days) {
    return `${days} d ${hours} h`;
  }
  return hours ? `${hours} h ${minutes % 60} min` : `${minutes} min`;
}

// The spans of the Health tab, in hours; the server answers which it keeps (get-instance-health `spans`).
export const HEALTH_SPANS = [1, 3, 6, 12, 24];

export const LEVEL_TEXT = { warn: "Warning", crit: "Critical" };

// group: os|db; series: [{field, label}] charted, the first is the value; max: a fixed top of the chart (else the
// highest value); rules: the warning rules, the first one draws its warn threshold; access: the DB sources needed.
export const HEALTH_TILES = [
  {
    key: "cpu",
    group: "os",
    title: "CPU",
    hint: "CPU used on this server's host, and by rapo's processes (server, runs, analysis workers), of all cores",
    series: [
      { field: "cpu", label: "Host" },
      { field: "cpu_rapo", label: "Rapo" },
    ],
    format: percent,
    max: 100,
    rules: ["cpu"],
    sub: (p) => `rapo ${percent(p.cpu_rapo)} · load ${p.load === null || p.load === undefined ? "–" : formatNumber(p.load, 2)} · ${p.cpus} cores`,
  },
  {
    key: "memory",
    group: "os",
    title: "Memory",
    hint: "Memory used on this server's host, and resident memory of rapo's processes",
    series: [
      { field: "memory", label: "Host" },
      { field: "memory_rapo", label: "Rapo" },
    ],
    format: percent,
    max: 100,
    rules: ["memory"],
    sub: (p) => `rapo ${gb(p.memory_rapo_gb)} of ${gb(p.memory_total_gb)} · swap ${percent(p.swap)}`,
  },
  {
    key: "processes",
    group: "os",
    title: "Processes",
    hint: "Rapo's processes: the server, its runs and analysis/scan workers; the host's total in the line below",
    series: [{ field: "processes_rapo", label: "Rapo" }],
    format: count,
    rules: [],
    sub: (p) => `host ${count(p.processes)} · rapo ${count(p.fds_rapo)} open files`,
  },
  {
    // A template: InstanceHealth makes one tile per file system of the latest sample's `disks` (diskTiles).
    key: "disk",
    group: "os",
    title: "Disk",
    hint: "Used space of the file systems holding the logs, rapo and the datasources' input and archive directories",
    series: [{ field: "used_percent", label: "Used" }],
    format: percent,
    max: 100,
    rules: ["disk"],
    perMount: true,
  },
  {
    key: "network",
    group: "os",
    title: "Network",
    hint: "Received (line) and sent (dashed) by the host, all interfaces but loopback; errors and drops since the sample before",
    series: [
      { field: "net_rx_mbs", label: "Received" },
      { field: "net_tx_mbs", label: "Sent" },
    ],
    format: rate,
    rules: [],
    sub: (p) => `sent ${rate(p.net_tx_mbs)} · errors ${count(p.net_errors)} · drops ${count(p.net_drops)}`,
  },
  {
    key: "connections",
    group: "os",
    title: "Connections",
    hint: "TCP connections of the host: established (line) and CLOSE_WAIT (dashed), connections the other side closed but a local program never did, a leak when it grows",
    series: [
      { field: "tcp_established", label: "Established" },
      { field: "tcp_close_wait", label: "CLOSE_WAIT" },
    ],
    format: count,
    rules: ["close_wait"],
    sub: (p) => `CLOSE_WAIT ${count(p.tcp_close_wait)} · TIME_WAIT ${count(p.tcp_time_wait)} · rapo→DB ${count(p.rapo_db_sockets)}`,
  },
  {
    key: "db_cpu",
    group: "db",
    title: "DB CPU",
    hint: "CPU used by this database (container) of its cpu_count, the last minute; AAS = average active sessions",
    series: [{ field: "db_cpu", label: "CPU" }],
    format: percent,
    max: 100,
    rules: ["db_cpu"],
    access: ["sysmetric", "parameter"],
    sub: (p) => `AAS ${p.aas ?? "–"} · ${p.db_cpu_cores ?? "–"} of ${p.cpu_count ?? "–"} CPUs`,
  },
  {
    key: "db_io",
    group: "db",
    title: "DB I/O",
    hint: "Physical reads (line) and writes (dashed) of the database, all files incl. redo and temp, the last minute",
    series: [
      { field: "io_read_mbs", label: "Read" },
      { field: "io_write_mbs", label: "Write" },
    ],
    format: rate,
    rules: [],
    access: ["sysmetric"],
    sub: (p) => `write ${rate(p.io_write_mbs)} · redo ${rate(p.redo_mbs)} · ${p.commits ?? "–"} commits/s`,
  },
  {
    key: "sessions",
    group: "db",
    title: "Sessions",
    hint: "User sessions of the database, and rapo's (module 'rapo'); click to list them",
    series: [
      { field: "sessions", label: "All" },
      { field: "sessions_rapo", label: "Rapo" },
    ],
    format: count,
    rules: [],
    access: ["session"],
    drill: "sessions",
    sub: (p) => `active ${count(p.sessions_active)} · rapo ${count(p.sessions_rapo)} (${count(p.sessions_rapo_active)} active)`,
  },
  {
    key: "locks",
    group: "db",
    title: "Locks",
    hint: "Sessions waiting for a lock another session holds; click to list them and their blockers",
    series: [{ field: "locks", label: "Blocked" }],
    format: count,
    rules: ["locks", "locks_wait"],
    access: ["session"],
    drill: "locks",
    sub: (p) => (p.locks ? `longest wait ${count(p.locks_wait)} s` : "no session blocked"),
  },
  {
    key: "db_memory",
    group: "db",
    title: "DB memory",
    hint: "PGA allocated, of pga_aggregate_limit; the SGA's maximum size in the line below",
    series: [{ field: "pga_percent", label: "PGA" }],
    format: percent,
    max: 100,
    rules: ["db_memory"],
    access: ["sgainfo", "pgastat", "parameter"],
    sub: (p) => `PGA ${gb(p.pga_gb)} of ${gb(p.pga_limit_gb)} · SGA ${gb(p.sga_gb)}`,
  },
  {
    key: "storage",
    group: "db",
    title: "Storage",
    hint: "Used space of rapo's default tablespace (line) and the size of rapo's result and temporary tables (dashed); each tablespace of the default and temporary ones below, of what it may grow to (autoextend counted)",
    series: [
      { field: "storage_gb", label: "Default tablespace" },
      { field: "rapo_gb", label: "Rapo tables" },
    ],
    format: gb,
    // The warning rule is a used percent, so its level colors the tile but draws no line on a chart in GB.
    rules: ["storage"],
    noThreshold: true,
    access: ["tablespace"],
    sub: (p) =>
      [...(p.tablespaces || []).map((ts) => `${ts.name} ${gb(ts.used_gb)} of ${gb(ts.size_gb)} (${percent(ts.used_percent)})`), p.rapo_gb !== undefined ? `rapo ${gb(p.rapo_gb)}` : null]
        .filter(Boolean)
        .join(" · "),
  },
];

// The order of the tiles of each tab, two per row; "disk" stands for one tile per file system.
export const HEALTH_ROWS = {
  os: ["cpu", "memory", "disk", "network", "connections", "processes"],
  db: ["db_cpu", "db_memory", "storage", "db_io", "sessions", "locks"],
};

export function healthTiles(group) {
  return HEALTH_ROWS[group].map((key) => HEALTH_TILES.find((tile) => tile.key === key));
}

const ROLE_TEXT = { logs: "logs", home: "rapo", input: "input", archive: "archive" };

// What a file system holds, e.g. "logs · rapo · 72 input · 61 archive dirs".
function diskRoles(roles) {
  const parts = Object.keys(ROLE_TEXT)
    .filter((role) => roles && roles[role])
    .map((role) => (role === "logs" || role === "home" ? ROLE_TEXT[role] : `${roles[role]} ${ROLE_TEXT[role]}`));
  return parts.join(" · ") + (roles && (roles.input || roles.archive) ? " dirs" : "");
}

// At most this many symlinks are named in a disk tile's hint.
const MAX_LINKS = 10;

// A disk tile's hint: its device, what it holds and the symlinks leading onto it (/data_in → /iris/DATA1/data_in).
function diskHint(template, disk) {
  const lines = [`${template.hint}.`, `${disk.mount}${disk.device ? ` (${disk.device})` : ""} holds ${diskRoles(disk.roles)}.`];
  const links = disk.links || [];
  if (links.length) {
    lines.push(...links.slice(0, MAX_LINKS).map(([link, target]) => `${link} → ${target}`));
    if (links.length > MAX_LINKS) {
      lines.push(`+${links.length - MAX_LINKS} more`);
    }
  }
  return lines.join("\n");
}

// The Disk template made into one tile per file system of the latest point, each charting its own used percent from
// the `disks` of every point (a point without the mount has no value). Its level is its own value against the disk
// thresholds, since the rule "disk" is the fullest one.
export function diskTiles(points, thresholds) {
  const template = HEALTH_TILES.find((tile) => tile.key === "disk");
  const latest = points.length ? points[points.length - 1].disks || [] : [];
  const [warn, crit] = (thresholds && thresholds.disk) || [];
  return latest.map((disk) => {
    const mountPoints = points.map((point) => {
      const item = (point.disks || []).find((other) => other.mount === disk.mount);
      return { t: point.t, used_percent: item ? item.used_percent : null, disk: item, errors: item && item.error ? { disk: item.error } : {} };
    });
    const value = disk.used_percent;
    const level = value === null || value === undefined ? null : crit !== null && crit !== undefined && value >= crit ? "crit" : warn !== null && warn !== undefined && value >= warn ? "warn" : null;
    return {
      ...template,
      key: `disk:${disk.mount}`,
      title: `Disk ${disk.mount}`,
      hint: diskHint(template, disk),
      points: mountPoints,
      level,
      sub: (p) => (p.disk ? `${gb(p.disk.free_gb)} free of ${gb(p.disk.total_gb)} · ${diskRoles(p.disk.roles)}` : "–"),
    };
  });
}

// The views a tile reads that this database user may not select from, as "GRANT SELECT ON ..." lines.
export function missingGrants(tile, access) {
  return (tile.access || []).filter((name) => access && access[name] && access[name].error).map((name) => access[name].grant);
}

// The worst level of a tile's rules.
export function tileLevel(tile, levels) {
  const values = tile.rules.map((rule) => levels && levels[rule]);
  return values.includes("crit") ? "crit" : values.includes("warn") ? "warn" : null;
}
