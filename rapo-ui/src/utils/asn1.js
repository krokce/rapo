// The ASN.1 view of the file viewer: what a node (as get-ds-file-asn1 answers it) shows, and the parts of its bytes.

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
