<template>
  <div class="asn1-details">
    <div v-if="!node" class="text-grey-7">Select a node to see its bytes and value.</div>
    <div v-else class="details-grid">
      <div class="details-label">Offset</div>
      <div class="text-mono">{{ formatNumber(node.offset) }} <span class="text-grey-7">(0x{{ hexAddress(node.offset) }})</span></div>
      <template v-if="node.undecodable">
        <div class="details-label">Bytes</div>
        <div>{{ formatNumber(node.length) }} that are no TLV</div>
      </template>
      <template v-else>
        <div class="details-label">Tag</div>
        <div>
          <span class="text-mono">{{ node.tag }}</span>
          <span class="text-grey-7"> · {{ nodeForm(node) }}</span>
        </div>
        <div class="details-label">Length</div>
        <div>{{ formatNumber(node.length) }} bytes <span class="text-grey-7">(header {{ node.header_len }})</span></div>
        <template v-if="name || node.type">
          <div class="details-label">Field</div>
          <div>
            <span v-if="name" class="text-weight-medium">{{ name }}</span>
            <span v-if="node.type" class="text-grey-8">{{ name ? " · " : "" }}{{ typeText }}</span>
          </div>
        </template>
        <template v-if="node.unknown">
          <div class="details-label">Grammar</div>
          <div class="text-orange-9">This tag is not expected here by the grammar</div>
        </template>
        <template v-if="!node.constructed">
          <div class="details-label">Value</div>
          <div>
            <div v-if="!readings.length" class="text-grey-7">No reading fits: see the bytes below</div>
            <div v-for="(reading, index) in readings" :key="index" class="row no-wrap items-baseline">
              <span class="reading-label text-grey-7">{{ reading.label }}</span>
              <span class="text-mono reading-value" :class="{ 'text-weight-medium': index === 0 }">{{ reading.value || "(empty)" }}</span>
            </div>
          </div>
          <div class="details-label">Hex</div>
          <div class="text-mono hex-value">{{ hexText }}</div>
        </template>
      </template>
    </div>
  </div>
</template>

<script>
import { formatNumber } from "../../utils/format";
import { hexAddress, nodeForm, nodeName } from "../../utils/asn1";

// The facts of the selected node (get-ds-file-asn1-node): offset, tag, form, length, field name and type with a
// grammar, and what a primitive value reads as.
export default {
  name: "Asn1Details",
  props: {
    // The node as listed in the tree, and its details once read (null while reading).
    node: { type: Object, default: null },
    detail: { type: Object, default: null },
  },
  computed: {
    name() {
      return this.node ? nodeName(this.node) : null;
    },
    typeText() {
      const chain = (this.detail && this.detail.type_chain) || [];
      const names = [this.node.type, ...chain].filter((name, index, all) => name && all.indexOf(name) === index);
      return names.join(" → ");
    },
    readings() {
      return (this.detail && this.detail.readings) || [];
    },
    hexText() {
      if (!this.detail) {
        return "…";
      }
      const pairs = (this.detail.hex || "").toUpperCase().match(/../g) || [];
      return pairs.join(" ") + (this.detail.hex_cut ? " …" : "");
    },
  },
  methods: { formatNumber, hexAddress, nodeForm },
};
</script>

<style scoped>
.asn1-details {
  font-size: 13px;
}
.details-grid {
  display: grid;
  grid-template-columns: 80px 1fr;
  column-gap: 12px;
  row-gap: 2px;
}
.details-label {
  color: var(--rapo-label);
}
.reading-label {
  flex: 0 0 140px;
}
.reading-value {
  word-break: break-all;
}
.hex-value {
  word-break: break-all;
  font-size: 12px;
}
</style>
