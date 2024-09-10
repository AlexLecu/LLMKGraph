<script setup lang="ts">
import { ref } from 'vue';
import 'vue-loading-overlay/dist/css/index.css';
import { useLoading } from 'vue-loading-overlay';

const abstract = ref('');
const responseText = ref('');
const statusText = ref('');
const validationError = ref('');
const $loading = useLoading();
let statusTimeout = null;

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
</script>

<template>
  <div class="app-container">
    <aside class="sidebar">
      <router-link to="/" class="sidebar-link">Home</router-link>
      <router-link to="/chat" class="sidebar-link">Chat</router-link>
    </aside>

    <div class="main-content">
      <section class="iframe-section">
        <h2 class="section-title">Knowledge Graph Visualization</h2>
        <iframe
          src="http://localhost:7200/graphs-visualizations?uri=http:%2F%2Fwww.semanticweb.org%2Flecualexandru%2Fontologies%2F2024%2F1%2Funtitled-ontology-6%23AMD&embedded"
          title="Knowledge Graph Visualization"
          class="visualization-iframe">
        </iframe>
      </section>

      <section class="controls-section">
        <h2 class="section-title">Knowledge Graph Operations</h2>

        <div class="input-area">
          <label for="abstract-input" class="input-label">Enter Abstract</label>
          <textarea v-model="abstract" id="abstract-input" placeholder="Enter abstract" class="abstract-textarea"></textarea>
        </div>

        <div class="buttons-container">
          <button @click="showRelations" class="action-button" :disabled="isLoading">Show Relations</button>
          <button @click="addRelations" class="action-button" :disabled="isLoading">Add Relations</button>
          <button @click="reasonKg" class="action-button" :disabled="isLoading">Reason KG</button>
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
  overflow-x: hidden; /* Prevent horizontal overflow */
}

/* General App Container */
.app-container {
  display: flex;
  min-height: 100vh;
  width: 100vw;
  background-color: #f7f9fc;
  font-family: 'Roboto', sans-serif;
  overflow-x: hidden; /* Ensure no horizontal scrolling */
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

.sidebar-link:hover {
  background-color: #007bff;
  color: #ffffff;
  transform: scale(1.05);
  box-shadow: 0 4px 8px rgba(0, 123, 255, 0.2);
}

/* Main Content Area */
.main-content {
  margin-left: 200px; /* Offset the content by the width of the sidebar */
  display: flex;
  flex-grow: 1;
  gap: 20px;
  padding: 20px;
  background-color: #f7f9fc;
  overflow-x: hidden;
  width: calc(100% - 200px); /* Ensure the content fits within the viewport */
}

/* Visualization Section */
.iframe-section {
  flex-grow: 2;
  padding: 20px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.visualization-iframe {
  width: 100%;
  height: 80vh;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* Controls Section */
.controls-section {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background-color: #f0f2f5;
  padding: 25px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

/* Fix for the section title text color */
.section-title {
  font-size: 24px;
  font-weight: bold;
  color: #333; /* Darker text for better visibility */
  margin-bottom: 15px;
}

/* Input and Button Areas */
.input-area, .textarea-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.input-label {
  font-size: 16px;
  font-weight: 500;
  color: #333; /* Darker color for better visibility */
}

/* Abstract Textarea */
.abstract-textarea {
  height: 300px;
  padding: 15px;
  border: 1px solid #ced4da;
  border-radius: 8px;
  background-color: #ffffff;
  font-size: 16px;
  color: #333; /* Darker color for text inside the textarea */
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
  color: #333; /* Darker color for text in the textareas */
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

/* Buttons */
.buttons-container {
  display: flex;
  justify-content: space-between;
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
  .app-container {
    flex-direction: column;
  }

  .visualization-iframe {
    height: 50vh;
  }
}

@media (max-width: 768px) {
  .main-content {
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
</style>
