<script setup lang="ts">
// Horizontal grouped bars: one row per category, one thin bar per series.
// Values are shown as a share of each series' total (so models of different
// size compare fairly); the hover card gives the raw counts.
import { computed, ref } from 'vue';

export interface Series {
  id: string;
  label: string;
  color: string; // CSS colour, e.g. var(--series-1)
}

const props = defineProps<{
  categories: { key: string; label: string }[];
  series: Series[];
  /** counts[seriesId][categoryKey] */
  counts: Record<string, Record<string, number>>;
  /** What one unit is, for the hover card (e.g. "relations"). */
  unit: string;
}>();

const totals = computed(() =>
  Object.fromEntries(props.series.map((s) => [s.id, Object.values(props.counts[s.id] ?? {}).reduce((a, b) => a + b, 0)])),
);

function count(seriesId: string, key: string) {
  return props.counts[seriesId]?.[key] ?? 0;
}
function share(seriesId: string, key: string) {
  const total = totals.value[seriesId];
  return total ? (100 * count(seriesId, key)) / total : 0;
}
const maxShare = computed(() =>
  Math.max(1, ...props.categories.flatMap((c) => props.series.map((s) => share(s.id, c.key)))),
);

const fmtPct = (v: number) => (v >= 10 ? v.toFixed(0) : v.toFixed(1)) + '%';

// ---- hover card ----
const hover = ref<{ key: string; x: number; y: number } | null>(null);
const TIP_WIDTH = 240;
const root = ref<HTMLElement | null>(null);
function onMove(key: string, ev: MouseEvent) {
  const box = root.value?.getBoundingClientRect();
  if (!box) return;
  // keep the card inside the chart: flip to the left of the cursor near the right edge
  const x = ev.clientX - box.left;
  hover.value = { key, x: x + 14 + TIP_WIDTH > box.width ? Math.max(0, x - 14 - TIP_WIDTH) : x + 14, y: ev.clientY - box.top + 10 };
}
const hoverCategory = computed(() => props.categories.find((c) => c.key === hover.value?.key));
</script>

<template>
  <div ref="root" class="gbars" @mouseleave="hover = null">
    <div
      v-for="cat in categories"
      :key="cat.key"
      class="row"
      :class="{ active: hover?.key === cat.key }"
      @mousemove="onMove(cat.key, $event)"
    >
      <div class="label" :title="cat.label">{{ cat.label }}</div>
      <div class="bars">
        <div v-for="s in series" :key="s.id" class="bar-line">
          <span class="bar" :style="{ width: (share(s.id, cat.key) / maxShare) * 100 + '%', background: s.color }" />
          <span class="value">{{ fmtPct(share(s.id, cat.key)) }}</span>
        </div>
      </div>
    </div>

    <div
      v-if="hover && hoverCategory"
      class="tip"
      :style="{ left: hover.x + 'px', top: hover.y + 'px', width: TIP_WIDTH + 'px' }"
      role="tooltip"
    >
      <div class="tip-title">{{ hoverCategory.label }}</div>
      <div v-for="s in series" :key="s.id" class="tip-row">
        <span class="swatch" :style="{ background: s.color }" />
        <span class="tip-name">{{ s.label }}</span>
        <span class="tip-val">{{ count(s.id, hoverCategory.key).toLocaleString() }} {{ unit }}</span>
        <span class="tip-pct">{{ fmtPct(share(s.id, hoverCategory.key)) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.gbars {
  position: relative;
  display: flex;
  flex-direction: column;
}

.row {
  display: grid;
  grid-template-columns: minmax(90px, 140px) 1fr;
  gap: 12px;
  align-items: center;
  padding: 6px 4px;
  border-radius: var(--radius-sm);
}

.row.active {
  background: var(--surface-muted);
}

.label {
  font-size: 13px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bars {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.bar-line {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 9px;
}

.bar {
  height: 8px;
  min-width: 2px;
  border-radius: 0 4px 4px 0;
}

.value {
  font-size: 11px;
  line-height: 1;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.tip {
  position: absolute;
  z-index: 5;
  pointer-events: none;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow);
  padding: 8px 10px;
  font-size: 12.5px;
}

.tip-title {
  font-weight: 700;
  color: var(--heading);
  margin-bottom: 4px;
}

.tip-row {
  display: grid;
  grid-template-columns: 10px 1fr auto auto;
  gap: 8px;
  align-items: center;
  color: var(--text);
}

.swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
}

.tip-val {
  font-variant-numeric: tabular-nums;
}

.tip-pct {
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  min-width: 42px;
  text-align: right;
}

@media (max-width: 600px) {
  .row {
    grid-template-columns: 90px 1fr;
    gap: 8px;
  }
}
</style>
