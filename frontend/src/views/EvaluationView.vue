<script setup lang="ts">
// LLM comparison: the same AMD abstracts, extracted by three different LLMs and
// stored in one repository each. Statistics come from GET /api/evaluation.
import { computed, onMounted, ref } from 'vue';
import axios from 'axios';
import AppSidebar from '@/components/AppSidebar.vue';
import GroupedBars, { type Series } from '@/components/GroupedBars.vue';
import { API_URL } from '@/config';
import { ENTITY_STYLES } from '@/graph/palette';
import { repoInfo } from '@/graph/repositories';

interface RepoStats {
  relations: number;
  unique_triples: number;
  only_here: number;
  entities: number;
  links: number;
  avg_degree: number;
  clustering: number;
  relation_types: Record<string, number>;
  entity_types: Record<string, number>;
  degree_distribution: Record<string, number>;
  top_entities: { name: string; degree: number }[];
}
interface Evaluation {
  repositories: string[];
  stats: Record<string, RepoStats>;
  overlap: Record<string, Record<string, number>>;
  common_to_all: number;
}


const data = ref<Evaluation | null>(null);
const error = ref('');
const loading = ref(true);

onMounted(async () => {
  try {
    data.value = (await axios.get<Evaluation>(`${API_URL}/api/evaluation`, { timeout: 120000 })).data;
  } catch (e: any) {
    error.value = e?.response?.data?.error ?? `The API at ${API_URL || window.location.origin} did not answer.`;
  } finally {
    loading.value = false;
  }
});

// Series colour follows the repository (fixed order), never its rank
const series = computed<Series[]>(() =>
  (data.value?.repositories ?? []).map((id, i) => ({
    id,
    label: repoInfo(id).label,
    color: `var(--series-${(i % 3) + 1})`,
  })),
);

function countsOf(field: 'relation_types' | 'entity_types' | 'degree_distribution') {
  const out: Record<string, Record<string, number>> = {};
  for (const id of data.value?.repositories ?? []) out[id] = data.value!.stats[id]![field];
  return out;
}

/** Categories ordered by their average share across the models. */
function rankedCategories(field: 'relation_types' | 'entity_types', label: (k: string) => string) {
  const counts = countsOf(field);
  const share: Record<string, number> = {};
  for (const id of Object.keys(counts)) {
    const c = counts[id]!;
    const total = Object.values(c).reduce((a, b) => a + b, 0) || 1;
    for (const [k, v] of Object.entries(c)) share[k] = (share[k] ?? 0) + v / total;
  }
  return Object.keys(share)
    .sort((a, b) => share[b]! - share[a]!)
    .map((key) => ({ key, label: label(key) }));
}

const relationCategories = computed(() => rankedCategories('relation_types', (k) => k));
const entityCategories = computed(() => rankedCategories('entity_types', (k) => ENTITY_STYLES[k]?.label ?? k));
// Fixed bucket order (JSON object keys arrive sorted alphabetically)
const DEGREE_BUCKETS = ['1', '2', '3–5', '6–10', '11–20', '21+'];
const degreeCategories = computed(() => {
  const present = Object.keys(data.value?.stats[data.value.repositories[0]!]?.degree_distribution ?? {});
  return [...DEGREE_BUCKETS.filter((k) => present.includes(k)), ...present.filter((k) => !DEGREE_BUCKETS.includes(k))]
    .map((key) => ({ key, label: `${key} link${key === '1' ? '' : 's'}` }));
});

const SUMMARY: { key: keyof RepoStats; label: string; hint: string; digits?: number }[] = [
  { key: 'relations', label: 'Relations', hint: 'stored relations (a triple found in several abstracts counts each time)' },
  { key: 'unique_triples', label: 'Distinct triples', hint: 'distinct (subject, relation, object) triples' },
  { key: 'only_here', label: 'Found only by this model', hint: 'distinct triples no other model extracted' },
  { key: 'entities', label: 'Entities', hint: 'nodes taking part in at least one relation' },
  { key: 'links', label: 'Entity pairs linked', hint: 'distinct subject → object pairs' },
  { key: 'avg_degree', label: 'Average degree', hint: 'links per entity', digits: 2 },
  { key: 'clustering', label: 'Clustering coefficient', hint: 'how often the neighbours of an entity are linked too', digits: 3 },
];

function fmt(v: number, digits?: number) {
  return digits ? v.toFixed(digits) : v.toLocaleString();
}
function best(key: keyof RepoStats) {
  const vals = (data.value?.repositories ?? []).map((id) => data.value!.stats[id]![key] as number);
  return Math.max(...vals);
}
const pretty = (name: string) => name.replace(/_/g, ' ');
</script>

<template>
  <div class="app-shell">
    <AppSidebar />
    <main class="page eval">
      <header class="page-head">
        <div>
          <h1>LLM comparison</h1>
          <p class="muted">
            The same 100 AMD abstracts, with relations extracted by three different LLMs (one graph each).
          </p>
        </div>
        <div v-if="series.length" class="legend" aria-label="Legend">
          <span v-for="s in series" :key="s.id" class="legend-item">
            <span class="swatch" :style="{ background: s.color }" />{{ s.label }}
          </span>
        </div>
      </header>

      <p v-if="loading" class="muted">Computing the comparison…</p>
      <p v-else-if="error" class="msg msg-error">{{ error }}</p>

      <template v-else-if="data">
        <section class="card">
          <h2 class="card-title">At a glance</h2>
          <div class="table-wrap">
            <table class="summary">
              <thead>
                <tr>
                  <th scope="col"></th>
                  <th v-for="s in series" :key="s.id" scope="col">
                    <span class="swatch" :style="{ background: s.color }" />{{ s.label }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in SUMMARY" :key="row.key">
                  <th scope="row">
                    {{ row.label }}
                    <span class="row-hint">{{ row.hint }}</span>
                  </th>
                  <td
                    v-for="s in series"
                    :key="s.id"
                    :class="{ top: (data.stats[s.id]![row.key] as number) === best(row.key) }"
                  >
                    {{ fmt(data.stats[s.id]![row.key] as number, row.digits) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="muted note">Highest value in each row in bold. Hover a chart row below for raw counts.</p>
        </section>

        <div class="grid">
          <section class="card">
            <h2 class="card-title">Relation types</h2>
            <p class="card-sub">Share of each model's relations</p>
            <GroupedBars :categories="relationCategories" :series="series" :counts="countsOf('relation_types')" unit="relations" />
          </section>

          <section class="card">
            <h2 class="card-title">Entity types</h2>
            <p class="card-sub">Share of each model's typed entities</p>
            <GroupedBars :categories="entityCategories" :series="series" :counts="countsOf('entity_types')" unit="entities" />
          </section>

          <section class="card">
            <h2 class="card-title">Connectivity</h2>
            <p class="card-sub">Share of entities by number of links</p>
            <GroupedBars :categories="degreeCategories" :series="series" :counts="countsOf('degree_distribution')" unit="entities" />
          </section>

          <section class="card">
            <h2 class="card-title">Agreement between models</h2>
            <p class="card-sub">Distinct triples extracted by both models (diagonal: the model's own total)</p>
            <div class="table-wrap">
              <table class="overlap">
                <thead>
                  <tr>
                    <th scope="col"></th>
                    <th v-for="s in series" :key="s.id" scope="col">{{ s.label }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="a in series" :key="a.id">
                    <th scope="row"><span class="swatch" :style="{ background: a.color }" />{{ a.label }}</th>
                    <td v-for="b in series" :key="b.id" :class="{ diag: a.id === b.id }">
                      {{ data.overlap[a.id]![b.id]!.toLocaleString() }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p class="stat">
              <strong>{{ data.common_to_all.toLocaleString() }}</strong>
              <span class="muted">triples were extracted by all three models</span>
            </p>
          </section>
        </div>

        <section class="card">
          <h2 class="card-title">Most connected entities</h2>
          <div class="tops">
            <div v-for="s in series" :key="s.id">
              <h3><span class="swatch" :style="{ background: s.color }" />{{ s.label }}</h3>
              <ol>
                <li v-for="e in data.stats[s.id]!.top_entities" :key="e.name">
                  <span class="ent">{{ pretty(e.name) }}</span>
                  <span class="deg">{{ e.degree }}</span>
                </li>
              </ol>
            </div>
          </div>
        </section>
      </template>
    </main>
  </div>
</template>

<style scoped>
/* Categorical series slots (validated: CVD + contrast, light and dark) */
.eval {
  --series-1: #2a78d6;
  --series-2: #eb6834;
  --series-3: #1baf7a;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (prefers-color-scheme: dark) {
  .eval {
    --series-1: #3987e5;
    --series-2: #d95926;
    --series-3: #199e70;
  }
}

.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.page-head h1 {
  font-size: 24px;
}

.legend {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--text);
}

.legend-item {
  display: inline-flex;
  align-items: center;
}

.swatch {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  margin-right: 6px;
  vertical-align: baseline;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr));
  gap: 16px;
}

.table-wrap {
  overflow-x: auto;
}

table {
  border-collapse: collapse;
  width: 100%;
  font-size: 13.5px;
  font-variant-numeric: tabular-nums;
}

th,
td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  text-align: right;
  white-space: nowrap;
}

th[scope='row'] {
  text-align: left;
  font-weight: 600;
  color: var(--text);
  white-space: normal;
}

thead th {
  color: var(--text-muted);
  font-weight: 600;
}

.summary th[scope='row'] {
  min-width: 200px;
}

.row-hint {
  display: block;
  font-weight: 400;
  font-size: 12px;
  color: var(--text-muted);
}

td.top {
  font-weight: 700;
  color: var(--heading);
}

.overlap td.diag {
  color: var(--text-muted);
}

.note {
  margin-top: 10px;
}

.card > .card-title + .card-sub {
  margin-top: 2px;
}

.stat {
  margin-top: 14px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.stat strong {
  font-size: 22px;
  color: var(--heading);
}

.tops {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 18px;
}

.tops h3 {
  font-size: 14px;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
}

.tops ol {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
}

.tops li {
  padding: 2px 0;
}

.tops li::marker {
  color: var(--text-muted);
}

.ent {
  color: var(--text);
}

.deg {
  float: right;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}
</style>
