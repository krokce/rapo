<template>
  <div class="analysis-layout">
    <!-- Narrow screens: the sections in one row under the header. -->
    <nav v-if="narrow && sections.length > 1" class="rail-row row no-wrap items-center q-gutter-x-xs q-mb-md" aria-label="On this page">
      <q-btn
        v-for="section in sections"
        :key="section.id"
        flat
        dense
        no-caps
        size="13px"
        padding="4px 10px"
        :color="section.id === active ? 'teal' : 'blue-grey-8'"
        :icon="section.icon"
        :label="section.label"
        :aria-current="section.id === active ? 'true' : undefined"
        @click="go(section.id)" />
    </nav>
    <div class="row no-wrap items-start">
      <div class="col analysis-main">
        <slot />
      </div>
      <nav v-if="!narrow && sections.length > 1" class="rail" aria-label="On this page">
        <div class="rail-title">On this page</div>
        <a
          v-for="section in sections"
          :key="section.id"
          class="rail-link row no-wrap items-center"
          :class="{ 'rail-link--active': section.id === active }"
          :href="`#${section.id}`"
          :aria-current="section.id === active ? 'true' : undefined"
          @click.prevent="go(section.id)">
          <q-icon :name="section.icon" size="13px" class="q-mr-sm" />
          <span class="col ellipsis">{{ section.label }}</span>
          <span v-if="section.count !== null && section.count !== undefined" class="rail-count">{{ formatNumber(section.count) }}</span>
        </a>
      </nav>
    </div>
  </div>
</template>

<script>
import { formatNumber } from "../../utils/format";

// The point below the fixed header where a section counts as the one being read.
const READING_LINE = 120;

// The skeleton of the analysis pages: the sections (AnalysisSection, by `id`) in one scrolling column, and the rail "On
// this page" beside it (in a row under the header on narrow screens), the section being read marked as the page
// scrolls. A link scrolls its section to the top and puts its id in the URL hash, so a copied link opens there; the
// page scrolls to the hash itself once loaded (scrollTo). Kept alive with its page, so it listens only while active.
export default {
  name: "AnalysisLayout",
  props: {
    // [{id, label, icon, count}], in page order.
    sections: { type: Array, required: true },
  },
  data() {
    return { active: null };
  },
  computed: {
    narrow() {
      return this.$q.screen.lt.md;
    },
  },
  watch: {
    sections() {
      this.$nextTick(this.update);
    },
  },
  created() {
    this.onScroll = () => {
      if (!this.frame) {
        this.frame = requestAnimationFrame(() => {
          this.frame = null;
          this.update();
        });
      }
    };
  },
  mounted() {
    this.listen();
  },
  activated() {
    this.listen();
  },
  deactivated() {
    this.unlisten();
  },
  unmounted() {
    this.unlisten();
  },
  methods: {
    formatNumber,
    listen() {
      if (!this.listening) {
        this.listening = true;
        window.addEventListener("scroll", this.onScroll, { passive: true });
        window.addEventListener("resize", this.onScroll, { passive: true });
        this.$nextTick(this.update);
      }
    },
    unlisten() {
      this.listening = false;
      window.removeEventListener("scroll", this.onScroll);
      window.removeEventListener("resize", this.onScroll);
    },
    // The last section whose top has passed the reading line, or the last one at the bottom of the page.
    update() {
      const elements = this.sections.map((section) => document.getElementById(section.id)).filter(Boolean);
      if (!elements.length) {
        this.active = null;
        return;
      }
      const root = document.documentElement;
      let active = elements[0].id;
      if (window.scrollY > 0 && window.innerHeight + window.scrollY >= root.scrollHeight - 4) {
        active = elements[elements.length - 1].id;
      } else {
        elements.forEach((element) => {
          if (element.getBoundingClientRect().top <= READING_LINE) {
            active = element.id;
          }
        });
      }
      this.active = active;
    },
    go(id) {
      this.scrollTo(id);
      if (this.$route.hash !== `#${id}`) {
        this.$router.replace({ query: this.$route.query, hash: `#${id}` });
      }
    },
    // Scrolls a section to the top; false when the page does not have it (yet).
    scrollTo(id, smooth = true) {
      const element = document.getElementById(id);
      if (!element) {
        return false;
      }
      element.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
      this.active = id;
      return true;
    },
  },
};
</script>

<style scoped>
.analysis-main {
  min-width: 0;
}

.rail {
  position: sticky;
  top: 84px;
  flex: 0 0 188px;
  margin-left: 24px;
  font-size: 13px;
}

.rail-title {
  color: var(--rapo-label);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0 0 6px 12px;
}

.rail-link {
  padding: 5px 8px 5px 10px;
  border-left: 2px solid var(--rapo-grid);
  color: var(--rapo-strong);
  text-decoration: none;
}

.rail-link:hover {
  background: var(--rapo-row-hover);
}

.rail-link--active {
  border-left-color: var(--rapo-teal);
  color: var(--rapo-teal);
  font-weight: 500;
}

.rail-count {
  margin-left: 8px;
  color: var(--rapo-label);
  font-size: 12px;
}

.rail-row {
  position: sticky;
  top: 62px;
  z-index: 2;
  overflow-x: auto;
  background: var(--rapo-page);
  border-bottom: 1px solid var(--rapo-grid);
}
</style>
