// Formula mode of REC and CMP criteria: a field becomes an SQL expression referring to the sides as `a.` and `b.`.

/**
 * The formula a field starts with when formula mode is switched on.
 * @param {string|null} field - the chosen column
 * @param {string} prefix - "a." or "b."
 * @returns {string}
 */
export function toFormula(field, prefix) {
  return prefix + (field || "");
}

/**
 * The column a formula goes back to when formula mode is switched off: the column when the formula is only
 * `<prefix><column>` of a column of that side (any case), else null.
 * @param {string|null} formula
 * @param {string} prefix - "a." or "b."
 * @param {string[]} columns - the side's columns
 * @returns {string|null}
 */
export function fromFormula(formula, prefix, columns) {
  const text = (formula || "").trim().toLowerCase();
  if (!text.startsWith(prefix)) {
    return null;
  }
  const name = text.slice(prefix.length);
  return (columns || []).find((column) => column.toLowerCase() === name) ?? null;
}
