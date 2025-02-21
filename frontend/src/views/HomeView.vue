<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue';
import 'vue-loading-overlay/dist/css/index.css';
import { useLoading } from 'vue-loading-overlay';
import axios from 'axios';
import { Network } from 'vis-network';
import { DataSet } from 'vis-data';

interface Edge {
  id: string;
  from: string;
  to: string;
  label: string;
  predicate: string;
}

interface Repository {
  id: string;
}

// Reactive State Variables
const abstract = ref('');
const responseText = ref('');
const statusText = ref('');
const validationError = ref('');
const searchValidationError = ref('');
const repositories = ref<Repository[]>([]);
const currentRepoId = ref('amd_repo_mistral');
const queryText = ref('');
const filterType = ref('');
const results = ref<{ relation: string; subject: string; predicate: string; object: string; publication: string }[]>([]);
const selectedEdge = ref<Edge | null>(null);
const loadingGraph = ref(true);
const nodeStates = ref<Record<string, string>>({});

const abstractFile = ref<File | null>(null);
const relationsFile = ref<File | Blob | null>(null);
const selectedModel = ref<string>('');
const abstractDownloadLink = ref<string | null>(null);
const relationsFileReady = ref(false);
const uploadStatus = ref<string | null>(null);
const infoVisible = ref(false);
const deepSeekInfoVisible = ref(false);
const repoInfoVisible = ref(false);

// Loading Indicator & Graph Refs
const $loading = useLoading();
let statusTimeout: number | null = null;
const graphContainer = ref<HTMLElement | null>(null);
let network: Network | null = null;
const nodes = ref<DataSet<any> | null>(null);
const edges = ref<DataSet<Edge> | null>(null);
const expandedData = ref<Record<string, { nodes: any[]; edges: any[] }>>({});

// Utility Functions
function getLocalName(uri: string): string {
  const hashIndex = uri.lastIndexOf('#');
  if (hashIndex !== -1) return uri.substring(hashIndex + 1);
  const slashIndex = uri.lastIndexOf('/');
  if (slashIndex !== -1) return uri.substring(slashIndex + 1);
  return uri;
}

function clearStatusTextAfterDelay() {
  if (statusTimeout) clearTimeout(statusTimeout);
  statusTimeout = setTimeout(() => {
    statusText.value = '';
  }, 5000);
}

// Data Fetching & Initialization
onMounted(() => {
  fetchData();
  fetchRepositories();
});

async function fetchRepositories() {
  try {
    const response = await axios.get<Repository[]>("http://localhost:5555/api/available_repositories");
    repositories.value = response.data;
  } catch (error) {
    console.error("Error fetching repositories:", error);
  }
}

function activateRepository(repoId: string) {
  currentRepoId.value = repoId;
  fetchData();
}

async function fetchData(query: string | null = null) {
  const endpointUrl = `http://localhost:7200/repositories/${currentRepoId.value}`;
  const defaultQuery = `
    PREFIX c: <http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    SELECT ?relation ?subject ?predicate ?object ?publication WHERE {
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
    }
    LIMIT 10
  `.replace(/\s+/g, ' ');

  try {
    const response = await axios.get(endpointUrl, {
      params: { query: defaultQuery },
      headers: { 
        Accept: 'application/sparql-results+json',
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      paramsSerializer: (params) =>
        Object.keys(params)
          .map(key => `${key}=${encodeURIComponent(params[key])}`)
          .join('&')
    });
    processData(response.data);
    loadingGraph.value = false;
  } catch (error) {
    console.error('Error fetching data:', error);
    loadingGraph.value = false;
  }
}

function processData(data: any) {
  const nodesArray: any[] = [];
  const edgesArray: any[] = [];
  const nodeIds = new Set<string>();

  // Define the full URIs for each relation role
  const predicateURIs = {
    relation_subject: "http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#relation_subject",
    relation_predicate: "http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#relation_predicate",
    relation_object: "http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#relation_object",
    wasDerivedFrom: "http://www.w3.org/ns/prov#wasDerivedFrom"
  };

  data.results.bindings.forEach((binding: any) => {
    const { relation, subject, predicate, object, publication } = {
      relation: binding.relation?.value,
      subject: binding.subject?.value,
      predicate: binding.predicate?.value,
      object: binding.object?.value,
      publication: binding.publication?.value,
    };

    if (subject && predicate && object) {
      if (relation) {
        // Use a label for the relation node – here we show "Relation" plus publication info if available.
        const relationLabel = publication
          ? `Relation (Pub: ${getLocalName(publication)})`
          : "Relation";
        // Create nodes: relation, subject, predicate, object
        addNode(nodesArray, nodeIds, relation, relationLabel, "#FF9900", "diamond");
        addNode(nodesArray, nodeIds, subject, getLocalName(subject), "#6AA84F", "ellipse");
        addNode(nodesArray, nodeIds, predicate, getLocalName(predicate), "#9900FF", "box");
        addNode(nodesArray, nodeIds, object, getLocalName(object), "#6AA84F", "ellipse");

        // Create edges using the correct full URIs for each role
        edgesArray.push({
          from: relation,
          to: subject,
          label: "relation_subject",
          predicate: predicateURIs.relation_subject
        });
        edgesArray.push({
          from: relation,
          to: predicate,
          label: "relation_predicate",
          predicate: predicateURIs.relation_predicate
        });
        edgesArray.push({
          from: relation,
          to: object,
          label: "relation_object",
          predicate: predicateURIs.relation_object
        });
        if (publication) {
          addNode(nodesArray, nodeIds, publication, getLocalName(publication), "#1E90FF", "square");
          edgesArray.push({
            from: relation,
            to: publication,
            label: "wasDerivedFrom",
            predicate: predicateURIs.wasDerivedFrom
          });
        }
      } else {
        // For simple triples without an explicit relation node
        addNode(nodesArray, nodeIds, subject, getLocalName(subject), "#6AA84F", "ellipse");
        addNode(nodesArray, nodeIds, object, getLocalName(object), "#6AA84F", "ellipse");
        edgesArray.push({
          from: subject,
          to: object,
          label: getLocalName(predicate),
          predicate: predicate
        });
      }
    }
  });

  nextTick(() => renderGraph(nodesArray, edgesArray));
}

function addNode(nodesArray: any[], nodeIds: Set<string>, uri: string, label: string, color: string, shape: string) {
  if (!nodeIds.has(uri)) {
    nodesArray.push({
      id: uri,
      label,
      color,
      shape,
      font: { color: "#333", size: 14 }
    });
    nodeIds.add(uri);
  }
}

// Graph Visualization
function renderGraph(nodesArray: any[], edgesArray: any[]) {
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

  const data = { nodes: nodes.value, edges: edges.value };

  const options = {
    nodes: {
      shape: 'dot',
      size: 25,
      font: { size: 14, face: 'Helvetica', color: '#333' },
      borderWidth: 2,
      shadow: { enabled: true, color: 'rgba(0,0,0,0.3)' }
    },
    edges: {
      arrows: 'to',
      smooth: {
        enabled: true,
        type: "continuous",
        roundness: 0.5
      },
      font: { size: 12, align: 'middle' },
      color: { color: '#848484', highlight: '#848484' },
      width: 2
    },
    physics: {
      stabilization: { iterations: 100, updateInterval: 25 },
      barnesHut: { gravitationalConstant: -1500, springLength: 150 }
    },
    interaction: { hover: true, tooltipDelay: 200 },
    layout: { improvedLayout: true }
  };

  if (!network) {
    network = new Network(graphContainer.value, data, options);
  } else {
    network.setData(data);
  }

  network.off('click');
  network.on('click', async (params: any) => {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0];
      await toggleNode(nodeId);
    } else if (params.edges.length > 0) {
      const edgeId = params.edges[0];
      selectEdge(edgeId);
    } else {
      deselectEdge();
    }
  });
}

function selectEdge(edgeId: string) {
  if (edges.value) {
    const edge = edges.value.get(edgeId);
    if (edge) {
      selectedEdge.value = edge;
      
      let displayLabel = "";

      if (edge.label === "relation_predicate") {
        displayLabel = `${getLocalName(edge.from)} ${edge.label} ${getLocalName(edge.predicate)}`;
      } else {
        displayLabel = `${getLocalName(edge.from)} ${edge.label} ${getLocalName(edge.to)}`;
      }
      responseText.value = displayLabel;
    }
  }
}

function deselectEdge() {
  selectedEdge.value = null;
  responseText.value = '';
}

// Node Expansion / Collapse
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
  if (nodes.value && memory.nodes.length) {
    nodes.value.add(memory.nodes);
  }
  if (edges.value && memory.edges.length) {
    edges.value.add(memory.edges);
  }
}

async function expandNode(nodeId: string) {
  if (expandedData.value[nodeId]) {
    addNodesAndEdgesFromMemory(expandedData.value[nodeId]);
  } else {
    const connectedBindings = await fetchConnectedNodes(nodeId);
    const memory: { nodes: any[]; edges: any[] } = { nodes: [], edges: [] };
    const newNodes: any[] = [];
    const newEdges: any[] = [];
    const nodeIds = new Set(nodes.value?.getIds() || []);

    connectedBindings.forEach((binding: any) => {
      const s = binding.subject.value;
      const p = binding.predicate.value;
      const o = binding.object.value;
      if (!nodeIds.has(s)) {
        const nodeObj = { id: s, label: getLocalName(s), shape: 'ellipse', color: '#6AA84F' };
        newNodes.push(nodeObj);
        nodeIds.add(s);
        nodeStates.value[s] = 'collapsed';
        memory.nodes.push(nodeObj);
      }
      if (!nodeIds.has(o)) {
        const nodeObj = { id: o, label: getLocalName(o), shape: 'ellipse', color: '#6AA84F' };
        newNodes.push(nodeObj);
        nodeIds.add(o);
        nodeStates.value[o] = 'collapsed';
        memory.nodes.push(nodeObj);
      }
      const edgeObj = { from: s, to: o, label: getLocalName(p), predicate: p };
      newEdges.push(edgeObj);
      memory.edges.push(edgeObj);
    });
    if (nodes.value && newNodes.length) nodes.value.add(newNodes);
    if (edges.value && newEdges.length) edges.value.add(newEdges);
    expandedData.value[nodeId] = memory;
  }
}

async function fetchConnectedNodes(nodeId: string) {
  const endpointUrl = `http://localhost:7200/repositories/${currentRepoId.value}`;
  const baseURI = 'http://www.semanticweb.org/lecualexandru/ontologies/2024/11/CausalAMD#';
  const isURI = /^(http|https):\/\/.+$/.test(nodeId);
  const formattedNodeId = isURI ? nodeId : `${baseURI}${nodeId}`;
  const sparqlQuery = `
    SELECT ?subject ?predicate ?object WHERE {
      { ?subject ?predicate ?object . FILTER(?subject = <${formattedNodeId}> ) }
      UNION
      { ?subject ?predicate ?object . FILTER(?object = <${formattedNodeId}> ) }
    } LIMIT 100
  `;

  try {
    const response = await axios.get(endpointUrl, {
      params: { query: sparqlQuery },
      headers: { Accept: 'application/sparql-results+json' }
    });
    return response.data.results.bindings;
  } catch (error) {
    console.error('Error fetching connected nodes:', error);
    return [];
  }
}

function addNodesAndEdges(bindings: any[]) {
  if (!nodes.value || !edges.value) return;
  const newNodes: any[] = [];
  const newEdges: any[] = [];
  const nodeIds = new Set(nodes.value.getIds());

  bindings.forEach((binding: any) => {
    const s = binding.subject.value;
    const p = binding.predicate.value;
    const o = binding.object.value;
    if (!nodeIds.has(s)) {
      newNodes.push({ id: s, label: getLocalName(s), shape: 'ellipse', color: '#6AA84F' });
      nodeIds.add(s);
      nodeStates.value[s] = 'collapsed';
    }
    if (!nodeIds.has(o)) {
      newNodes.push({ id: o, label: getLocalName(o), shape: 'ellipse', color: '#6AA84F' });
      nodeIds.add(o);
      nodeStates.value[o] = 'collapsed';
    }
    newEdges.push({ from: s, to: o, label: getLocalName(p), predicate: p });
  });
  nodes.value.add(newNodes);
  edges.value.add(newEdges);
}

function collapseNode(nodeId: string) {
  if (!expandedData.value[nodeId] || !nodes.value || !edges.value) return;
  const { nodes: memoryNodes, edges: memoryEdges } = expandedData.value[nodeId];
  const edgeIds = memoryEdges.map(edge => edge.id || `${edge.from}-${edge.to}-${edge.label}`);
  edges.value.remove(edgeIds);
  const nodeIds = memoryNodes.map(node => node.id);
  nodes.value.remove(nodeIds);
}

function performSearch() {
  if (!queryText.value.trim()) {
    searchValidationError.value = 'Please enter a search term.';
    return;
  }
  searchValidationError.value = '';
  const loader = $loading.show();

  const params = new URLSearchParams();
  params.append('q', queryText.value);
  if (filterType.value) params.append('type', filterType.value);
  params.append('repo_id', currentRepoId.value);

  fetch(`http://localhost:5555/api/search?${params.toString()}`)
    .then(response => response.json())
    .then((data) => {
      // Map each field to its local name only.
      results.value = data.map((result: any) => ({
        relation: getLocalName(result.relation),
        subject: getLocalName(result.subject),
        predicate: getLocalName(result.predicate),
        object: getLocalName(result.object),
        publication: result.publicationId ? getLocalName(result.publicationId) : ''
      }));

      const nodesArray: any[] = [];
      const edgesArray: any[] = [];
      const nodeIds = new Set<string>();

      data.forEach((result: any) => {
        const rel = getLocalName(result.relation);
        const s = getLocalName(result.subject);
        const p = getLocalName(result.predicate);
        const o = getLocalName(result.object);
        const pub = result.publicationId ? getLocalName(result.publicationId) : '';

        // Create central Relation Node
        if (!nodeIds.has(rel)) {
          nodesArray.push({
            id: rel,
            label: rel,
            shape: 'diamond',
            color: '#FF9900'
          });
          nodeIds.add(rel);
        }
        // Create Subject Node
        if (!nodeIds.has(s)) {
          nodesArray.push({
            id: s,
            label: s,
            shape: 'ellipse',
            color: '#6AA84F'
          });
          nodeIds.add(s);
          nodeStates.value[s] = 'collapsed';
        }
        // Create Predicate Node
        if (!nodeIds.has(p)) {
          nodesArray.push({
            id: p,
            label: p,
            shape: 'box',
            color: '#9900FF'
          });
          nodeIds.add(p);
          nodeStates.value[p] = 'collapsed';
        }
        // Create Object Node
        if (!nodeIds.has(o)) {
          nodesArray.push({
            id: o,
            label: o,
            shape: 'ellipse',
            color: '#6AA84F'
          });
          nodeIds.add(o);
          nodeStates.value[o] = 'collapsed';
        }
        // Edge from Relation -> Subject
        edgesArray.push({
          from: rel,
          to: s,
          label: "relation_subject",
          predicate: p  // using predicate local name here if needed
        });
        // Edge from Relation -> Predicate
        edgesArray.push({
          from: rel,
          to: p,
          label: "relation_predicate",
          predicate: p
        });
        // Edge from Relation -> Object
        edgesArray.push({
          from: rel,
          to: o,
          label: "relation_object",
          predicate: p
        });
        // Edge from Relation -> Publication (if exists)
        if (pub) {
          if (!nodeIds.has(pub)) {
            nodesArray.push({
              id: pub,
              label: pub,
              shape: 'square',
              color: '#1E90FF'
            });
            nodeIds.add(pub);
            nodeStates.value[pub] = 'collapsed';
          }
          edgesArray.push({
            from: rel,
            to: pub,
            label: "wasDerivedFrom",
            predicate: "publication"
          });
        }
      });

      if (edgesArray.length === 0) {
        statusText.value = 'No results found.';
        clearGraph();
      } else {
        statusText.value = 'Search completed successfully!';
        renderGraph(nodesArray, edgesArray);
      }
    })
    .catch((error) => {
      console.error('Error during search:', error);
      statusText.value = 'Error during search.';
    })
    .finally(() => {
      loader.hide();
      clearStatusTextAfterDelay();
    });
}


function selectRelation(result: any) {
  clearGraph();
  const nodesArray: any[] = [];
  const edgesArray: any[] = [];
  const nodeIds = new Set<string>();

  // Extract values from the result object.
  const relNum = result.relation; // The raw relation number (ID)
  const subject = result.subject;
  const predicate = result.predicate; // The relation type (e.g., "cause")
  const object = result.object;
  const pub = result.publication;

  // Create central node: Relation Number
  if (!nodeIds.has(relNum)) {
    nodesArray.push({
      id: relNum,
      label: getLocalName(relNum),
      shape: 'diamond',
      color: '#FF9900'
    });
    nodeIds.add(relNum);
  }

  // Create Subject Node
  if (!nodeIds.has(subject)) {
    nodesArray.push({
      id: subject,
      label: getLocalName(subject),
      shape: 'ellipse',
      color: '#6AA84F'
    });
    nodeIds.add(subject);
  }

  // Create Object Node
  if (!nodeIds.has(object)) {
    nodesArray.push({
      id: object,
      label: getLocalName(object),
      shape: 'ellipse',
      color: '#6AA84F'
    });
    nodeIds.add(object);
  }

  // Create Relation Type Node (separate node to show the relation label)
  const relTypeId = "type_" + relNum;
  if (!nodeIds.has(relTypeId)) {
    nodesArray.push({
      id: relTypeId,
      label: getLocalName(predicate),
      shape: 'box',
      color: '#9900FF'
    });
    nodeIds.add(relTypeId);
  }

  // Create Publication Node if available
  if (pub && !nodeIds.has(pub)) {
    nodesArray.push({
      id: pub,
      label: getLocalName(pub),
      shape: 'square',
      color: '#1E90FF'
    });
    nodeIds.add(pub);
  }

  // Create edges from the central relation number node to the others.
  edgesArray.push({
    from: relNum,
    to: subject,
    label: "relation_subject",
    predicate: predicate
  });
  edgesArray.push({
    from: relNum,
    to: relTypeId,
    label: "relation_predicate",
    predicate: predicate
  });
  edgesArray.push({
    from: relNum,
    to: object,
    label: "relation_object",
    predicate: predicate
  });
  if (pub) {
    edgesArray.push({
      from: relNum,
      to: pub,
      label: "wasDerivedFrom",
      predicate: "publication"
    });
  }

  renderGraph(nodesArray, edgesArray);
}

async function deleteSelectedEdge() {
  if (!selectedEdge.value) {
    statusText.value = 'No edge selected for deletion.';
    clearStatusTextAfterDelay();
    return;
  }

  const edge = selectedEdge.value;
  console.log('Attempting to delete edge:', edge);

  // Build payload based on edge type using the same logic as in your selectEdge function
  let payload;
  if (edge.label === "relation_predicate") {
    payload = {
      subject: edge.from,
      predicate: edge.label, // "relation_predicate"
      object: edge.predicate,
      repo_id: currentRepoId.value
    };
  } else {
    payload = {
      subject: edge.from,
      predicate: edge.label,
      object: edge.to,
      repo_id: currentRepoId.value
    };
  }
  console.log('Payload for deletion:', payload);

  // Show loader before starting the request
  const loader = $loading.show();

  try {
    const response = await axios.post(
      'http://localhost:5555/api/deleteRelation',
      payload,
      { headers: { 'Content-Type': 'application/json' } }
    );

    if (response.status === 200) {
      // Use the DataSet's remove method
      if (edges.value) {
        edges.value.remove(edge.id);
      }
      deselectEdge();
      statusText.value = 'Relation deleted successfully!';
      console.log('Edge deleted successfully.');
    } else {
      console.warn('Deletion request returned non-200 status:', response.status);
      statusText.value = 'Failed to delete relation.';
    }
  } catch (error) {
    console.error('Error deleting relation:', error);
    statusText.value = 'Error deleting relation.';
  } finally {
    loader.hide();
    clearStatusTextAfterDelay();
  }
}

function clearGraph() {
  if (nodes.value) nodes.value.clear();
  if (edges.value) edges.value.clear();
  if (network) network.setData({ nodes: [], edges: [] });
}

function refreshGraph() {
  loadingGraph.value = true;
  if (queryText.value.trim()) {
    performSearch();
  } else {
    fetchData().then(() => {
      loadingGraph.value = false;
      statusText.value = 'Default graph loaded successfully!';
      clearStatusTextAfterDelay();
    });
  }
}

// KG Operations & Relation Extraction
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
  } catch (e) {
    validationError.value = 'Relations must be valid JSON.';
    return false;
  }
  return true;
}

function showRelations() {
  if (!validateAbstract()) return;
  validationError.value = '';
  const loader = $loading.show();
  fetch('http://localhost:5555/api/showRelations', {
    method: 'POST',
    body: JSON.stringify(abstract.value),
    headers: { 'Content-Type': 'application/json' }
  })
    .then(response => response.json())
    .then(response => {
      responseText.value = JSON.stringify(response, null, 2);
      statusText.value = 'Relations fetched successfully!';
    })
    .catch(() => {
      statusText.value = 'Error fetching relations.';
    })
    .finally(() => {
      loader.hide();
      clearStatusTextAfterDelay();
    });
}

function addRelations() {
  if (!validateRelations()) return;
  validationError.value = '';
  const loader = $loading.show();
  const payload = {
    repo_id: currentRepoId.value,
    relations: JSON.parse(responseText.value)
  };
  fetch('http://localhost:5555/api/addRelations', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'Content-Type': 'application/json' }
  })
    .then(response => response.json())
    .then(data => {
      statusText.value = data.status === "Successfully completed"
        ? "Relations successfully added to the knowledge graph!"
        : "There was an issue adding relations.";
    })
    .catch(() => {
      statusText.value = 'Error adding relations.';
    })
    .finally(() => {
      loader.hide();
      clearStatusTextAfterDelay();
    });
}

function reasonKg() {
  validationError.value = '';
  const loader = $loading.show();
  const params = new URLSearchParams();
  params.append('repo_id', currentRepoId.value);
  fetch(`http://localhost:5555/api/reason?${params.toString()}`, {
    method: 'GET',
  })
    .then(response => response.json())
    .then(data => {
      statusText.value = data.status === "Successfully completed"
        ? "Reasoning operation completed successfully!"
        : "There was an issue running the reasoner.";
    })
    .catch(() => {
      statusText.value = 'Error running the reasoner.';
    })
    .finally(() => {
      loader.hide();
      clearStatusTextAfterDelay();
    });
}

// File Upload & Extraction
function handleAbstractUpload(event: Event) {
  const fileInput = event.target as HTMLInputElement;
  abstractFile.value = fileInput.files ? fileInput.files[0] : null;
}

function handleRelationsUpload(event: Event) {
  const fileInput = event.target as HTMLInputElement;
  relationsFile.value = fileInput.files ? fileInput.files[0] : null;
}

async function uploadAbstractFile() {
  const loader = $loading.show();
  if (!abstractFile.value || !selectedModel.value) return;
  const formData = new FormData();
  formData.append("file", abstractFile.value);
  formData.append("model", selectedModel.value);
  try {
    const response = await axios.post("http://localhost:5555/api/upload_abstract", formData, {
      responseType: "blob",
    });
    const extractedFile = new Blob([response.data], { type: "application/json" });
    abstractDownloadLink.value = URL.createObjectURL(extractedFile);
    relationsFile.value = extractedFile;
    relationsFileReady.value = true;
  } catch (error) {
    console.error("Error extracting relations from abstract:", error);
  } finally {
    loader.hide();
    clearStatusTextAfterDelay();
  }
}

async function addRelationsToKG() {
  if (!relationsFile.value || !currentRepoId.value) {
    console.error('No relations file or repository ID provided.');
    return;
  }
  const formData = new FormData();
  formData.append("file", relationsFile.value);
  formData.append("repo_id", currentRepoId.value);
  try {
    const response = await axios.post("http://localhost:5555/api/upload_relations", formData);
    uploadStatus.value = response.data.message || "Failed to add relations.";
  } catch (error) {
    console.error("Error adding relations to KG:", error);
    uploadStatus.value = "Error adding relations to KG.";
  }
}

function toggleInfo() {
  infoVisible.value = !infoVisible.value;
}

function toggleDeepSeekInfo() {
  deepSeekInfoVisible.value = !deepSeekInfoVisible.value;
}

function toggleRepoInfo() {
  repoInfoVisible.value = !repoInfoVisible.value;
}
</script>

<template>
  <div class="app-container">
    <aside class="sidebar">
      <router-link to="/" class="sidebar-link">Home</router-link>
      <router-link to="/chat" class="sidebar-link">Chat</router-link>
      <router-link to="/evaluation" class="sidebar-link">Evaluation</router-link>
    </aside>

    <div class="main-content">
      <div class="left-part">
        <section class="iframe-section">
          <h2 class="section-title">Knowledge Graph Visualization</h2>
          <div ref="graphContainer" class="visualization-container"></div>
          <button @click="refreshGraph" class="action-button">Refresh Graph</button>
        </section>

        <section class="search-section">
          <h2 class="section-title">Search and Filtering</h2>
          <div class="input-area">
            <label for="search-input" class="input-label">Search</label>
            <input type="text" v-model="queryText" id="search-input" placeholder="Enter search term" @keyup.enter="performSearch" class="search-input">
          </div>
          <div class="filter-area">
            <label for="filter-select" class="input-label">Filter By</label>
            <select v-model="filterType" id="filter-select" class="filter-select">
              <option value="">All</option>
              <option value="node">Node</option>
              <option value="relation">Relation</option>
              <option value="entity">Entity</option>
            </select>
          </div>
          <div class="buttons-container">
            <button @click="performSearch" class="action-button">Search</button>
          </div>
          <div v-if="searchValidationError" class="validation-error">
            <p>{{ searchValidationError }}</p>
          </div>
          <div v-if="results.length" class="results-section">
            <h3 class="section-title">Results:</h3>
            <div class="results-table-container">
              <table class="results-table">
                <thead>
                  <tr>
                    <th>Subject</th>
                    <th>Predicate</th>
                    <th>Object</th>
                    <th>Publication</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(result, index) in results"
                      :key="index"
                      @click="selectRelation(result)"
                      style="cursor: pointer;">
                    <td>{{ result.subject }}</td>
                    <td>{{ result.predicate }}</td>
                    <td>{{ result.object }}</td>
                    <td>{{ result.publication }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>

      <section class="controls-section">
        <div class="header-container">
          <div class="info-container">
            <button class="info-button" @click="toggleDeepSeekInfo">
              <svg class="info-icon" viewBox="0 0 24 24" width="18" height="18">
                <circle cx="12" cy="12" r="10" fill="none" stroke="#007bff" stroke-width="2"/>
                <text x="12" y="16" text-anchor="middle" fill="#007bff" font-size="12" font-family="Arial" font-weight="bold">i</text>
              </svg>
            </button>
            <transition name="fade">
              <div v-if="deepSeekInfoVisible" class="popover">
                <p>Relations are extracted using DeepSeek-R1:7B</p>
                <button class="close-button" @click="toggleDeepSeekInfo">&times;</button>
              </div>
            </transition>
          </div>
          <h2 class="section-title">Knowledge Graph Operations</h2>
        </div>

        <div class="input-area">
          <textarea v-model="abstract" id="abstract-input" placeholder="Enter abstract" class="abstract-textarea"></textarea>
        </div>
        <div class="buttons-container">
          <button @click="showRelations" class="action-button">Show Relations</button>
          <button @click="addRelations" class="action-button">Add Relations</button>
          <button @click="reasonKg" class="action-button">Reason KG</button>
          <button @click="deleteSelectedEdge" class="action-button delete-button" :disabled="!selectedEdge">Delete Relation</button>
        </div>
        <div v-if="validationError" class="validation-error">
          <p>{{ validationError }}</p>
        </div>
        <div class="output-area">
          <div class="textarea-container">
            <textarea v-model="responseText" id="response-text" placeholder="Relations" class="response-textarea"></textarea>
          </div>
          <div class="textarea-container">
            <label for="status-text" class="input-label">Status</label>
            <textarea v-model="statusText" id="status-text" readonly class="status-textarea"></textarea>
          </div>
        </div>
      </section>

      <section class="repositories-section">
        <div class="header-container">
          <div class="info-container left">
            <button class="info-button" @click="toggleRepoInfo">
              <svg class="info-icon" viewBox="0 0 24 24" width="18" height="18">
                <circle cx="12" cy="12" r="10" fill="none" stroke="#007bff" stroke-width="2"/>
                <text x="12" y="16" text-anchor="middle" fill="#007bff" font-size="12" font-family="Arial" font-weight="bold">i</text>
              </svg>
            </button>
            <transition name="fade">
              <div v-if="repoInfoVisible" class="popover left">
                <p>Select the repository you wish to use from GraphDB.</p>
                <button class="close-button" @click="toggleRepoInfo">&times;</button>
              </div>
            </transition>
          </div>
          <h2 class="section-title">Available Repositories</h2>
        </div>
        <div class="repositories-container">
          <button v-for="repo in repositories" :key="repo.id" @click="activateRepository(repo.id)" :class="['repo-button', { active: repo.id === currentRepoId }]" class="repo-button">
            {{ repo.id }}
          </button>
        </div>
        <div class="header-container">
        <div class="info-container">
            <button class="info-button" @click="toggleInfo">
              <svg class="info-icon" viewBox="0 0 24 24" width="18" height="18">
                <circle cx="12" cy="12" r="10" fill="none" stroke="#007bff" stroke-width="2"/>
                <text x="12" y="16" text-anchor="middle" fill="#007bff" font-size="12" font-family="Arial" font-weight="bold">i</text>
              </svg>
            </button>
            <transition name="fade">
              <div v-if="infoVisible" class="popover">
                <p>API keys must be provided in the .env file for this section to work correctly.</p>
                <button class="close-button" @click="toggleInfo">&times;</button>
              </div>
            </transition>
          </div>
          <h2 class="section-title">Relation Extraction and Upload</h2>
        </div>
        <div class="form-group">
          <label for="modelSelect">Select Model for Extraction:</label>
          <select v-model="selectedModel" id="modelSelect" class="select-input">
            <option value="" disabled>Select a model</option>
            <option value="model_a">GPT3.5 Turbo (Fine-Tuned)</option>
            <option value="model_b">Mistral-Nemo (Fine-Tuned)</option>
            <option value="model_c">GPT 4o1-mini</option>
            <option value="model_d">DeepSeek R1</option>
          </select>
        </div>
        <div class="form-group">
          <label for="abstractFile">Upload Abstract File:</label>
          <input type="file" id="abstractFile" @change="handleAbstractUpload" class="file-input" />
          <button @click="uploadAbstractFile" :disabled="!abstractFile || !selectedModel" class="action-button">
            Extract Relations from Abstract
          </button>
        </div>
        <div v-if="abstractDownloadLink" class="download-section">
          <a :href="abstractDownloadLink" download="extracted_relations.json" class="download-link">
            Download Extracted Relations
          </a>
        </div>
        <p v-if="relationsFileReady" class="status-message">
          Extracted relations are ready for upload. You can replace the file if needed.
        </p>
        <div class="form-group">
          <label for="relationsFile">Upload or Modify Extracted Relations File:</label>
          <input type="file" id="relationsFile" @change="handleRelationsUpload" class="file-input" />
          <button @click="addRelationsToKG" :disabled="!relationsFile" class="action-button">
            Add Relations to Knowledge Graph
          </button>
        </div>
        <div v-if="uploadStatus" class="upload-status">
          {{ uploadStatus }}
        </div>
      </section>
    </div>
  </div>
</template>

<style>
/* Global Reset and Base Styles */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
html, body {
  height: 100%;
  width: 100%;
  overflow-x: hidden;
  font-family: 'Roboto', sans-serif;
  background-color: #f7f9fc;
  color: #333;
}
.header-container {
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-title {
  margin: 0;
  font-size: 1.5em;
  flex: 1;
}

.info-container {
  position: relative;
}

/* Refined info button */
.info-button {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: 50%;
  transition: background-color 0.2s;
}

.info-button:hover {
  background-color: rgba(0, 123, 255, 0.1);
}

.info-icon {
  display: block;
}

/* Adjusted popover with wider dimensions */
.popover {
  position: absolute;
  top: 110%;
  left: 0;
  width: 320px; /* Fixed width for a horizontal layout */
  background: #fff;
  border: 1px solid #e0e0e0;
  padding: 10px 15px;
  border-radius: 4px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  z-index: 100;
  font-size: 0.8em;
  line-height: 1.3;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.popover p {
  margin: 0;
  white-space: normal;
  flex: 1;
}

/* Optional: A slight adjustment for the arrow, if needed, removed for a cleaner design */
/* .popover::before and .popover::after { ... } */

.close-button {
  background: none;
  border: none;
  font-size: 1em;
  color: #888;
  cursor: pointer;
  margin-left: 10px;
  padding: 0;
}

.close-button:hover {
  color: #555;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Focus styles for accessibility */
:focus {
  outline: 3px solid #007bff;
  outline-offset: 2px;
}

/* App Layout */
.app-container {
  display: flex;
  min-height: 100vh;
  width: 100vw;
}

/* Sidebar Styling */
.sidebar {
  width: 200px;
  background-color: #343a40;
  color: #fff;
  padding: 20px;
  height: 100vh;
  position: fixed;
  top: 0;
  left: 0;
  box-shadow: 2px 0 10px rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
}
.sidebar-link {
  display: block;
  padding: 15px 20px;
  margin-bottom: 15px;
  color: #f8f9fa;
  text-decoration: none;
  border-radius: 6px;
  transition: background 0.3s ease;
}
.sidebar-link:hover, .sidebar-link:focus {
  background-color: #007bff;
}

/* Main Content Area */
.main-content {
  margin-left: 200px;
  padding: 20px;
  display: flex;
  gap: 20px;
  width: calc(100% - 200px);
  /* Allow vertical scrolling */
  overflow-y: auto;
  max-height: 100vh;
}

/* Left Part: Graph & Search */
.left-part {
  width: 50%;
  display: flex;
  flex-direction: column;
  gap: 20px;
  /* Ensure this column never pushes out the header */
  max-height: 100vh;
  overflow-y: auto;
}
.visualization-container {
  width: 100%;
  height: 50vh;  /* Fixed height for graph */
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  background-color: #fff;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  padding: 10px;
  overflow: auto;
}

/* Right Part: Operations */
.controls-section {
  width: 50%;
  background-color: #f0f2f5;
  padding: 25px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
  overflow-y: auto;
  max-height: 100vh;
}

/* Section Titles */
.section-title {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 20px;
  border-bottom: 2px solid #007bff;
  padding-bottom: 10px;
}

/* Input Areas */
.input-area, .textarea-container, .filter-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.input-label {
  font-size: 16px;
  font-weight: 500;
}
.abstract-textarea, .response-textarea, .status-textarea {
  padding: 15px;
  border: 1px solid #ced4da;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}
.abstract-textarea:focus, .response-textarea:focus, .status-textarea:focus {
  border-color: #007bff;
  box-shadow: 0 0 0 3px rgba(0,123,255,0.25);
}
.response-textarea {
  height: 250px;
  background-color: #f8f9fa;
}
.status-textarea {
  height: 120px;
  background-color: #eaf5ea;
  color: #28a745;
  font-weight: 500;
}

/* Search and Filter */
.search-input, .filter-select {
  padding: 12px;
  border: 1px solid #ced4da;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}
.search-input:focus, .filter-select:focus {
  border-color: #007bff;
  box-shadow: 0 0 0 3px rgba(0,123,255,0.25);
}

/* Buttons */
.buttons-container {
  display: flex;
  gap: 15px;
}
.action-button {
  padding: 12px 25px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  background-color: #007bff;
  color: #fff;
  font-size: 16px;
  transition: background 0.3s, transform 0.2s, box-shadow 0.3s;
}
.action-button:hover, .action-button:focus {
  background-color: #0056b3;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0,123,255,0.2);
}
.delete-button:disabled {
  background-color: #6c757d;
  cursor: not-allowed;
}

/* Results Table */
.results-table-container {
  max-height: 50vh;
  overflow-y: auto;
  border: 1px solid #ced4da;
  border-radius: 8px;
}
.results-table {
  width: 100%;
  border-collapse: collapse;
}
.results-table th,
.results-table td {
  padding: 10px;
  border: 1px solid #dee2e6;
  font-size: 16px;
  white-space: nowrap;
}
.results-table th {
  background-color: #f8f9fa;
  font-weight: bold;
}
.results-table tbody tr:hover {
  background-color: #f1f3f5;
}

/* Repositories Section */
.repositories-section {
  padding: 20px;
  background-color: #f9fafb;
  border-radius: 8px;
  margin-top: 20px;
  text-align: center;
}
.repositories-container {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}
.repo-button {
  min-width: 120px;
  padding: 12px 16px;
  background-color: #e5e7eb;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.3s, transform 0.2s, box-shadow 0.3s;
}
.repo-button:hover {
  background-color: #d1d5db;
  transform: translateY(-2px);
}
.repo-button.active {
  background-color: #3b82f6;
  color: #fff;
  transform: scale(1.05);
  box-shadow: 0 6px 12px rgba(59,130,246,0.4);
}

/* File Upload & Download */
.select-input, .file-input {
  padding: 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background-color: #fff;
  font-size: 1em;
  transition: border-color 0.3s, box-shadow 0.3s;
}
.select-input:focus, .file-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.25);
}
.download-section {
  margin-bottom: 15px;
}
.download-link {
  display: inline-block;
  padding: 10px 15px;
  background-color: #10b981;
  color: #fff;
  border-radius: 6px;
  text-decoration: none;
  transition: background 0.3s, transform 0.2s;
}
.download-link:hover {
  background-color: #059669;
  transform: translateY(-2px);
}
.status-message, .upload-status {
  text-align: center;
  margin-top: 10px;
  font-weight: 500;
}

/* Responsive Design */
@media (max-width: 1200px) {
  .main-content {
    flex-direction: column;
  }
  .left-part, .controls-section {
    width: 100%;
  }
}
@media (max-width: 768px) {
  .sidebar {
    width: 100%;
    height: auto;
    position: static;
  }
  .main-content {
    margin-left: 0;
  }
  .action-button, .repo-button {
    width: 100%;
  }
}
</style>