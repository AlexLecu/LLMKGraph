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

const abstract = ref('');
const responseText = ref('');
const statusText = ref('');
const validationError = ref('');
const searchValidationError = ref('');
const $loading = useLoading();
let statusTimeout: number | null = null;
const repositories = ref<Repository[]>([]);
const currentRepoId = ref('amd_repo');

const graphContainer = ref<HTMLElement | null>(null);
let network: Network | null = null;
const nodes = ref<DataSet<any> | null>(null);
const edges = ref<DataSet<Edge> | null>(null);
const nodeStates = ref<Record<string, string>>({});
const loadingGraph = ref(true);

const queryText = ref('');
const filterType = ref('');
const results = ref<{ subject: string; predicate: string; object: string }[]>([]);

const selectedEdge = ref<Edge | null>(null);

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
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX ont: <http://www.semanticweb.org/lecualexandru/ontologies/2024/1/>
    SELECT ?subject ?predicate ?object WHERE {
      ?subject ?predicate ?object .
      FILTER (?subject = ont:AMD)
    } LIMIT 50
  `;

  const sparqlQuery = query || defaultQuery;

  try {
    const response = await axios.get(endpointUrl, {
      params: { query: sparqlQuery },
      headers: { Accept: 'application/sparql-results+json' },
    });
    processData(response.data);
    loadingGraph.value = false;

  } catch (error) {
    console.error('Error fetching data:', error);
    loadingGraph.value = false;
  }
}

  function getLocalName(uri: string): string {
    const hashIndex = uri.lastIndexOf('#');
    if (hashIndex !== -1) {
      return uri.substring(hashIndex + 1);
    } else {
      const slashIndex = uri.lastIndexOf('/');
      if (slashIndex !== -1) {
        return uri.substring(slashIndex + 1);
      } else {
        return uri;
      }
    }
  }

function processData(data: any) {
  const nodesArray: any[] = [];
  const edgesArray: any[] = [];
  const nodeIds = new Set<string>();

  data.results.bindings.forEach((binding: any) => {
    const s = binding.subject.value;
    const p = binding.predicate.value;
    const o = binding.object.value;

    const sLabel = getLocalName(s);
    const pLabel = getLocalName(p);
    const oLabel = getLocalName(o);

    if (!nodeIds.has(s)) {
      nodesArray.push({ id: s, label: sLabel });
      nodeIds.add(s);
      nodeStates.value[s] = 'collapsed';
    }

    if (!nodeIds.has(o)) {
      nodesArray.push({ id: o, label: oLabel });
      nodeIds.add(o);
      nodeStates.value[o] = 'collapsed';
    }

    edgesArray.push({ from: s, to: o, label: pLabel });
  });

  nextTick(() => {
    renderGraph(nodesArray, edgesArray);
  });
}

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

  const data = {
    nodes: nodes.value,
    edges: edges.value,
  };

  const options = {
    nodes: {
      shape: 'dot',
      size: 15,
      font: {
        color: '#343434',
      },
    },
    edges: {
      arrows: {
        to: { enabled: true, scaleFactor: 1 },
      },
      color: '#848484',
      font: {
        align: 'top',
        color: '#343434',
      },
    },
    physics: {
      enabled: true,
    },
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
      // Clicked on empty space, deselect
      deselectEdge();
    }
  });
}

function selectEdge(edgeId: string) {
  if (edges.value) {
    const edge = edges.value.get(edgeId);
    if (edge) {
      selectedEdge.value = edge;
      const relation = `${getLocalName(edge.from)} ${edge.label} ${getLocalName(edge.to)}`;
      responseText.value = relation;
    }
  }
}

function deselectEdge() {
  selectedEdge.value = null;
  responseText.value = '';
}

async function deleteSelectedEdge() {
  if (selectedEdge.value) {
    const edge = selectedEdge.value;

    const payload = {
      subject: edge.from,
      predicate: edge.predicate,
      object: edge.to
    };

    const loader = $loading.show();

    try {
      const response = await axios.post('http://localhost:5555/api/deleteRelation', payload, {
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (response.status === 200) {
        if (edges.value && selectedEdge.value) {
          edges.value.remove(edge.id);
          deselectEdge();
          statusText.value = 'Relation deleted successfully!';
        }
      } else {
        statusText.value = 'Failed to delete relation.';
      }
    } catch (error) {
      console.error('Error deleting relation:', error);
      statusText.value = 'Error deleting relation.';
    } finally {
      loader.hide();
      clearStatusTextAfterDelay();
    }
  } else {
    statusText.value = 'No edge selected for deletion.';
    clearStatusTextAfterDelay();
  }
}

async function toggleNode(nodeId: string) {
  if (nodeStates.value[nodeId] === 'expanded') {
    collapseNode(nodeId);
    nodeStates.value[nodeId] = 'collapsed';
  } else {
    const connectedBindings = await fetchConnectedNodes(nodeId);
    addNodesAndEdges(connectedBindings);
    nodeStates.value[nodeId] = 'expanded';
  }
}

async function fetchConnectedNodes(nodeId: string) {
  const endpointUrl = `http://localhost:7200/repositories/${currentRepoId.value}`;

  const baseURI = 'http://www.semanticweb.org/lecualexandru/ontologies/2024/1/';
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
      headers: { Accept: 'application/sparql-results+json' },
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

    const sLabel = getLocalName(s);
    const pLabel = getLocalName(p);
    const oLabel = getLocalName(o);

    if (!nodeIds.has(s)) {
      newNodes.push({ id: s, label: sLabel });
      nodeIds.add(s);
      nodeStates.value[s] = 'collapsed';
    }

    if (!nodeIds.has(o)) {
      newNodes.push({ id: o, label: oLabel });
      nodeIds.add(o);
      nodeStates.value[o] = 'collapsed';
    }

    newEdges.push({ from: s, to: o, label: pLabel });
  });
  nodes.value.add(newNodes);
  edges.value.add(newEdges);
}

function collapseNode(nodeId: string) {
  if (!nodes.value || !edges.value) return;

  const connectedEdges = edges.value.get({
    filter: (edge: any) => edge.from === nodeId || edge.to === nodeId,
  });

  const connectedNodeIds = new Set<string>();
  connectedEdges.forEach((edge: any) => {
    if (edge.from !== nodeId) connectedNodeIds.add(edge.from);
    if (edge.to !== nodeId) connectedNodeIds.add(edge.to);
  });

  const connectedEdgeIds = connectedEdges.map((edge: any) => edge.id);
  edges.value.remove(connectedEdgeIds);

  nodes.value.remove(Array.from(connectedNodeIds));

  connectedNodeIds.forEach((id) => {
    delete nodeStates.value[id];
  });
}

function performSearch() {
  const nodesArray: any[] = [];
  const edgesArray: any[] = [];
  const nodeIds = new Set<string>();

  if (!queryText.value.trim()) {
    searchValidationError.value = 'Please enter a search term.';
    return;
  }

  searchValidationError.value = '';
  const loader = $loading.show();
  const params = new URLSearchParams();
  params.append('q', queryText.value);
  if (filterType.value) {
    params.append('type', filterType.value);
  }
  params.append('repo_id', currentRepoId.value)

  fetch(`http://localhost:5555/api/search?${params.toString()}`)
    .then((response) => response.json())
    .then((data) => {
      results.value = data.map((result: { subject: string; predicate: string; object: string }) => ({
          subject: getLocalName(result.subject),
          predicate: getLocalName(result.predicate),
          object: getLocalName(result.object),
        }));

      data.forEach(function (value: { subject: string; predicate: string; object: string }) {
          const s = value.subject;
          const p = value.predicate;
          const o = value.object;

          const sLabel = getLocalName(s);
          const pLabel = getLocalName(p);
          const oLabel = getLocalName(o);

        if (!nodeIds.has(s)) {
          nodesArray.push({ id: s, label: sLabel });
          nodeIds.add(s);
          nodeStates.value[s] = 'collapsed';
        }

        if (!nodeIds.has(o)) {
          nodesArray.push({ id: o, label: oLabel });
          nodeIds.add(o);
          nodeStates.value[o] = 'collapsed';
        }

        edgesArray.push({ from: s, to: o, label: pLabel, predicate: p });
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
    headers: {
      'Content-Type': 'application/json',
    }
  })
  .then((response) => response.json())
  .then((response) => {
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
    headers: {
      'Content-Type': 'application/json',
    }
  })
  .then((response) => response.json())
  .then((data) => {
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
  .then((response) => response.json())
  .then((data) => {
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

function clearStatusTextAfterDelay() {
  if (statusTimeout) {
    clearTimeout(statusTimeout);
  }
  statusTimeout = setTimeout(() => {
    statusText.value = '';
  }, 5000);
}

const abstractFile = ref<File | null>(null);
const relationsFile = ref<File | Blob | null>(null);
const selectedModel = ref<string>('');
const abstractDownloadLink = ref<string | null>(null);
const relationsFileReady = ref(false);
const uploadStatus = ref<string | null>(null);

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
</script>

<template>
  <div class="app-container">
    <aside class="sidebar">
      <router-link to="/" class="sidebar-link">Home</router-link>
      <router-link to="/chat" class="sidebar-link">Chat</router-link>
      <router-link to="/evaluation" class="sidebar-link">Evaluation</router-link>
    </aside>

    <div class="main-content">
      <!-- Left Part: Iframe and Search Section -->
      <div class="left-part">
        <section class="iframe-section">
          <h2 class="section-title">Knowledge Graph Visualization</h2>
          <div ref="graphContainer" class="visualization-container"></div>
          <button @click="refreshGraph" class="refresh-button">Refresh Graph</button>
        </section>

        <!-- Search Section -->
        <section class="search-section">
          <h2 class="section-title">Search and Filtering</h2>

          <div class="input-area">
            <label for="search-input" class="input-label">Search</label>
            <input
              type="text"
              v-model="queryText"
              id="search-input"
              placeholder="Enter search term"
              @keyup.enter="performSearch"
              class="search-input">
          </div>

          <div class="filter-area">
            <label for="filter-select" class="input-label">Filter By</label>
            <select
              v-model="filterType"
              id="filter-select"
              class="filter-select">
              <option value="">All</option>
              <option value="node">Node</option>
              <option value="relation">Relation</option>
              <option value="entity">Entity</option>
            </select>
          </div>

          <div class="buttons-container">
            <button @click="performSearch" class="action-button">Search</button>
          </div>

          <!-- Validation Error -->
          <div v-if="searchValidationError" class="validation-error">
            <p>{{ searchValidationError }}</p>
          </div>

          <!-- Search Results -->
          <div v-if="results.length" class="results-section">
            <h3 class="section-title">Results:</h3>

            <!-- Scrollable Table Container -->
            <div class="results-table-container">
              <table class="results-table">
                <thead>
                  <tr>
                    <th>Subject</th>
                    <th>Predicate</th>
                    <th>Object</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(result, index) in results" :key="index">
                    <td>{{ result.subject }}</td>
                    <td>{{ result.predicate }}</td>
                    <td>{{ result.object }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>

      <!-- Right Part: Controls Section -->
      <section class="controls-section">
        <h2 class="section-title">Knowledge Graph Operations</h2>

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
  <h2 class="section-title">Available Repositories</h2>

  <div class="repositories-container">
    <button
      v-for="repo in repositories"
      :key="repo.id"
      @click="activateRepository(repo.id)"
      :class="['repo-button', { active: repo.id === currentRepoId }]"
      class="repo-button"
    >
      {{ repo.id }}
    </button>
  </div>

  <h2 class="section-title">Relation Extraction and Upload</h2>

  <!-- Model Selection for Relation Extraction -->
  <div class="form-group">
    <label for="modelSelect">Select Model for Extraction:</label>
    <select v-model="selectedModel" id="modelSelect" class="select-input">
      <option value="" disabled>Select a model</option>
      <option value="model_a">GPT3.5 Turbo (Fine-Tuned)</option>
      <option value="model_b">Mistral-Nemo (Fine-Tuned)</option>
      <option value="model_c">GPT 4o1-mini</option>
    </select>
  </div>

  <!-- Upload Abstract File -->
  <div class="form-group">
    <label for="abstractFile">Upload Abstract File:</label>
    <input type="file" id="abstractFile" @change="handleAbstractUpload" class="file-input" />
    <button @click="uploadAbstractFile" :disabled="!abstractFile || !selectedModel" class="action-button">
      Extract Relations from Abstract
    </button>
  </div>

  <!-- Download Extracted Relations -->
  <div v-if="abstractDownloadLink" class="download-section">
    <a :href="abstractDownloadLink" download="extracted_relations.json" class="download-link">
      Download Extracted Relations
    </a>
  </div>

  <!-- Status Message -->
  <p v-if="relationsFileReady" class="status-message">
    Extracted relations are ready for upload. You can replace the file if needed.
  </p>

  <!-- Upload or Modify Extracted Relations File -->
  <div class="form-group">
    <label for="relationsFile">Upload or Modify Extracted Relations File:</label>
    <input type="file" id="relationsFile" @change="handleRelationsUpload" class="file-input" />
    <button @click="addRelationsToKG" :disabled="!relationsFile" class="action-button">
      Add Relations to Knowledge Graph
    </button>
  </div>

  <!-- Upload Status -->
  <div v-if="uploadStatus" class="upload-status">
    {{ uploadStatus }}
  </div>
</section>
    </div>
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  height: 100%;
  width: 100%;
  overflow-x: hidden;
}

html {
  scroll-behavior: smooth;
}

body {
  line-height: 1.6;
  color: #333;
  font-family: 'Roboto', sans-serif;
}

/* Improved focus styles for better accessibility */
:focus {
  outline: 3px solid #007bff;
  outline-offset: 2px;
}

/* General App Container */
.app-container {
  display: flex;
  min-height: 100vh;
  width: 100vw;
  background-color: #f7f9fc;
  overflow-x: hidden;
}

/* Sidebar Styling */
.sidebar {
  width: 200px;
  background-color: #343a40;
  color: white;
  height: 100vh;
  padding: 20px;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  position: fixed;
  left: 0;
  top: 0;
  transition: width 0.3s ease;
}

.sidebar-link {
  display: block;
  padding: 15px 20px;
  margin-bottom: 15px;
  font-size: 16px;
  color: #f8f9fa;
  background-color: #343a40;
  border-radius: 6px;
  transition: all 0.3s ease;
  border: 1px solid transparent;
}

.sidebar-link:hover, .sidebar-link:focus {
  background-color: #007bff;
  color: #ffffff;
  transform: scale(1.05);
  box-shadow: 0 4px 8px rgba(0, 123, 255, 0.2);
  border-color: #f8f9fa;
}

.validation-error {
  color: red;
  font-weight: bold;
  margin-top: 10px;
}

/* Main Content Area */
.main-content {
  margin-left: 200px;
  display: flex;
  flex-grow: 1;
  gap: 20px;
  padding: 20px;
  background-color: #f7f9fc;
  overflow-x: hidden;
  width: calc(100% - 200px);
  height: 100vh;
  overflow-y: auto;
}

/* Left Part: Iframe and Search Section */
.left-part {
  width: 50%;
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-height: calc(100vh - 40px);
  overflow-y: auto;
}

.visualization-container {
  width: 100%;
  height: 50vh;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  padding: 10px;
}

/* Right Part: Controls Section */
.controls-section {
  flex-grow: 1;
  width: 50%;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background-color: #f0f2f5;
  padding: 25px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  max-height: calc(100vh - 40px);
  overflow-y: auto;
}

/* Visualization Section */
.iframe-section {
  flex-grow: 1;
  background-color: #fff;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.refresh-button {
  margin-top: 15px;
  padding: 12px 25px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  background-color: #28a745;
  color: white;
  font-size: 16px;
  font-weight: 500;
  transition: all 0.3s ease;
}

.delete-button:disabled {
  background-color: #6c757d;
  cursor: not-allowed;
}

.delete-button:disabled:hover {
  background-color: #6c757d;
  box-shadow: none;
  transform: none;
}

.refresh-button:hover, .refresh-button:focus {
  background-color: #218838;
  box-shadow: 0 4px 8px rgba(40, 167, 69, 0.2);
  transform: translateY(-2px);
}

.refresh-button:active {
  transform: translateY(0);
}

.visualization-iframe {
  width: 100%;
  height: 50vh;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* Search Section */
.search-section {
  flex-grow: 1;
  background-color: #fff;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  max-height: none;
  overflow-y: visible;
}

.results-section {
  margin-top: 20px;
  overflow-y: visible;
  flex-grow: 1;
}

.results-table-container {
  max-height: 50vh;
  overflow-y: auto;
  width: 100%;
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
  text-align: left;
  font-size: 16px;
  color: #333;
  white-space: nowrap;
}

.results-table th {
  background-color: #f8f9fa;
  font-weight: bold;
}

.results-table td {
  background-color: #ffffff;
}

.results-table thead {
  position: sticky;
  top: 0;
  background-color: #f8f9fa;
  z-index: 1;
}

.results-table tbody tr:hover {
  background-color: #f1f3f5;
}

/* Section title styling */
.section-title {
  font-size: 24px;
  font-weight: bold;
  color: #333;
  margin-bottom: 20px;
  border-bottom: 2px solid #007bff;
  padding-bottom: 10px;
}

/* Input and Button Areas */
.input-area, .textarea-container, .filter-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.input-label {
  font-size: 16px;
  font-weight: 500;
  color: #333;
}

/* Abstract Textarea */
.abstract-textarea {
  height: 300px;
  padding: 15px;
  border: 1px solid #ced4da;
  border-radius: 8px;
  background-color: #ffffff;
  font-size: 16px;
  color: #333;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

.abstract-textarea:focus {
  border-color: #007bff;
  outline: none;
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.25);
}

/* Response and Status Textareas */
.response-textarea, .status-textarea {
  padding: 15px;
  border: 1px solid #ced4da;
  border-radius: 8px;
  background-color: #ffffff;
  font-size: 16px;
  color: #333;
  resize: vertical;
  box-sizing: border-box;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
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

.response-textarea:focus, .status-textarea:focus {
  border-color: #007bff;
  outline: none;
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.25);
}

/* Search Input */
.search-input {
  padding: 12px;
  border: 1px solid #ced4da;
  border-radius: 8px;
  font-size: 16px;
  color: #333;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

.search-input:focus {
  border-color: #007bff;
  outline: none;
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.25);
}

/* Filter Select */
.filter-select {
  padding: 12px;
  border: 1px solid #ced4da;
  border-radius: 8px;
  font-size: 16px;
  color: #333;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

.filter-select:focus {
  border-color: #007bff;
  outline: none;
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.25);
}

/* Buttons */
.buttons-container {
  display: flex;
  justify-content: flex-start;
  gap: 15px;
}

.action-button {
  padding: 12px 25px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  background-color: #007bff;
  color: white;
  font-size: 16px;
  font-weight: 500;
  transition: all 0.3s ease;
}

.action-button:hover, .action-button:focus {
  background-color: #0056b3;
  box-shadow: 0 4px 8px rgba(0, 123, 255, 0.2);
  transform: translateY(-2px);
}

.action-button:active {
  transform: translateY(0);
}

/* Loading indicator */
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.loading-indicator {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #007bff;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin: 20px auto;
}

/* Fade-in animation */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.fade-in {
  animation: fadeIn 0.5s ease-in;
}

/* Media Queries */
@media (max-width: 1200px) {
  .main-content {
    flex-direction: column;
  }

  .left-part, .controls-section {
    width: 100%;
    max-height: none;
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
    width: 100%;
  }

  .action-button {
    width: 100%;
  }

  .buttons-container {
    flex-direction: column;
  }

  .visualization-iframe {
    height: 45vh;
  }

  .abstract-textarea, .response-textarea, .status-textarea {
    font-size: 14px;
  }

  .action-button {
    padding: 10px 20px;
    font-size: 14px;
  }
}
/* Repositories Section Styling */
.repositories-section {
  padding: 20px;
  background-color: #f9fafb;
  border-radius: 8px;
  margin-top: 20px;
}

.repositories-section h2 {
  margin-bottom: 20px;
  font-size: 1.5em;
  color: #333;
  text-align: center;
}

.repositories-container {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}

.repo-button {
  flex: 1 1 150px;
  min-width: 120px;
  padding: 12px 16px;
  background-color: #e5e7eb;
  color: #1f2937;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 1em;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: background-color 0.3s, transform 0.2s, box-shadow 0.3s;
}

.repo-button:hover {
  background-color: #d1d5db;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.repo-button.active {
  background-color: #3b82f6;
  color: #fff;
  transform: scale(1.05);
  box-shadow: 0 6px 12px rgba(59, 130, 246, 0.4);
}

.repo-button:focus {
  outline: 3px solid #3b82f6;
  outline-offset: 2px;
}

@media (max-width: 768px) {
  .repo-button {
    flex: 1 1 45%;
  }
}

@media (max-width: 480px) {
  .repo-button {
    flex: 1 1 100%;
  }
}

.repositories-section {
  padding: 20px;
  background-color: #f9fafb;
  border-radius: 8px;
  margin-top: 20px;
}

.repositories-section-section h2 {
  margin-bottom: 20px;
  font-size: 1.5em;
  color: #333;
  text-align: center;
}

.repositories-section .form-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 15px;
}

.repositories-section label {
  font-weight: 600;
  color: #1f2937;
}

.repositories-section .select-input,
.repositories-section .file-input {
  padding: 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 1em;
  background-color: #fff;
  transition: border-color 0.3s, box-shadow 0.3s;
}

.repositories-section .select-input:focus,
.repositories-section .file-input:focus {
  border-color: #3b82f6;
  outline: none;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25);
}

.repositories-section .action-button {
  padding: 12px 20px;
  background-color: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 1em;
  cursor: pointer;
  transition: background-color 0.2s, transform 0.2s, box-shadow 0.3s;
}

.repositories-section .action-button:hover:not(:disabled) {
  background-color: #2563eb;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(37, 99, 235, 0.3);
}

.repositories-section .action-button:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
}

.repositories-section .download-section {
  text-align: center;
  margin-bottom: 15px;
}

.repositories-section .download-link {
  display: inline-block;
  padding: 10px 15px;
  background-color: #10b981;
  color: #fff;
  border-radius: 6px;
  text-decoration: none;
  transition: background-color 0.3s, transform 0.2s, box-shadow 0.3s;
}

.repositories-section .download-link:hover {
  background-color: #059669;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(16, 185, 129, 0.3);
}

.repositories-section .status-message {
  text-align: center;
  color: #065f46;
  font-weight: 500;
  margin-top: 10px;
}

.repositories-section .upload-status {
  text-align: center;
  padding: 10px;
  background-color: #d1fae5;
  color: #065f46;
  border-radius: 6px;
  margin-top: 10px;
}
</style>
