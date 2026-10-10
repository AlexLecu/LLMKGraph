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

interface Edge {
  id?: string;
  from: string;
  to: string;
  /** Short label drawn on the canvas. */
  label: string;
  /** Original predicate local name (relation_subject, cause, …), used by the API. */
  rel: string;
  predicate: string;
}

const EDGE_LABELS: Record<string, string> = {
  relation_subject: 'subject',
  relation_predicate: 'type',
  relation_object: 'object',
  wasDerivedFrom: 'source',
};

function makeEdge(from: string, to: string, rel: string, predicate: string): Edge {
  return { from, to, rel, predicate, label: EDGE_LABELS[rel] ?? prettyLabel(rel) };
}

interface Repository {
  id: string;
}

interface SearchResult {
  relation: string;
  subject: string;
  predicate: string;
  object: string;
  publication: string;
  subjectType: string | null;
  objectType: string | null;
}

type GraphState = 'loading' | 'ready' | 'empty' | 'error';
type ApiStatus = 'unknown' | 'ok' | 'down';

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
const results = ref<SearchResult[]>([]);
const selectedResultIndex = ref<number | null>(null);
const selectedEdge = ref<Edge | null>(null);
const graphState = ref<GraphState>('loading');
const graphError = ref('');
const apiStatus = ref<ApiStatus>('unknown');
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
const edges = ref<DataSet<Edge> | null>(null);
const expandedData = ref<Record<string, { nodes: any[]; edges: any[] }>>({});

const selectedRelationText = computed(() => {
  const e = selectedEdge.value;
  if (!e) return '';
  const target = e.rel === 'relation_predicate' ? e.predicate : e.to;
  return `${prettyLabel(localName(e.from))}  →  ${e.rel}  →  ${prettyLabel(localName(target))}`;
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
  clearStatusTextAfterDelay();
}

function clearStatusTextAfterDelay() {
  if (statusTimeout) clearTimeout(statusTimeout);
  statusTimeout = window.setTimeout(() => {
    statusText.value = '';
  }, 5000);
}

/** Read-only SPARQL through the API proxy (the browser never calls GraphDB directly). */
function sparqlGet(repoId: string, query: string) {
  return axios.post(`${API_URL}/api/sparql`, { repo_id: repoId, query }, { timeout: 60000 });
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
    await axios.get(`${API_URL}/api/health`, { timeout: 4000 });
    apiStatus.value = 'ok';
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
// Default graph (neighbourhood of the AMD node)
// ---------------------------------------------------------------------------
async function fetchData() {
  graphState.value = 'loading';
  graphError.value = '';
  const defaultQuery = `
    PREFIX c: <${ONT_NS}>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    SELECT ?relation ?subject ?predicate ?object ?publication ?subjectType ?objectType WHERE {
      {
        BIND(c:age_related_macular_degeneration AS ?subject)
        ?subject ?predicate ?object .
        FILTER(?predicate IN (c:cause, c:affect, c:prevent, c:aggravate,
                              c:diagnose, c:improve, c:present, c:progression,
                              c:test, c:treat))
        OPTIONAL { ?subject prov:wasDerivedFrom ?publication }
      }
      UNION
      {
        BIND(c:age_related_macular_degeneration AS ?subject)
        ?relation a c:RELATION ;
                  c:relation_subject ?subject ;
                  c:relation_predicate ?predicate ;
                  c:relation_object ?object .
        OPTIONAL { ?relation prov:wasDerivedFrom ?publication }
      }
      OPTIONAL { ?subject a ?subjectType . FILTER(STRSTARTS(STR(?subjectType), "${ONT_NS}") && ?subjectType != <${ONT_NS}Entity>) }
      OPTIONAL { ?object a ?objectType . FILTER(STRSTARTS(STR(?objectType), "${ONT_NS}") && ?objectType != <${ONT_NS}Entity>) }
    }
    LIMIT 10
  `.replace(/\s+/g, ' ');

  try {
    const response = await sparqlGet(currentRepoId.value, defaultQuery);
    const bindings = response.data?.results?.bindings ?? [];
    if (!bindings.length) {
      clearGraph();
      graphState.value = 'empty';
      return;
    }
    processData(response.data);
    graphState.value = 'ready';
  } catch (error: any) {
    console.error('Error fetching data:', error);
    clearGraph();
    graphState.value = 'error';
    graphError.value = describeAxiosError(error);
  }
}

function describeAxiosError(error: any): string {
  if (error?.response?.data?.error) return String(error.response.data.error);
  if (error?.response) return `The API answered ${error.response.status} for repository "${currentRepoId.value}".`;
  return `No answer from the API at ${API_URL}.`;
}

function processData(data: any) {
  const nodesArray: GraphNode[] = [];
  const edgesArray: Edge[] = [];
  const nodeIds = new Set<string>();

  const predicateURIs = {
    relation_subject: `${ONT_NS}relation_subject`,
    relation_predicate: `${ONT_NS}relation_predicate`,
    relation_object: `${ONT_NS}relation_object`,
    wasDerivedFrom: 'http://www.w3.org/ns/prov#wasDerivedFrom',
  };

  data.results.bindings.forEach((binding: any) => {
    const relation = binding.relation?.value;
    const subject = binding.subject?.value;
    const predicate = binding.predicate?.value;
    const object = binding.object?.value;
    const publication = binding.publication?.value;
    const subjectType = binding.subjectType?.value;
    const objectType = binding.objectType?.value;
    if (!subject || !predicate || !object) return;

    if (relation) {
      addNode(nodesArray, nodeIds, makeNode(relation, 'RELATION'));
      addNode(nodesArray, nodeIds, makeNode(subject, entityKind(subjectType)));
      addNode(nodesArray, nodeIds, makeNode(predicate, 'PREDICATE'));
      addNode(nodesArray, nodeIds, makeNode(object, entityKind(objectType)));
      edgesArray.push(makeEdge(relation, subject, 'relation_subject', predicateURIs.relation_subject));
      edgesArray.push(makeEdge(relation, predicate, 'relation_predicate', predicateURIs.relation_predicate));
      edgesArray.push(makeEdge(relation, object, 'relation_object', predicateURIs.relation_object));
      if (publication) {
        addNode(nodesArray, nodeIds, makeNode(publication, 'PUBLICATION'));
        edgesArray.push(makeEdge(relation, publication, 'wasDerivedFrom', predicateURIs.wasDerivedFrom));
      }
    } else {
      addNode(nodesArray, nodeIds, makeNode(subject, entityKind(subjectType)));
      addNode(nodesArray, nodeIds, makeNode(object, entityKind(objectType)));
      edgesArray.push(makeEdge(subject, object, localName(predicate), predicate));
    }
  });

  nextTick(() => renderGraph(nodesArray, edgesArray));
}

function addNode(nodesArray: GraphNode[], nodeIds: Set<string>, node: GraphNode) {
  if (nodeIds.has(node.id)) return;
  nodesArray.push(node);
  nodeIds.add(node.id);
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function updateLegend() {
  const kinds = new Set<string>();
  nodes.value?.forEach((n: any) => kinds.add(n.kind ?? 'ENTITY'));
  const order = [...Object.keys(ENTITY_STYLES), 'ENTITY', 'RELATION', 'PREDICATE', 'PUBLICATION'];
  legendKinds.value = order.filter((k) => kinds.has(k));
}

function renderGraph(nodesArray: GraphNode[], edgesArray: Edge[]) {
  if (!graphContainer.value) {
    console.error('Graph container is not available.');
    return;
  }
  if (!nodes.value) nodes.value = new DataSet();
  if (!edges.value) edges.value = new DataSet();

  nodes.value.clear();
  edges.value.clear();
  nodes.value.add(nodesArray);
  edges.value.add(edgesArray);
  updateLegend();

  const data = { nodes: nodes.value, edges: edges.value };
  const options = {
    nodes: {
      shape: 'dot',
      size: 22,
      borderWidth: 2,
      shadow: { enabled: true, color: 'rgba(15,23,42,0.18)', size: 8, x: 0, y: 2 },
      font: { size: 15, face: 'Helvetica, Arial, sans-serif', color: '#1f2937' },
    },
    edges: {
      arrows: 'to',
      smooth: { enabled: true, type: 'continuous', roundness: 0.5 },
      font: { size: 11, align: 'middle', color: '#475569', strokeWidth: 3, strokeColor: '#ffffff' },
      color: { color: '#94a3b8', highlight: '#2563eb', hover: '#2563eb' },
      selectionWidth: 2,
      width: 1.5,
    },
    physics: {
      stabilization: { iterations: 120, updateInterval: 25 },
      barnesHut: { gravitationalConstant: -2200, springLength: 160, springConstant: 0.03 },
    },
    interaction: { hover: true, tooltipDelay: 150, zoomSpeed: 0.6 },
    layout: { improvedLayout: true },
  };

  if (!network) {
    network = new Network(graphContainer.value, data, options as any);
  } else {
    network.setData(data);
  }

  network.off('click');
  network.on('click', async (params: any) => {
    if (params.nodes.length > 0) {
      await toggleNode(params.nodes[0]);
    } else if (params.edges.length > 0) {
      selectEdge(params.edges[0]);
    } else {
      deselectEdge();
    }
  });
}

function fitGraph() {
  network?.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
}

function selectEdge(edgeId: string) {
  const edge = edges.value?.get(edgeId);
  if (!edge) return;
  selectedEdge.value = edge;
}

function deselectEdge() {
  selectedEdge.value = null;
  network?.unselectAll();
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

function addNodesAndEdgesFromMemory(memory: { nodes: any[]; edges: any[] }) {
  if (nodes.value && memory.nodes.length) nodes.value.add(memory.nodes);
  if (edges.value && memory.edges.length) edges.value.add(memory.edges);
}

async function expandNode(nodeId: string) {
  if (expandedData.value[nodeId]) {
    addNodesAndEdgesFromMemory(expandedData.value[nodeId]);
    updateLegend();
    return;
  }
  const connectedBindings = await fetchConnectedNodes(nodeId);
  const memory: { nodes: any[]; edges: any[] } = { nodes: [], edges: [] };
  const newNodes: GraphNode[] = [];
  const newEdges: Edge[] = [];
  const nodeIds = new Set<string>((nodes.value?.getIds() as string[]) || []);

  connectedBindings.forEach((binding: any) => {
    const s = binding.subject.value;
    const p = binding.predicate.value;
    const o = binding.object.value;
    // rdf:type statements are used for colouring, not drawn as edges
    if (p === 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type') return;
    const sKind = guessKind(s, binding.subjectType?.value, p, 'subject');
    const oKind = guessKind(o, binding.objectType?.value, p, 'object');
    if (!nodeIds.has(s)) {
      const nodeObj = makeNode(s, sKind);
      newNodes.push(nodeObj);
      nodeIds.add(s);
      nodeStates.value[s] = 'collapsed';
      memory.nodes.push(nodeObj);
    }
    if (!nodeIds.has(o)) {
      const nodeObj = makeNode(o, oKind);
      newNodes.push(nodeObj);
      nodeIds.add(o);
      nodeStates.value[o] = 'collapsed';
      memory.nodes.push(nodeObj);
    }
    const edgeObj: Edge = makeEdge(s, o, localName(p), p);
    newEdges.push(edgeObj);
    memory.edges.push(edgeObj);
  });
  if (nodes.value && newNodes.length) nodes.value.add(newNodes);
  if (edges.value && newEdges.length) edges.value.add(newEdges);
  expandedData.value[nodeId] = memory;
  updateLegend();
}

/** Decide how to draw a neighbour reached through an arbitrary predicate. */
function guessKind(uri: string, typeUri: string | undefined, predicate: string, role: 'subject' | 'object'): string {
  const name = localName(uri);
  if (name.startsWith('REL_')) return 'RELATION';
  if (name.startsWith('PUB_') || predicate.endsWith('wasDerivedFrom') && role === 'object') return 'PUBLICATION';
  if (predicate.endsWith('relation_predicate') && role === 'object') return 'PREDICATE';
  return entityKind(typeUri);
}

async function fetchConnectedNodes(nodeId: string) {
  const isURI = /^(http|https):\/\/.+$/.test(nodeId);
  const formattedNodeId = isURI ? nodeId : `${ONT_NS}${nodeId}`;
  const sparqlQuery = `
    SELECT ?subject ?predicate ?object ?subjectType ?objectType WHERE {
      { ?subject ?predicate ?object . FILTER(?subject = <${formattedNodeId}>) }
      UNION
      { ?subject ?predicate ?object . FILTER(?object = <${formattedNodeId}>) }
      OPTIONAL { ?subject a ?subjectType . FILTER(STRSTARTS(STR(?subjectType), "${ONT_NS}") && ?subjectType != <${ONT_NS}Entity>) }
      OPTIONAL { ?object a ?objectType . FILTER(STRSTARTS(STR(?objectType), "${ONT_NS}") && ?objectType != <${ONT_NS}Entity>) }
    } LIMIT 100
  `;
  try {
    const response = await sparqlGet(currentRepoId.value, sparqlQuery);
    return response.data.results.bindings;
  } catch (error) {
    console.error('Error fetching connected nodes:', error);
    setStatus('Could not load the neighbours of this node.', 'error');
    return [];
  }
}

function collapseNode(nodeId: string) {
  if (!expandedData.value[nodeId] || !nodes.value || !edges.value) return;
  const { nodes: memoryNodes, edges: memoryEdges } = expandedData.value[nodeId];
  edges.value.remove(memoryEdges.map((edge) => edge.id || `${edge.from}-${edge.to}-${edge.rel}`));
  nodes.value.remove(memoryNodes.map((node) => node.id));
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
        relation: r.relation,
        subject: r.subject,
        predicate: r.predicate,
        object: r.object,
        publication: r.publicationId || '',
        subjectType: r.subjectType ?? null,
        objectType: r.objectType ?? null,
      }));

      const nodesArray: GraphNode[] = [];
      const edgesArray: Edge[] = [];
      const nodeIds = new Set<string>();

      results.value.forEach((r) => {
        addNode(nodesArray, nodeIds, makeNode(r.relation, 'RELATION'));
        addNode(nodesArray, nodeIds, makeNode(r.subject, entityKind(r.subjectType)));
        addNode(nodesArray, nodeIds, makeNode(r.predicate, 'PREDICATE'));
        addNode(nodesArray, nodeIds, makeNode(r.object, entityKind(r.objectType)));
        nodeStates.value[r.subject] = 'collapsed';
        nodeStates.value[r.object] = 'collapsed';
        edgesArray.push(makeEdge(r.relation, r.subject, 'relation_subject', r.predicate));
        edgesArray.push(makeEdge(r.relation, r.predicate, 'relation_predicate', r.predicate));
        edgesArray.push(makeEdge(r.relation, r.object, 'relation_object', r.predicate));
        if (r.publication) {
          addNode(nodesArray, nodeIds, makeNode(r.publication, 'PUBLICATION'));
          edgesArray.push(makeEdge(r.relation, r.publication, 'wasDerivedFrom', 'publication'));
        }
      });

      if (edgesArray.length === 0) {
        setStatus('No results found.', 'info');
        clearGraph();
        graphState.value = 'empty';
      } else {
        setStatus(`${results.value.length} relation(s) found.`, 'success');
        renderGraph(nodesArray, edgesArray);
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

/** Show a single search result as a small star graph and highlight the row. */
function selectRelation(result: SearchResult, index: number) {
  selectedResultIndex.value = index;
  deselectEdge();
  const nodesArray: GraphNode[] = [];
  const edgesArray: Edge[] = [];
  const nodeIds = new Set<string>();

  addNode(nodesArray, nodeIds, makeNode(result.relation, 'RELATION'));
  addNode(nodesArray, nodeIds, makeNode(result.subject, entityKind(result.subjectType)));
  addNode(nodesArray, nodeIds, makeNode(result.object, entityKind(result.objectType)));
  const relTypeId = 'type_' + result.relation;
  addNode(nodesArray, nodeIds, makeNode(relTypeId, 'PREDICATE', localName(result.predicate)));
  nodeStates.value[result.subject] = 'collapsed';
  nodeStates.value[result.object] = 'collapsed';

  edgesArray.push(makeEdge(result.relation, result.subject, 'relation_subject', result.predicate));
  edgesArray.push(makeEdge(result.relation, relTypeId, 'relation_predicate', result.predicate));
  edgesArray.push(makeEdge(result.relation, result.object, 'relation_object', result.predicate));
  if (result.publication) {
    addNode(nodesArray, nodeIds, makeNode(result.publication, 'PUBLICATION'));
    edgesArray.push(makeEdge(result.relation, result.publication, 'wasDerivedFrom', 'publication'));
  }
  renderGraph(nodesArray, edgesArray);
  graphState.value = 'ready';
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

  const payload = edge.rel === 'relation_predicate'
    ? { subject: localName(edge.from), predicate: edge.rel, object: localName(edge.predicate), repo_id: currentRepoId.value }
    : { subject: localName(edge.from), predicate: edge.rel, object: localName(edge.to), repo_id: currentRepoId.value };

  const loader = $loading.show();
  try {
    const response = await axios.post(`${API_URL}/api/deleteRelation`, payload, { headers: { 'Content-Type': 'application/json' } });
    if (response.status === 200) {
      if (edge.id && edges.value) edges.value.remove(edge.id);
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

function clearGraph() {
  nodes.value?.clear();
  edges.value?.clear();
  network?.setData({ nodes: [], edges: [] });
  legendKinds.value = [];
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
          ⚠️ The backend API is not reachable at <code>{{ API_URL }}</code>. Search, extraction and
          reasoning are disabled until it is up (<code>cd backend && flask run -p 5555</code>).
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
                Make sure the API (<code class="inline">flask run -p 5555</code>) and GraphDB are running,
                and that <code class="inline">GRAPHDB_URL</code> in <code class="inline">.env</code> points at GraphDB.
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
            <p class="muted hint">Click a node to expand or collapse its neighbours · click an edge to select a relation · scroll to zoom.</p>
          </div>

          <div v-if="selectedEdge" class="selection">
            <span class="selection-text">{{ selectedRelationText }}</span>
            <div class="btn-row">
              <button class="btn btn-secondary btn-sm" type="button" @click="deselectEdge">Clear</button>
              <button class="btn btn-danger btn-sm" type="button" @click="deleteSelectedEdge">Delete relation</button>
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
                    :key="result.relation + index"
                    :class="{ selected: index === selectedResultIndex }"
                    @click="selectRelation(result, index)"
                  >
                    <td>{{ prettyLabel(localName(result.subject)) }}</td>
                    <td><span class="tag">{{ localName(result.predicate) }}</span></td>
                    <td>{{ prettyLabel(localName(result.object)) }}</td>
                    <td class="muted">{{ localName(result.publication) || '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="card">
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

          <section class="card">
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

.graph-overlay h3 {
  font-size: 17px;
}

.graph-overlay p {
  max-width: 460px;
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
