<script setup lang="ts">
import { ref } from 'vue';
import 'vue-loading-overlay/dist/css/index.css';
import { useLoading } from 'vue-loading-overlay';

const abstract = ref('');
const responseText = ref('');
const statusText = ref('');
const validationError = ref('');
const $loading = useLoading();
let statusTimeout: number | null = null;

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

  fetch('http://localhost:5555/api/addRelations', {
    method: 'POST',
    body: JSON.stringify(JSON.parse(responseText.value)),
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

  fetch('http://localhost:5555/api/reason', {
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

const queryText = ref('');
const filterType = ref('');
const results = ref([]);
const cyElements = ref([]);

function extractMainComponent(uri: string): string {
  // Split the URI at '#' and return the last part
  return uri.split('#').pop() || uri;
}

function processSearchResults(data: any[]) {
  // Assuming the response is an array of objects with subject, predicate, and object
  return data.map(result => ({
    subject: extractMainComponent(result.subject),
    predicate: extractMainComponent(result.predicate),
    object: extractMainComponent(result.object),
  }));
}

function performSearch() {
  if (!queryText.value.trim()) {
    validationError.value = 'Please enter a search term.';
    return;
  }

  validationError.value = '';
  const loader = $loading.show();
  const params = new URLSearchParams();
  params.append('q', queryText.value);
  if (filterType.value) {
    params.append('type', filterType.value);
  }

  fetch(`http://localhost:5555/api/search?${params.toString()}`)
    .then((response) => response.json())
    .then((data) => {
      // Process the results to extract main components
      results.value = processSearchResults(data);

      if (results.value.length === 0) {
        statusText.value = 'No results found.';
      } else {
        statusText.value = 'Search completed successfully!';
      }
    })
    .catch((error) => {
      console.error('Error:', error);
      statusText.value = 'Error during search.';
    })
    .finally(() => {
      loader.hide();
      clearStatusTextAfterDelay();
    });
}
</script>

<template>
  <div class="app-container">
    <aside class="sidebar">
      <router-link to="/" class="sidebar-link">Home</router-link>
      <router-link to="/chat" class="sidebar-link">Chat</router-link>
    </aside>

    <div class="main-content">
      <!-- Left Part: Iframe and Search Section -->
      <div class="left-part">
        <section class="iframe-section">
          <h2 class="section-title">Knowledge Graph Visualization</h2>
          <iframe
            src="http://localhost:7200/graphs-visualizations?uri=http:%2F%2Fwww.semanticweb.org%2Flecualexandru%2Fontologies%2F2024%2F1%2Funtitled-ontology-6%23AMD&embedded"
            title="Knowledge Graph Visualization"
            class="visualization-iframe">
          </iframe>
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
          <div v-if="validationError" class="validation-error">
            <p>{{ validationError }}</p>
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
          <label for="abstract-input" class="input-label">Enter Abstract</label>
          <textarea v-model="abstract" id="abstract-input" placeholder="Enter abstract" class="abstract-textarea"></textarea>
        </div>

        <div class="buttons-container">
          <button @click="showRelations" class="action-button">Show Relations</button>
          <button @click="addRelations" class="action-button">Add Relations</button>
          <button @click="reasonKg" class="action-button">Reason KG</button>
        </div>

        <div v-if="validationError" class="validation-error">
          <p>{{ validationError }}</p>
        </div>

        <div class="output-area">
          <div class="textarea-container">
            <label for="response-text" class="input-label">Relations Output (Editable)</label>
            <textarea v-model="responseText" id="response-text" placeholder="Relations" class="response-textarea"></textarea>
          </div>
          <div class="textarea-container">
            <label for="status-text" class="input-label">Status</label>
            <textarea v-model="statusText" id="status-text" readonly class="status-textarea"></textarea>
          </div>
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

/* General App Container */
.app-container {
  display: flex;
  min-height: 100vh;
  width: 100vw;
  background-color: #f7f9fc;
  font-family: 'Roboto', sans-serif;
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
}

.sidebar-link {
  display: block;
  padding: 15px 20px;
  margin-bottom: 15px;
  font-size: 16px;
  color: #fff;
  background-color: #495057;
  border-radius: 6px;
  transition: background-color 0.3s ease, transform 0.2s;
}

.validation-error {
  color: red;
  font-weight: bold;
  margin-top: 10px;
}

.sidebar-link:hover {
  background-color: #007bff;
  color: #ffffff;
  transform: scale(1.05);
  box-shadow: 0 4px 8px rgba(0, 123, 255, 0.2);
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
}

/* Left Part: Iframe and Search Section */
.left-part {
  width: 50%;
  display: flex;
  flex-direction: column;
  gap: 20px;
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
}

/* Visualization Section */
.iframe-section {
  flex-grow: 1;
  background-color: #fff;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
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
}

.results-section {
  margin-top: 20px;
}

.results-table-container {
  max-height: 300px;
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

/* Fix for the section title text color */
.section-title {
  font-size: 24px;
  font-weight: bold;
  color: #333;
  margin-bottom: 15px;
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
  transition: border-color 0.3s ease;
}

.abstract-textarea:focus {
  border-color: #007bff;
  outline: none;
  box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
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
}

.response-textarea {
  height: 250px;
  background-color: #f8f9fa;
}

.status-textarea {
  height: 120px;
  background-color: #eaf5ea;
  color: #28a745;
}

/* Search Input */
.search-input {
  padding: 12px;
  border: 1px solid #ced4da;
  border-radius: 8px;
  font-size: 16px;
  color: #333;
}

.search-input:focus {
  border-color: #007bff;
  outline: none;
}

/* Filter Select */
.filter-select {
  padding: 12px;
  border: 1px solid #ced4da;
  border-radius: 8px;
  font-size: 16px;
  color: #333;
}

.filter-select:focus {
  border-color: #007bff;
  outline: none;
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
  transition: background-color 0.3s ease, box-shadow 0.2s ease;
}

.action-button:hover {
  background-color: #0056b3;
  box-shadow: 0 4px 8px rgba(0, 123, 255, 0.2);
}

/* Media Queries */
@media (max-width: 1024px) {
  .main-content {
    flex-direction: column;
  }

  .left-part, .controls-section {
    width: 100%;
  }

  .visualization-iframe {
    height: 50vh;
  }
}

@media (max-width: 768px) {
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
</style>
