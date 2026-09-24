// Chain-rules: a control whose datasource is the result table of another control runs that control first, for
// the same period, and reads only the records of that run. The mirror of rapo/core/chain.py: only a plain
// RAPO_REST_/RAPO_RESA_/RAPO_RESB_<control name> of the own schema is such a datasource.
const RESULT_PREFIXES = ["rapo_rest_", "rapo_resa_", "rapo_resb_"];

// The datasource fields of a control type, with the side each feeds.
export function sourceFields(controlType) {
  if (controlType === "ANL" || controlType === "REP") {
    return [{ field: "source_name", side: null }];
  }
  if (controlType === "REC" || controlType === "CMP") {
    return [
      { field: "source_name_a", side: "a" },
      { field: "source_name_b", side: "b" },
    ];
  }
  return [];
}

// Control names by lower case, the lookup upstreamOf takes; built once per catalogue.
export function nameIndex(catalogue) {
  return new Map((catalogue || []).map((control) => [String(control.control_name).toLowerCase(), control.control_name]));
}

// The name of the control whose result table the datasource is, or null.
export function upstreamOf(sourceName, index) {
  if (!sourceName || typeof sourceName !== "string") {
    return null;
  }
  const table = sourceName.trim().toLowerCase();
  if (/[.@{}]/.test(table)) {
    return null;
  }
  const prefix = RESULT_PREFIXES.find((item) => table.startsWith(item));
  return prefix ? index.get(table.slice(prefix.length)) || null : null;
}

// The controls a configuration reads the results of, one entry per datasource.
export function upstreamsOf(control, index) {
  if (!control) {
    return [];
  }
  return sourceFields(control.control_type)
    .map(({ field, side }) => ({ field, side, control_name: upstreamOf(control[field], index) }))
    .filter((item) => item.control_name);
}

// Every control a run of this one runs first, in the order they run (the deepest first), each once.
export function allUpstreams(controlName, catalogue) {
  const index = nameIndex(catalogue);
  const byName = new Map((catalogue || []).map((control) => [control.control_name, control]));
  const order = [];
  const visit = (name, path) => {
    for (const { control_name } of upstreamsOf(byName.get(name), index)) {
      if (!path.includes(control_name) && !order.includes(control_name)) {
        visit(control_name, [...path, control_name]);
        order.push(control_name);
      }
    }
  };
  visit(controlName, [controlName]);
  return order;
}

// For every control, the controls it reads the results of and the ones reading its results.
export function chainIndex(catalogue) {
  const index = nameIndex(catalogue);
  const result = new Map();
  const entry = (name) => {
    if (!result.has(name)) {
      result.set(name, { upstream: [], dependents: [] });
    }
    return result.get(name);
  };
  for (const control of catalogue || []) {
    for (const { control_name } of upstreamsOf(control, index)) {
      entry(control.control_name).upstream.push(control_name);
      entry(control_name).dependents.push(control.control_name);
    }
  }
  return result;
}

// A sentence naming the controls a run performs first, or "" when there are none.
export function upstreamMessage(upstream) {
  return upstream.length ? `This will first run ${upstream.join(", ")} for the same period, and read only the results of those runs.` : "";
}
