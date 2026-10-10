<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue';
import 'vue-loading-overlay/dist/css/index.css';
import { useLoading } from 'vue-loading-overlay';
import axios from 'axios';
import { Network } from 'vis-network';
import { DataSet } from 'vis-data';
import AppSidebar from '@/components/AppSidebar.vue';
import { API_URL } from '@/config';
import {
  ONT_NS, ALL_STYLES, ENTITY_STYLES, localName, prettyLabel, entityKind, makeNode,
  type GraphNode,
} from '@/graph/palette';

/** One causal relation, whether stored reified (REL_ node) or as a direct triple. */
interface RelationRecord {
  id: string;            // relation URI (reified) or "subject|predicate|object" (legacy triple)
  reified: boolean;
  subject: string;
  subjectType: string | null;
  predicate: string;
  object: string;
  objectType: string | null;
  publication: string | null;
}

/** What vis-network draws: one edge per relation. */
interface GraphEdge {
  id: string;
  from: string;
  to: string;
  label: string;         // predicate local name, drawn on the canvas
  title?: string;        // hover tooltip
  predicate: string;     // predicate URI
  relation: string | null;   // REL_... local name when reified
  publication: string | null;
}

interface Repository {
  id: string;
}

type GraphState = 'loading' | 'ready' | 'empty' | 'error';
type ApiStatus = 'unknown' | 'ok' | 'down';

const RDF_TYPE = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type';
const CAUSAL_PREDICATES = ['cause', 'affect', 'prevent', 'aggravate', 'diagnose', 'improve', 'present', 'progression', 'test', 'treat'];
const TYPE_FILTER = (v: string) =>
  `OPTIONAL { ?${v} a ?${v}Type . FILTER(STRSTARTS(STR(?${v}Type), "${ONT_NS}") && ?${v}Type != <${ONT_NS}Entity>) }`;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const abstract = ref('');
const responseText = ref('');
const statusText = ref('');
const statusKind = ref<'info' | 'success' | 'error'>('info');
const validationError = ref('');
const searchValidationError = ref('');
const repositories = ref<Repository[]>([]);
const currentRepoId = ref('amd_repo_mistral');
const queryText = ref('');
const filterType = ref('');
const results = ref<RelationRecord[]>([]);
const selectedResultIndex = ref<number | null>(null);
const selectedEdge = ref<GraphEdge | null>(null);
const graphState = ref<GraphState>('loading');
const graphError = ref('');
const apiStatus = ref<ApiStatus>('unknown');
const readOnly = ref(false);
const nodeStates = ref<Record<string, string>>({});
const legendKinds = ref<string[]>([]);

const abstractFile = ref<File | null>(null);
const relationsFile = ref<File | Blob | null>(null);
const selectedModel = ref<string>('');
const abstractDownloadLink = ref<string | null>(null);
const relationsFileReady = ref(false);
const uploadStatus = ref<string | null>(null);

const $loading = useLoading();
let statusTimeout: number | null = null;
const graphContainer = ref<HTMLElement | null>(null);
let network: Network | null = null;
const nodes = ref<DataSet<any> | null>(null);
const edges = ref<DataSet<GraphEdge> | null>(null);
const expandedData = ref<Record<string, { nodes: string[]; edges: string[] }>>({});

const selectedRelationText = computed(() => {
  const e = selectedEdge.value;
  if (!e) return '';
  const src = e.publication ? `  ·  source: ${localName(e.publication)}` : '';
  return `${prettyLabel(localName(e.from))}  →  ${e.label}  →  ${prettyLabel(localName(e.to))}${src}`;
});

const legendItems = computed(() =>
  legendKinds.value.map((k) => ({ kind: k, ...ALL_STYLES[k] })),
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function setStatus(text: string, kind: 'info' | 'success' | 'error' = 'info') {
  statusText.value = text;
  statusKind.value = kind;
  if (statusTimeout) clearTimeout(statusTimeout);
  statusTimeout = window.setTimeout(() => { statusText.value = ''; }, 5000);
}

/** Read-only SPARQL through the API proxy (the browser never calls GraphDB directly). */
function sparqlGet(repoId: string, query: string) {
  return axios.post(`${API_URL}/api/sparql`, { repo_id: repoId, query }, { timeout: 60000 });
}

function describeAxiosError(error: any): string {
  if (error?.response?.data?.error) return String(error.response.data.error);
  if (error?.response) return `The API answered ${error.response.status} for repository "${currentRepoId.value}".`;
  return `No answer from the API at ${API_URL}.`;
}

/** SPARQL JSON bindings -> relation records (both schemas). */
function recordsFromBindings(bindings: any[]): RelationRecord[] {
  const out: RelationRecord[] = [];
  const seen = new Set<string>();
  for (const b of bindings) {
    const subject = b.subject?.value;
    const predicate = b.predicate?.value;
    const object = b.object?.value;
    if (!subject || !predicate || !object) continue;
    if (predicate === RDF_TYPE) continue;
    const relation = b.relation?.value as string | undefined;
    const id = relation ?? `${subject}|${predicate}|${object}`;
    if (seen.has(id)) continue; // several rdf:type rows per entity collapse into one
    seen.add(id);
    out.push({
      id,
      reified: !!relation,
      subject,
      subjectType: b.subjectType?.value ?? null,
      predicate,
      object,
      objectType: b.objectType?.value ?? null,
      publication: b.publication?.value ?? null,
    });
  }
  return out;
}

function edgeFromRecord(r: RelationRecord): GraphEdge {
  const label = localName(r.predicate);
  const source = r.publication ? ` · source: ${localName(r.publication)}` : '';
  return {
    id: r.id,
    from: r.subject,
    to: r.object,
    label,
    title: `${prettyLabel(localName(r.subject))} ${label} ${prettyLabel(localName(r.object))}${source}`,
    predicate: r.predicate,
    relation: r.reified ? localName(r.id) : null,
    publication: r.publication,
  };
}

// ---------------------------------------------------------------------------
// Startup
// ---------------------------------------------------------------------------
onMounted(() => {
  checkApi();
  fetchRepositories();
  fetchData();
});

async function checkApi() {
  try {
    const { data } = await axios.get(`${API_URL}/api/health`, { timeout: 8000 });
    apiStatus.value = 'ok';
    readOnly.value = !!data?.read_only;
  } catch {
    apiStatus.value = 'down';
  }
}

async function fetchRepositories() {
  try {
    const response = await axios.get<Repository[]>(`${API_URL}/api/available_repositories`, { timeout: 8000 });
    repositories.value = response.data;
    if (repositories.value.length && !repositories.value.some((r) => r.id === currentRepoId.value)) {
      // Prefer an AMD repository when GraphDB also hosts other projects
      const preferred = repositories.value.find((r) => /amd/i.test(r.id)) ?? repositories.value[0]!;
      currentRepoId.value = preferred.id;
      fetchData();
    }
  } catch (error) {
    console.error('Error fetching repositories:', error);
  }
}

function activateRepository(repoId: string) {
  if (repoId === currentRepoId.value) return;
  currentRepoId.value = repoId;
  results.value = [];
  selectedResultIndex.value = null;
  deselectEdge();
  fetchData();
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------
/** Relations around one entity (reified + legacy triples), both directions. */
function neighbourhoodQuery(entityUri: string, limit: number) {
  const preds = CAUSAL_PREDICATES.map((p) => `c:${p}`).join(', ');
  return `
    PREFIX c: <${ONT_NS}>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    SELECT ?relation ?subject ?predicate ?object ?publication ?subjectType ?objectType WHERE {
      {
        ?relation a c:RELATION ;
                  c:relation_subject ?subject ;
                  c:relation_predicate ?predicate ;
                  c:relation_object ?object .
        FILTER(?subject = <${entityUri}> || ?object = <${entityUri}>)
        OPTIONAL { ?relation prov:wasDerivedFrom ?publication }
      }
      UNION
      {
        ?subject ?predicate ?object .
        FILTER(?subject = <${entityUri}> || ?object = <${entityUri}>)
        FILTER(?predicate IN (${preds}))
        OPTIONAL { ?subject prov:wasDerivedFrom ?publication }
      }
      ${TYPE_FILTER('subject')}
      ${TYPE_FILTER('object')}
    }
    LIMIT ${limit}
  `.replace(/\s+/g, ' ');
}

// ---------------------------------------------------------------------------
// Default graph (neighbourhood of the AMD node)
// ---------------------------------------------------------------------------
async function fetchData() {
  graphState.value = 'loading';
  graphError.value = '';
  try {
    const response = await sparqlGet(currentRepoId.value, neighbourhoodQuery(`${ONT_NS}age_related_macular_degeneration`, 15));
    const records = recordsFromBindings(response.data?.results?.bindings ?? []);
    if (!records.length) {
      clearGraph();
      graphState.value = 'empty';
      return;
    }
    nextTick(() => drawRecords(records, true));
    graphState.value = 'ready';
  } catch (error: any) {
    console.error('Error fetching data:', error);
    clearGraph();
    graphState.value = 'error';
    graphError.value = describeAxiosError(error);
  }
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function ensureDataSets() {
  if (!nodes.value) nodes.value = new DataSet();
  if (!edges.value) edges.value = new DataSet();
}

function updateLegend() {
  const kinds = new Set<string>();
  nodes.value?.forEach((n: any) => kinds.add(n.kind ?? 'ENTITY'));
  const order = [...Object.keys(ENTITY_STYLES), 'ENTITY'];
  legendKinds.value = order.filter((k) => kinds.has(k));
}

/** Add the records' entities and edges to the canvas; `replace` clears it first. */
function drawRecords(records: RelationRecord[], replace: boolean, origin: string | null = null): { nodes: string[]; edges: string[] } {
  ensureDataSets();
  // Spawn new nodes next to the node that was expanded, so they grow out of it
  const spawn = origin && network ? network.getPositions([origin])[origin] : undefined;
  if (replace) {
    nodes.value!.clear();
    edges.value!.clear();
    nodeStates.value = {};
    expandedData.value = {};
    fitOnSettle = true;
  }
  const added = { nodes: [] as string[], edges: [] as string[] };
  const newNodes: GraphNode[] = [];
  const newEdges: GraphEdge[] = [];
  for (const r of records) {
    for (const [uri, type] of [[r.subject, r.subjectType], [r.object, r.objectType]] as const) {
      if (nodes.value!.get(uri) || newNodes.some((n) => n.id === uri)) continue;
      const node: any = makeNode(uri, entityKind(type));
      if (spawn) {
        node.x = spawn.x;
        node.y = spawn.y;
      }
      newNodes.push(node);
      added.nodes.push(uri);
      nodeStates.value[uri] = 'collapsed';
    }
    if (edges.value!.get(r.id) || newEdges.some((e) => e.id === r.id)) continue;
    newEdges.push(edgeFromRecord(r));
    added.edges.push(r.id);
  }
  nodes.value!.add(newNodes);
  edges.value!.add(newEdges);
  updateLegend();
  const first = !network;
  mountNetwork();
  if (!first && origin && added.nodes.length) placeAroundNode(origin, added.nodes);
  return added;
}

function mountNetwork() {
  if (!graphContainer.value || !nodes.value || !edges.value) return;
  if (network) return;
  const options = {
    nodes: {
      shape: 'ellipse',
      borderWidth: 2,
      margin: { top: 6, right: 10, bottom: 6, left: 10 },
      shadow: { enabled: true, color: 'rgba(15,23,42,0.15)', size: 6, x: 0, y: 2 },
      font: { size: 15, face: 'Helvetica, Arial, sans-serif', color: '#1f2937' },
    },
    edges: {
      arrows: { to: { enabled: true, scaleFactor: 0.7 } },
      smooth: { enabled: true, type: 'continuous', roundness: 0.25 },
      font: { size: 12, align: 'horizontal', color: '#475569', strokeWidth: 4, strokeColor: '#ffffff' },
      color: { color: '#94a3b8', highlight: '#2563eb', hover: '#2563eb' },
      selectionWidth: 2,
      width: 1.6,
    },
    physics: {
      solver: 'barnesHut',
      barnesHut: { gravitationalConstant: -6000, centralGravity: 0.15, springLength: 190, springConstant: 0.03, damping: 0.5, avoidOverlap: 0.6 },
      stabilization: { iterations: 300, updateInterval: 25, fit: false },
    },
    interaction: { hover: true, tooltipDelay: 150, zoomSpeed: 0.6 },
    layout: { improvedLayout: true },
  };
  network = new Network(graphContainer.value, { nodes: nodes.value, edges: edges.value }, options as any);
  if (import.meta.env.DEV) {
    // Dev-only hook so the graph can be driven from the console / automated tests
    (window as any).__kg = { network, toggleNode, fitGraph, nodes: nodes.value, edges: edges.value };
  }
  network.on('hoverNode', (params: any) => focusNeighbourhood(params.node));
  network.on('blurNode', () => focusNeighbourhood(null));
  network.on('dragStart', () => focusNeighbourhood(null));
  network.on('click', async (params: any) => {
    if (params.nodes.length > 0) {
      focusNeighbourhood(null);
      await toggleNode(params.nodes[0]);
    } else if (params.edges.length > 0) {
      selectEdge(params.edges[0]);
    } else {
      deselectEdge();
    }
  });
  // Physics only runs until the layout settles; otherwise the graph drifts forever.
  // The view is re-fitted only when the canvas was redrawn from scratch, so the
  // user's zoom and pan survive expanding or collapsing a node.
  network.on('stabilized', () => {
    network?.setOptions({ physics: { enabled: false } });
    if (fitOnSettle) {
      fitOnSettle = false;
      network?.fit({ animation: false });
    }
  });
}

let fitOnSettle = true;

/** Place freshly added nodes on an arc around `origin`, opening away from the
 *  side where its existing neighbours sit. Purely geometric: nothing else moves. */
function placeAroundNode(origin: string, freshIds: string[]) {
  if (!network || !nodes.value || !freshIds.length) return;
  const pos = network.getPositions();
  const o = pos[origin];
  if (!o) return;
  const fresh = new Set(freshIds);
  const neighbours = (network.getConnectedNodes(origin) as string[]).filter((id) => !fresh.has(id) && pos[id]);
  // Outward direction = opposite of the centroid of existing neighbours
  let dx = 0, dy = 0;
  for (const id of neighbours) { dx += pos[id]!.x - o.x; dy += pos[id]!.y - o.y; }
  const base = neighbours.length ? Math.atan2(-dy, -dx) : -Math.PI / 2;
  const n = freshIds.length;
  const span = n === 1 ? 0 : Math.min(Math.PI * 1.5, Math.max(Math.PI * 0.6, n * 0.35));
  // Chord between neighbouring fresh nodes ~150px so labels do not collide
  const radius = n === 1 ? 200 : Math.max(220, (190 * (n - 1)) / span);
  const sorted = [...freshIds].sort((a, b) => String(nodes.value!.get(a)?.label ?? a).localeCompare(String(nodes.value!.get(b)?.label ?? b)));
  // Approximate half-width of a node from its label (canvas units at scale 1)
  const halfWidth = (id: string) => (String(nodes.value!.get(id)?.label ?? '').length * 7.6 + 30) / 2;
  const taken = Object.entries(pos).filter(([id]) => !fresh.has(id)).map(([id, p]) => ({ x: p.x, y: p.y, hw: halfWidth(id) }));
  const placed: { x: number; y: number; hw: number }[] = [];
  const updates = sorted.map((id, i) => {
    const angle = base - span / 2 + (n === 1 ? 0 : (span * i) / (n - 1));
    const hw = halfWidth(id);
    let r = radius;
    let x = 0, y = 0;
    // Nudge outwards while overlapping anything already on the canvas
    for (let attempt = 0; attempt < 5; attempt++) {
      x = o.x + Math.cos(angle) * r;
      y = o.y + Math.sin(angle) * r;
      const clash = [...taken, ...placed].some((q) => Math.abs(q.x - x) < q.hw + hw + 16 && Math.abs(q.y - y) < 46);
      if (!clash) break;
      r += 60;
    }
    placed.push({ x, y, hw });
    return { id, x, y, fixed: { x: false, y: false } };
  });
  nodes.value.update(updates);
  panIntoView([origin, ...freshIds]);
}

/** Pan (never zoom) so that the given nodes are visible, if they are not already. */
function panIntoView(ids: string[]) {
  if (!network || !graphContainer.value) return;
  const pos = network.getPositions(ids);
  const pts = ids.map((id) => pos[id]).filter(Boolean) as { x: number; y: number }[];
  if (!pts.length) return;
  const { clientWidth: w, clientHeight: h } = graphContainer.value;
  const margin = 40;
  const outside = pts.some((p) => {
    const d = network!.canvasToDOM(p);
    return d.x < margin || d.y < margin || d.x > w - margin || d.y > h - margin;
  });
  if (!outside) return;
  const cx = pts.reduce((a, p) => a + p.x, 0) / pts.length;
  const cy = pts.reduce((a, p) => a + p.y, 0) / pts.length;
  network.moveTo({ position: { x: cx, y: cy }, scale: network.getScale(), animation: { duration: 350, easingFunction: 'easeInOutQuad' } });
}

/** Highlight a node's neighbourhood on hover; restore on blur. */
function focusNeighbourhood(nodeId: string | null) {
  if (!nodes.value || !edges.value || !network) return;
  if (nodeId === null) {
    nodes.value.update(nodes.value.map((n: any) => ({ id: n.id, opacity: 1 })));
    edges.value.update(edges.value.map((e: any) => ({ id: e.id, color: { color: '#94a3b8', highlight: '#2563eb', hover: '#2563eb' }, font: { color: '#475569' } })));
    return;
  }
  const near = new Set<string>([nodeId, ...(network.getConnectedNodes(nodeId) as string[])]);
  nodes.value.update(nodes.value.map((n: any) => ({ id: n.id, opacity: near.has(n.id) ? 1 : 0.18 })));
  edges.value.update(edges.value.map((e: any) => {
    const on = e.from === nodeId || e.to === nodeId;
    return { id: e.id, color: on ? { color: '#2563eb', highlight: '#2563eb', hover: '#2563eb' } : { color: 'rgba(148,163,184,0.25)', highlight: '#2563eb', hover: '#2563eb' }, font: { color: on ? '#1d4ed8' : 'rgba(71,85,105,0.3)' } };
  }));
}

function fitGraph() {
  network?.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
}

function selectEdge(edgeId: string) {
  const edge = edges.value?.get(edgeId);
  if (edge) selectedEdge.value = edge;
}

function deselectEdge() {
  selectedEdge.value = null;
  network?.unselectAll();
}

function clearGraph() {
  nodes.value?.clear();
  edges.value?.clear();
  nodeStates.value = {};
  expandedData.value = {};
  legendKinds.value = [];
}

// ---------------------------------------------------------------------------
// Node expansion / collapse
// ---------------------------------------------------------------------------
async function toggleNode(nodeId: string) {
  if (nodeStates.value[nodeId] === 'expanded') {
    collapseNode(nodeId);
    nodeStates.value[nodeId] = 'collapsed';
  } else {
    await expandNode(nodeId);
    nodeStates.value[nodeId] = 'expanded';
  }
}

const expanding = ref(false);

async function expandNode(nodeId: string) {
  if (expandedData.value[nodeId]) return; // already on the canvas
  expanding.value = true;
  try {
    const response = await sparqlGet(currentRepoId.value, neighbourhoodQuery(nodeId, 60));
    const records = recordsFromBindings(response.data?.results?.bindings ?? []);
    const added = drawRecords(records, false, nodeId);
    expandedData.value[nodeId] = added;
    if (!added.edges.length) setStatus('No further relations for this node.', 'info');
  } catch (error) {
    console.error('Error expanding node:', error);
    setStatus('Could not load the neighbours of this node.', 'error');
  } finally {
    expanding.value = false;
  }
}

function collapseNode(nodeId: string) {
  const memory = expandedData.value[nodeId];
  if (!memory || !nodes.value || !edges.value) return;
  edges.value.remove(memory.edges);
  nodes.value.remove(memory.nodes);
  for (const n of memory.nodes) delete nodeStates.value[n];
  delete expandedData.value[nodeId];
  updateLegend();
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------
function performSearch() {
  if (!queryText.value.trim()) {
    searchValidationError.value = 'Please enter a search term.';
    return;
  }
  searchValidationError.value = '';
  selectedResultIndex.value = null;
  const loader = $loading.show();

  const params = new URLSearchParams();
  params.append('q', queryText.value);
  if (filterType.value) params.append('type', filterType.value);
  params.append('repo_id', currentRepoId.value);

  fetch(`${API_URL}/api/search?${params.toString()}`)
    .then((response) => {
      if (!response.ok) throw new Error(`API answered ${response.status}`);
      return response.json();
    })
    .then((data: any[]) => {
      results.value = data.map((r) => ({
        id: r.relation,
        reified: true,
        subject: r.subject,
        subjectType: r.subjectType ?? null,
        predicate: r.predicate,
        object: r.object,
        objectType: r.objectType ?? null,
        publication: r.publicationId || null,
      }));
      if (!results.value.length) {
        setStatus('No results found.', 'info');
        clearGraph();
        graphState.value = 'empty';
      } else {
        setStatus(`${results.value.length} relation(s) found.`, 'success');
        drawRecords(results.value, true);
        graphState.value = 'ready';
      }
    })
    .catch((error) => {
      console.error('Error during search:', error);
      setStatus('Search failed. Is the backend API running?', 'error');
    })
    .finally(() => loader.hide());
}

function clearSearch() {
  queryText.value = '';
  filterType.value = '';
  results.value = [];
  selectedResultIndex.value = null;
  searchValidationError.value = '';
  deselectEdge();
  fetchData();
}

/** Show a single search result on the canvas and highlight the row. */
function selectRelation(result: RelationRecord, index: number) {
  selectedResultIndex.value = index;
  deselectEdge();
  drawRecords([result], true);
  graphState.value = 'ready';
  nextTick(() => selectEdge(result.id));
}

// ---------------------------------------------------------------------------
// Relation deletion
// ---------------------------------------------------------------------------
async function deleteSelectedEdge() {
  const edge = selectedEdge.value;
  if (!edge) {
    setStatus('Select an edge in the graph first.', 'info');
    return;
  }
  if (!window.confirm(`Delete this relation from "${currentRepoId.value}"?\n\n${selectedRelationText.value}`)) return;

  const payload = {
    subject: localName(edge.from),
    predicate: localName(edge.predicate),
    object: localName(edge.to),
    relation: edge.relation,
    repo_id: currentRepoId.value,
  };
  const loader = $loading.show();
  try {
    const response = await axios.post(`${API_URL}/api/deleteRelation`, payload, { headers: { 'Content-Type': 'application/json' } });
    if (response.status === 200) {
      edges.value?.remove(edge.id);
      results.value = results.value.filter((r) => r.id !== edge.id);
      deselectEdge();
      setStatus('Relation deleted.', 'success');
    } else {
      setStatus('Failed to delete relation.', 'error');
    }
  } catch (error: any) {
    console.error('Error deleting relation:', error);
    setStatus(error?.response?.data?.error || 'Error deleting relation.', 'error');
  } finally {
    loader.hide();
  }
}

function refreshGraph() {
  if (queryText.value.trim()) {
    performSearch();
  } else {
    fetchData().then(() => {
      if (graphState.value === 'ready') setStatus('Default graph loaded.', 'success');
    });
  }
}

// ---------------------------------------------------------------------------
// Relation extraction from a pasted abstract (GPT-4o-mini via the API)
// ---------------------------------------------------------------------------
function validateAbstract() {
  if (!abstract.value.trim()) {
    validationError.value = 'Abstract cannot be empty.';
    return false;
  }
  return true;
}

function validateRelations() {
  try {
    JSON.parse(responseText.value);
  } catch {
    validationError.value = 'Relations must be valid JSON.';
    return false;
  }
  return true;
}

function showRelations() {
  if (!validateAbstract()) return;
  validationError.value = '';
  const loader = $loading.show();
  fetch(`${API_URL}/api/showRelations`, {
    method: 'POST',
    body: JSON.stringify(abstract.value),
    headers: { 'Content-Type': 'application/json' },
  })
    .then((response) => {
      if (!response.ok) throw new Error(`API answered ${response.status}`);
      return response.json();
    })
    .then((response) => {
      responseText.value = JSON.stringify(response, null, 2);
      setStatus('Relations extracted. Review them, then click "Add to graph".', 'success');
    })
    .catch(() => setStatus('Error extracting relations. Check the API and the OPENAI_API_KEY.', 'error'))
    .finally(() => loader.hide());
}

function addRelations() {
  if (!validateRelations()) return;
  validationError.value = '';
  const loader = $loading.show();
  const payload = { repo_id: currentRepoId.value, relations: JSON.parse(responseText.value) };
  fetch(`${API_URL}/api/addRelations`, {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'Content-Type': 'application/json' },
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.status === 'Successfully completed') {
        setStatus('Relations added to the knowledge graph.', 'success');
        fetchData();
      } else {
        setStatus(data.error || 'There was an issue adding relations.', 'error');
      }
    })
    .catch(() => setStatus('Error adding relations.', 'error'))
    .finally(() => loader.hide());
}

function reasonKg() {
  validationError.value = '';
  const loader = $loading.show();
  const params = new URLSearchParams({ repo_id: currentRepoId.value });
  fetch(`${API_URL}/api/reason?${params.toString()}`)
    .then((response) => response.json())
    .then((data) => {
      if (data.status === 'Successfully completed') {
        setStatus('Reasoning completed; inferred triples were added.', 'success');
        fetchData();
      } else {
        setStatus(data.error || 'There was an issue running the reasoner.', 'error');
      }
    })
    .catch(() => setStatus('Error running the reasoner.', 'error'))
    .finally(() => loader.hide());
}

// ---------------------------------------------------------------------------
// Batch extraction from a file + bulk upload
// ---------------------------------------------------------------------------
function handleAbstractUpload(event: Event) {
  abstractFile.value = (event.target as HTMLInputElement).files?.[0] ?? null;
}

function handleRelationsUpload(event: Event) {
  relationsFile.value = (event.target as HTMLInputElement).files?.[0] ?? null;
  relationsFileReady.value = !!relationsFile.value;
}

async function uploadAbstractFile() {
  if (!abstractFile.value || !selectedModel.value) return;
  const loader = $loading.show();
  const formData = new FormData();
  formData.append('file', abstractFile.value);
  formData.append('model', selectedModel.value);
  uploadStatus.value = null;
  try {
    const response = await axios.post(`${API_URL}/api/upload_abstract`, formData, { responseType: 'blob' });
    const extractedFile = new Blob([response.data], { type: 'application/json' });
    abstractDownloadLink.value = URL.createObjectURL(extractedFile);
    relationsFile.value = extractedFile;
    relationsFileReady.value = true;
    uploadStatus.value = 'Extraction finished. Download the file to review it, or add it to the graph directly.';
  } catch (error) {
    console.error('Error extracting relations from abstract:', error);
    uploadStatus.value = 'Extraction failed. Check the API logs and the provider key for the selected model.';
  } finally {
    loader.hide();
  }
}

async function addRelationsToKG() {
  if (!relationsFile.value || !currentRepoId.value) return;
  const loader = $loading.show();
  const formData = new FormData();
  formData.append('file', relationsFile.value);
  formData.append('repo_id', currentRepoId.value);
  try {
    const response = await axios.post(`${API_URL}/api/upload_relations`, formData);
    uploadStatus.value = response.data.status === 'Successfully completed'
      ? `Relations added to "${currentRepoId.value}".`
      : (response.data.error || 'Failed to add relations.');
    fetchData();
  } catch (error: any) {
    console.error('Error adding relations to KG:', error);
    uploadStatus.value = error?.response?.data?.error || 'Error adding relations to the knowledge graph.';
  } finally {
    loader.hide();
  }
}
</script>

<template>
  <div class="app-shell">
    <AppSidebar />

    <main class="page">
      <div v-if="apiStatus === 'down'" class="banner banner-warn">
        <span>
          ⚠️ The backend API is not reachable at <code>{{ API_URL }}</code>. If this is the public demo, the
          service is probably waking up: retry in a minute. Locally: <code>cd backend && flask run -p 5555</code>.
        </span>
        <button class="btn btn-secondary btn-sm" type="button" @click="checkApi">Retry</button>
      </div>

      <header class="page-head">
        <div>
          <h1>AMD Knowledge Graph</h1>
          <p class="muted">Causal relations extracted from AMD literature, stored in GraphDB.</p>
        </div>
        <div class="repos" v-if="repositories.length">
          <span class="muted">Repository</span>
          <button
            v-for="repo in repositories"
            :key="repo.id"
            type="button"
            class="pill"
            :class="{ active: repo.id === currentRepoId }"
            @click="activateRepository(repo.id)"
          >
            {{ repo.id }}
          </button>
        </div>
        <div v-else class="repos">
          <span class="muted">Repository <code class="inline">{{ currentRepoId }}</code></span>
        </div>
      </header>

      <div class="layout">
        <!-- ================= Graph ================= -->
        <section class="card graph-card">
          <div class="card-head">
            <h2 class="card-title">Graph</h2>
            <div class="btn-row">
              <span v-if="expanding" class="muted">Loading neighbours…</span>
              <button class="btn btn-secondary btn-sm" type="button" @click="fitGraph" :disabled="graphState !== 'ready'">Fit</button>
              <button class="btn btn-secondary btn-sm" type="button" @click="refreshGraph">Refresh</button>
            </div>
          </div>

          <div class="graph-wrap">
            <div ref="graphContainer" class="graph-canvas"></div>

            <div v-if="graphState === 'loading'" class="graph-overlay">
              <div class="spinner"></div>
              <p>Loading graph…</p>
            </div>
            <div v-else-if="graphState === 'error'" class="graph-overlay">
              <h3>Graph data is not available</h3>
              <p class="muted">{{ graphError }}</p>
              <p class="muted">
                The API may still be waking up (free hosting sleeps when idle; retry in a minute). Locally, make sure
                <code class="inline">flask run -p 5555</code> and GraphDB are running.
              </p>
              <button class="btn btn-primary btn-sm" type="button" @click="fetchData">Retry</button>
            </div>
            <div v-else-if="graphState === 'empty'" class="graph-overlay">
              <h3>Nothing to show</h3>
              <p class="muted">
                Repository <code class="inline">{{ currentRepoId }}</code> has no relations around the AMD node
                (or the search returned nothing). Import <code class="inline">data/amd_repo.rdf</code> in GraphDB
                or add relations from the panel on the right.
              </p>
              <button class="btn btn-secondary btn-sm" type="button" @click="fetchData">Reload</button>
            </div>
          </div>

          <div class="graph-foot">
            <ul class="legend" v-if="legendItems.length">
              <li v-for="item in legendItems" :key="item.kind">
                <span class="swatch" :class="'swatch-' + item.shape" :style="{ background: item.color, borderColor: item.border }"></span>
                {{ item.label }}
              </li>
            </ul>
            <p class="muted hint">One arrow per relation, labelled with its type · click a node to expand or collapse its neighbours · click an arrow to select it · scroll to zoom.</p>
          </div>

          <div v-if="selectedEdge" class="selection">
            <span class="selection-text">{{ selectedRelationText }}</span>
            <div class="btn-row">
              <button class="btn btn-secondary btn-sm" type="button" @click="deselectEdge">Clear</button>
              <button v-if="!readOnly" class="btn btn-danger btn-sm" type="button" @click="deleteSelectedEdge">Delete relation</button>
            </div>
          </div>

          <div v-if="statusText" class="msg" :class="'msg-' + statusKind">{{ statusText }}</div>
        </section>

        <!-- ================= Side panels ================= -->
        <aside class="side">
          <section class="card">
            <div class="card-head">
              <h2 class="card-title">Search</h2>
              <button v-if="results.length || queryText" class="btn btn-secondary btn-sm" type="button" @click="clearSearch">Clear</button>
            </div>
            <div class="search-row">
              <input
                v-model="queryText"
                type="search"
                class="input"
                placeholder="e.g. drusen, smoking"
                @keyup.enter="performSearch"
              />
              <select v-model="filterType" class="select select-narrow" aria-label="Filter by">
                <option value="">Any field</option>
                <option value="node">Subject</option>
                <option value="relation">Relation type</option>
                <option value="entity">Object</option>
              </select>
              <button class="btn btn-primary" type="button" @click="performSearch" :disabled="apiStatus === 'down'">Search</button>
            </div>
            <p v-if="searchValidationError" class="msg msg-error">{{ searchValidationError }}</p>

            <div v-if="results.length" class="results">
              <table class="results-table">
                <thead>
                  <tr>
                    <th>Subject</th>
                    <th>Relation</th>
                    <th>Object</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(result, index) in results"
                    :key="result.id + index"
                    :class="{ selected: index === selectedResultIndex }"
                    @click="selectRelation(result, index)"
                  >
                    <td>{{ prettyLabel(localName(result.subject)) }}</td>
                    <td><span class="tag">{{ localName(result.predicate) }}</span></td>
                    <td>{{ prettyLabel(localName(result.object)) }}</td>
                    <td class="muted">{{ result.publication ? localName(result.publication) : '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section v-if="readOnly" class="card">
            <div class="card-head">
              <h2 class="card-title">Read-only demo</h2>
            </div>
            <p class="muted">
              This public instance lets you browse and search the graph. Extracting relations from new
              abstracts, editing the graph and running the reasoner need API keys and GraphDB, so they are
              available in the local setup described in the
              <a href="https://github.com/AlexLecu/LLMKGraph#-quick-start" target="_blank" rel="noopener">README</a>.
            </p>
          </section>

          <section v-if="!readOnly" class="card">
            <div class="card-head">
              <h2 class="card-title">Extract from an abstract</h2>
            </div>
            <p class="card-sub">Paste an abstract; relations are extracted with GPT-4o-mini and can be edited before they are added to the graph.</p>
            <div class="field">
              <textarea v-model="abstract" class="textarea" rows="5" placeholder="Paste an AMD abstract here…"></textarea>
            </div>
            <div class="btn-row">
              <button class="btn btn-primary" type="button" @click="showRelations" :disabled="apiStatus === 'down'">Extract relations</button>
              <button class="btn btn-secondary" type="button" @click="addRelations" :disabled="!responseText || apiStatus === 'down'">Add to graph</button>
              <button class="btn btn-secondary" type="button" @click="reasonKg" :disabled="apiStatus === 'down'" title="Run the HermiT reasoner on the current repository">Run reasoner</button>
            </div>
            <p v-if="validationError" class="msg msg-error">{{ validationError }}</p>
            <div class="field" style="margin-top: 12px">
              <label for="response-text">Extracted relations (JSON, editable)</label>
              <textarea v-model="responseText" id="response-text" class="textarea textarea-mono" rows="7" placeholder="[ { &quot;entity1_name&quot;: …, &quot;relation_type&quot;: …, &quot;entity2_name&quot;: … } ]"></textarea>
            </div>
          </section>

          <section v-if="!readOnly" class="card">
            <div class="card-head">
              <h2 class="card-title">Batch extraction &amp; upload</h2>
            </div>
            <p class="card-sub">Extract relations from a JSON file of abstracts with the model of your choice, then load the result into the selected repository. Provider keys come from <code class="inline">.env</code>.</p>
            <div class="field">
              <label for="modelSelect">Extraction model</label>
              <select v-model="selectedModel" id="modelSelect" class="select">
                <option value="" disabled>Select a model</option>
                <option value="model_a">GPT-3.5 Turbo (fine-tuned)</option>
                <option value="model_b">Mistral Nemo (fine-tuned)</option>
                <option value="model_c">GPT-4o-mini</option>
                <option value="model_d">DeepSeek V3 (deepseek-chat)</option>
              </select>
            </div>
            <div class="field">
              <label for="abstractFile">Abstracts file (JSON)</label>
              <input type="file" id="abstractFile" accept=".json,application/json" class="file-input" @change="handleAbstractUpload" />
            </div>
            <div class="btn-row">
              <button class="btn btn-primary" type="button" @click="uploadAbstractFile" :disabled="!abstractFile || !selectedModel || apiStatus === 'down'">Extract relations</button>
              <a v-if="abstractDownloadLink" :href="abstractDownloadLink" download="extracted_relations.json" class="btn btn-secondary">Download result</a>
            </div>

            <div class="field" style="margin-top: 14px">
              <label for="relationsFile">Relations file (JSON) — extracted above or your own</label>
              <input type="file" id="relationsFile" accept=".json,application/json" class="file-input" @change="handleRelationsUpload" />
            </div>
            <div class="btn-row">
              <button class="btn btn-primary" type="button" @click="addRelationsToKG" :disabled="!relationsFile || apiStatus === 'down'">Add relations to graph</button>
              <span v-if="relationsFileReady" class="muted">File ready for upload.</span>
            </div>
            <p v-if="uploadStatus" class="msg msg-info">{{ uploadStatus }}</p>
          </section>
        </aside>
      </div>
    </main>
  </div>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}

.page-head h1 {
  font-size: 24px;
}

.repos {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.pill {
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid var(--border-strong);
  background: var(--surface);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.pill.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

@media (min-width: 1100px) {
  .layout {
    grid-template-columns: minmax(0, 1.7fr) minmax(360px, 1fr);
  }

  .graph-card {
    position: sticky;
    top: 24px;
  }
}

.side {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-width: 0;
}

/* ---- Graph card ---- */
.graph-wrap {
  position: relative;
  height: 560px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: #fff;
  overflow: hidden;
}

@media (max-width: 1099px) {
  .graph-wrap {
    height: 440px;
  }
}

.graph-canvas {
  width: 100%;
  height: 100%;
}

.graph-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  text-align: center;
  background: rgba(255, 255, 255, 0.92);
}

/* The overlay sits on the white canvas, so its text stays dark in both themes */
.graph-overlay h3 {
  font-size: 17px;
  color: #0f172a;
}

.graph-overlay p {
  max-width: 460px;
  color: #475569;
}

.graph-overlay code.inline {
  background: #f1f5f9;
  border-color: #e2e8f0;
  color: #0f172a;
}

.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.graph-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.legend {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  font-size: 12.5px;
}

.legend li {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.swatch {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid;
  border-radius: 50%;
}

.swatch-box {
  border-radius: 2px;
}

.swatch-square {
  border-radius: 0;
}

.swatch-diamond {
  border-radius: 2px;
  transform: rotate(45deg) scale(0.85);
}

.hint {
  font-size: 12.5px;
}

.selection {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid var(--primary);
  border-radius: var(--radius-sm);
  background: var(--primary-soft);
}

.selection-text {
  font-family: var(--font-mono);
  font-size: 12.5px;
  word-break: break-word;
}

/* ---- Search ---- */
.search-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 8px;
}

.select-narrow {
  width: auto;
}

@media (max-width: 480px) {
  .search-row {
    grid-template-columns: 1fr;
  }
}

.results {
  margin-top: 12px;
  max-height: 320px;
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.results-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.results-table th,
.results-table td {
  padding: 7px 10px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}

.results-table th {
  position: sticky;
  top: 0;
  background: var(--surface-muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

.results-table tbody tr {
  cursor: pointer;
}

.results-table tbody tr:hover {
  background: var(--surface-muted);
}

.results-table tbody tr.selected {
  background: var(--primary-soft);
}

.tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 999px;
  background: #ede9fe;
  color: #6d28d9;
  font-size: 12px;
  font-weight: 600;
}
</style>
