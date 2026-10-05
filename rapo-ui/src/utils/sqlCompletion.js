// Completion of table and column names for CodeBox's `tables` ({name: [column]}), in place of lang-sql's schema
// completion: names are matched whatever their case, and table aliases are read from the whole text, subqueries and
// WITH parts included (lang-sql only reads the top level of a statement, case-sensitively).

const IDENTIFIER = String.raw`(?:"[^"]+"|[A-Za-z][\w$#]*)`;
const TABLE = String.raw`${IDENTIFIER}(?:\.${IDENTIFIER})?(?:@[\w.$#]+)?`;
// A table after FROM or JOIN, or after a comma of a FROM list, with an optional alias.
const SOURCE = new RegExp(String.raw`(?:\bfrom|\bjoin|,)\s+(${TABLE})(?:\s+(?:as\s+)?(${IDENTIFIER}))?`, "gi");
// Words that may follow a table but are not its alias.
const NOT_ALIAS = new Set(
  (
    "where on join left right inner outer full cross natural using group order having union intersect minus except " +
    "connect start pivot unpivot sample partition fetch for model with as select from offset window match_recognize " +
    "lateral apply when then else end and or not into values set"
  ).split(" "),
);
const WORD = /^[\w$#]*$/;

// Comments and string literals as spaces, so a word in them is never read as a table or an alias.
function codeOnly(text) {
  return text.replace(/\/\*[\s\S]*?\*\/|--[^\n]*|'(?:[^']|'')*'/g, (match) => " ".repeat(match.length));
}

// The dictionary name of an identifier: a quoted one as written, any other in upper case.
function normalizePart(part) {
  return part.startsWith('"') ? part.replace(/^"|"$/g, "") : part.toUpperCase();
}

function splitName(name) {
  return name.replace(/@.*$/, "").match(/"[^"]*"?|[^.]+/g) || [];
}

export function normalizeName(name) {
  return splitName(name).map(normalizePart).join(".");
}

// {ALIAS: TABLE} of a query, both normalized.
export function findAliases(text) {
  const aliases = {};
  for (const match of codeOnly(text).matchAll(SOURCE)) {
    const [, table, alias] = match;
    if (alias && !NOT_ALIAS.has(alias.toLowerCase())) {
      aliases[normalizePart(alias)] = normalizeName(table);
    }
  }
  return aliases;
}

export function tableCompletionSource(tables) {
  const index = new Map();
  for (const [name, columns] of Object.entries(tables || {})) {
    index.set(normalizeName(name), columns || []);
  }
  // A table of the own schema written with its owner is found under its plain name too.
  const lookup = (name) => index.get(name) || index.get(name.split(".").pop());
  const tableOptions = Object.keys(tables || {}).map((label) => ({ label, type: "type" }));
  const columnOptions = [...new Set([...index.values()].flat())].map((label) => ({ label, type: "property" }));

  return (context) => {
    // alias.col, table.col or owner.table.col
    const qualified = context.matchBefore(/(?:(?:"[^"]+"|[\w$#]+)\.){1,2}[\w$#]*$/);
    if (qualified) {
      const dot = qualified.text.lastIndexOf(".");
      const prefix = normalizeName(qualified.text.slice(0, dot));
      const aliases = prefix.includes(".") ? {} : findAliases(context.state.doc.toString());
      const columns = (aliases[prefix] && lookup(aliases[prefix])) || lookup(prefix);
      if (!columns) return null;
      return {
        from: qualified.from + dot + 1,
        options: columns.map((label) => ({ label, type: "property" })),
        validFor: WORD,
      };
    }
    const word = context.matchBefore(/[\w$#]+$/);
    if (!word && !context.explicit) return null;
    const aliases = Object.keys(findAliases(context.state.doc.toString())).map((label) => ({ label, type: "constant" }));
    return {
      from: word ? word.from : context.pos,
      options: [...tableOptions, ...aliases, ...columnOptions],
      validFor: WORD,
    };
  };
}
