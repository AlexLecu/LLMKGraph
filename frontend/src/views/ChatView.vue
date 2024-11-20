<script setup lang="ts"></script>

<template>
  <div class="app-container">
    <aside class="sidebar">
      <router-link to="/" class="sidebar-link">Home</router-link>
      <router-link to="/chat" class="sidebar-link">Chat</router-link>
      <router-link to="/evaluation" class="sidebar-link">Evaluation</router-link>
    </aside>

    <div class="chat-content">
      <iframe ref="myIframe" src="http://localhost:8501/?embed=true&embed_options=show_toolbar"></iframe>
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

.app-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  background-color: #f7f9fc;
  font-family: 'Roboto', sans-serif;
}

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
  top: 0;
  left: 0;
  z-index: 1;
}

.sidebar-link {
  display: block;
  padding: 15px 20px;
  margin-bottom: 15px;
  font-size: 16px;
  color: #d1d1d1;
  background-color: #495057;
  border-radius: 6px;
  text-decoration: none;
  transition: background-color 0.3s ease, transform 0.2s;
}

.sidebar-link:hover {
  background-color: #007bff;
  color: white;
  transform: scale(1.05);
  box-shadow: 0 4px 8px rgba(0, 123, 255, 0.2);
}

.chat-content {
  margin-left: 200px; /* Aligns content next to the sidebar */
  flex-grow: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  overflow: hidden; /* Prevents overflow in the content */
  padding: 0;
}

iframe {
  width: 100%; /* Make iframe take the full remaining width */
  height: 100%; /* Make iframe take the full height */
  border: none; /* Remove default iframe borders */
  margin: 0;
  padding: 0;
}

/* Media Queries */
@media (max-width: 1024px) {
  .app-container {
    flex-direction: column;
  }

  .chat-content {
    margin-left: 0;
    height: calc(100vh - 200px); /* Adjust height based on sidebar */
  }
}

@media (max-width: 768px) {
  .sidebar {
    width: 100%;
    height: auto;
    padding: 10px;
  }

  .sidebar-link {
    font-size: 14px;
  }

  iframe {
    height: 50vh; /* Adjust iframe height for smaller screens */
  }
}
</style>
