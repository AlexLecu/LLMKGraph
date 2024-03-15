<script setup lang="ts">
import TheWelcome from '../components/TheWelcome.vue';
import {ref} from 'vue';
const abstract = ref('');
const responseText = ref('')
const statusText = ref('')

function showRelations(){
  console.log("abstract", abstract.value);

  fetch('/api/showRelations', {
      method: 'POST',
      body: JSON.stringify(abstract.value),
      }
    )
    .then((response) => response.json())
    .then((response)=> {
      console.log("data", response)
      responseText.value = JSON.stringify(response, null, 2)
    })

}

function addRelations(){
  fetch('/api/addRelations', {
      method: 'POST',
  })
  .then((response) => response.json())
  .then((response) => {
    console.log("data", response)
    statusText.value = JSON.stringify(response, null, 2)
  })

}
</script>

<template>
  <div class="app-container">
    <div class="sidebar">
      <router-link to="/" class="sidebar-link">Home</router-link>
      <router-link to="/chat" class="sidebar-link">Chat</router-link>
    </div>
    <div class="iframe-container">
      <iframe src="http://localhost:7200/graphs-visualizations?uri=http:%2F%2Fwww.semanticweb.org%2Flecualexandru%2Fontologies%2F2024%2F1%2Funtitled-ontology-6%23AMD&embedded" title="description" class="visualization-iframe"></iframe>
    </div>
    <div class="controls-container"> 
      <input v-model="abstract" placeholder="Enter abstract" class="input-field">
      <div class="buttons-container">
        <button @click="showRelations" class="action-button">Show relations</button>
        <button @click="addRelations" class="action-button">Add relations</button>
      </div>
      <textarea v-model="responseText" placeholder="Relations" readonly class="response-textarea"></textarea>
      <textarea v-model="statusText" readonly class="status-textarea"></textarea>
    </div>
  </div>
</template>

<style>
.app-container {
  display: flex;
  height: 100vh; /* Use the full height of the viewport */
  width: 100vw;
  gap: 20px;
  padding-left: 0; /* Ensure no padding is pushing content to the right */
  align-items: flex-start; /* Align items to the start of the flex-direction which is horizontal here */
}
.sidebar {
  width: 150px; /* Adjust based on your preference */
  background-color: #181818; /* Example background color */
  height: 100%; /* Make the sidebar full height */
  padding-top: 20px; /* Adjust based on your preference */
  box-sizing: border-box;
}

.sidebar-link {
  display: block;
  padding: 10px 20px; /* Adjust based on your preference */
  text-decoration: none;
  color: #d1d1d1; /* Light gray color */
  margin-bottom: 10px; /* Spacing between links */
}

.sidebar-link:hover {
  background-color: #ddd; /* Example hover effect */
  color: #ffffff; /* Change text color on hover to white for better visibility */
}
.visualization-iframe {
  flex-grow: 1; /* Allow the iframe to grow to fill available space */
  width: 60vw; /* Use viewport width units to set width directly */
  height: 90vh; /* Adjust height as needed */
  border: 1px solid #ccc;
  border-radius: 8px;
  overflow: auto;
  resize: both;
}

.controls-container {
  flex-basis: 30%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.status-textarea {
  color: green; 
  height: 100px; 
  width: 100%; 
  padding: 10px;
  border: none;
  resize: none;
  background-color: #181818;
}

.input-field, .response-textarea {
  padding: 50px;
  border: 1px solid #ccc;
  border-radius: 8px;
  width: 100%;
  box-sizing: border-box;
}

.response-textarea {
  height: 200px; /* Adjust based on your preference */
  resize: vertical;
}

.action-button {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  background-color: #007bff;
  color: white;
  transition: background-color 0.3s ease;
}

.action-button:hover {
  background-color: #0056b3;
}

.buttons-container {
  display: flex;
  gap: 10px;
}

@media (max-width: 1024px; margin: 0) {
  .app-container {
    flex-direction: column;
  }

  .iframe-container, .controls-container {
    flex-basis: auto;
    width: 100%;
  }

  .visualization-iframe {
    height: 50vh; /* Adjust for smaller screens */
  }
}
</style>

