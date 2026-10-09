// The ASN.1 view of the file viewer: what a node (as get-ds-file-asn1 answers it) shows, and the parts of its bytes.

// The fillers between records the server skips (ber.FILLERS).
export const FILLERS = [
  { value: "00ff", label: "00 and FF" },
  { value: "ff", label: "FF only" },
  { value: "none", label: "None" },
];

// The request parameters of a decoding ({grammar, top, start_offset, record_header, filler}).
export function decodingParams(decoding) {
  return {
    start_offset: decoding.start_offset || 0,
    record_header: decoding.record_header || 0,
    filler: decoding.filler || "00ff",
    grammar: decoding.grammar || null,
    top: decoding.top || null,
  };
}

// A node's segment of its full tag: the number of a tag of a class, the short name of a UNIVERSAL one (SEQ, SET).
export function fullTagSegment(node) {
  if (node.undecodable) {
    return "?";
  }
  if (node.cls !== "UNIVERSAL") {
    return String(node.number);
  }
  return node.number === 16 ? "SEQ" : node.number === 17 ? "SET" : node.tag;
}

// The label of a node: its name (or the CHOICE alternative it is), else its tag.
export function nodeName(node) {
  if (node.undecodable) {
    return "Undecodable";
  }
  if (node.name) {
    return node.name;
  }
  if (node.alternatives && node.alternatives.length) {
    return node.alternatives[node.alternatives.length - 1];
  }
  return null;
}

// The tag shown after "Tag :" as in common ASN.1 viewers, e.g. [20], [APPLICATION 1], SEQUENCE.
export function nodeTag(node) {
  return node.undecodable ? "" : node.tag;
}

// The value shown after a primitive node: its likeliest reading, else its first bytes in hex.
export function nodePreview(node) {
  if (node.undecodable || node.constructed) {
    return "";
  }
  return node.preview != null ? node.preview : node.preview_hex || "";
}

// The byte ranges of a node, [from, to) each: the tag, the length (and an indefinite length's EOC), the value.
export function nodeRanges(node) {
  if (!node) {
    return [];
  }
  if (node.undecodable) {
    return [{ kind: "value", from: node.offset, to: node.end }];
  }
  const valueStart = node.offset + node.header_len;
  const ranges = [
    { kind: "prefix", from: node.record_offset != null ? node.record_offset : node.offset, to: node.offset },
    { kind: "tag", from: node.offset, to: node.offset + node.tag_len },
    { kind: "len", from: node.offset + node.tag_len, to: valueStart },
    { kind: "value", from: valueStart, to: valueStart + node.length },
  ];
  if (node.indefinite) {
    ranges.push({ kind: "len", from: node.end - 2, to: node.end });
  }
  return ranges.filter((range) => range.to > range.from);
}

// The kind of byte at an offset in ranges (tag, len, value) or null.
export function rangeKind(ranges, offset) {
  for (const range of ranges) {
    if (offset >= range.from && offset < range.to) {
      return range.kind;
    }
  }
  return null;
}

// The form as ASN.1 viewers name it.
export function nodeForm(node) {
  if (node.undecodable) {
    return "";
  }
  return node.constructed ? (node.indefinite ? "CONSTRUCTED, indefinite length" : "CONSTRUCTED") : "PRIMITIVE";
}

// Offsets as hex addresses of 8 digits.
export function hexAddress(offset) {
  return offset.toString(16).toUpperCase().padStart(8, "0");
}

// The byte shown as text in a hex dump: printable ASCII, else a dot.
export function byteChar(byte) {
  return byte >= 0x20 && byte < 0x7f ? String.fromCharCode(byte) : ".";
}

// The key of the children listed under a node (its offset) or under the root.
export function parentKey(offset) {
  return offset == null ? "root" : String(offset);
}

// Reads a file as text: UTF-8, else Windows-1252 (any byte is a character), as .asn files of other tools are.
export async function readText(file) {
  const buffer = await file.arrayBuffer();
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(buffer);
  } catch {
    return new TextDecoder("windows-1252").decode(buffer);
  }
}

// Whether a text is a tag map of a Pentaho ASN.1 decoder rather than ASN.1 modules (as tagmap.looks_like).
export function looksLikeTagMap(text) {
  const plain = (text || "").replace(/\/\*[\s\S]*?\*\//g, " ").replace(/(^|\s)\/\/.*$/gm, " ");
  if (/\bDEFINITIONS\b/.test(plain)) {
    return false;
  }
  return /props\s*\.\s*(put|setProperty)\s*\(/.test(plain) || /^\s*\d+(\.\d+)*\s*[=:]/m.test(plain);
}
