// The tiles of the instance health (Instance details, Health tab): which sampled fields each one charts, how its
// value reads, which warning rules color it (rapo/health/monitor.py RULES) and which DB views it needs.
import { formatNumber } from "./format";

const percent = (value) => (value === null || value === undefined ? "–" : `${formatNumber(value, value < 10 ? 1 : 0)}%`);
const gb = (value) => (value === null || value === undefined ? "–" : `${formatNumber(value, value < 10 ? 2 : 1)} GB`);
const count = (value) => (value === null || value === undefined ? "–" : formatNumber(value));

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
    sub: (p) => `rapo ${percent(p.cpu_rapo)} · load ${p.load ?? "–"} · ${p.cpus} cores`,
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
    key: "disk",
    group: "os",
    title: "Disk",
    hint: "Used space of the file systems holding the log directory and rapo's home, the fullest one charted",
    series: [{ field: "disk", label: "Used" }],
    format: percent,
    max: 100,
    rules: ["disk"],
    sub: (p) => (p.disks || []).map((disk) => `${gb(disk.free_gb)} free`).join(" · ") || "–",
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
    hint: "Used space of rapo's default and temporary tablespaces (autoextend counted), the fullest one charted; rapo's result and temporary tables below",
    series: [{ field: "storage", label: "Used" }],
    format: percent,
    max: 100,
    rules: ["storage"],
    access: ["tablespace"],
    sub: (p) =>
      [...(p.tablespaces || []).map((ts) => `${ts.name} ${percent(ts.used_percent)}`), p.rapo_gb !== undefined ? `rapo ${gb(p.rapo_gb)}` : null]
        .filter(Boolean)
        .join(" · "),
  },
];

// The views a tile reads that this database user may not select from, as "GRANT SELECT ON ..." lines.
export function missingGrants(tile, access) {
  return (tile.access || []).filter((name) => access && access[name] && access[name].error).map((name) => access[name].grant);
}

// The worst level of a tile's rules.
export function tileLevel(tile, levels) {
  const values = tile.rules.map((rule) => levels && levels[rule]);
  return values.includes("crit") ? "crit" : values.includes("warn") ? "warn" : null;
}
