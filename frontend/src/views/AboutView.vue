

<script>
/*
export default {
  mounted() {
    this.makeFullScreen();
  },
  methods: {
    makeFullScreen() {
      const iframe = this.$refs.myIframe;
      iframe.style.position = 'fixed';
      iframe.style.top = '0';
      iframe.style.left = '0';
      iframe.style.width = '100vw';
      iframe.style.height = '100vh';
      iframe.style.zIndex = '1000'; // Ensure it's above other content
      iframe.style.border = 'none'; // Optional: remove the border for a cleaner look
    }
  }
}
*/
</script>

<template>
  <div class="app-container">
    <div class="sidebar">
      <router-link to="/" class="sidebar-link">Home</router-link>
      <router-link to="/chat" class="sidebar-link">Chat</router-link>
    </div>
    <div class="chat-content">
      <iframe ref="myIframe" src="http://localhost:8501/?embed=true&embed_options=show_toolbar"></iframe>
    </div>
  </div>
</template>

<style>
.app-container {
  display: flex;
  height: 100vh; /* Make the container full height */
  width: 100vw; /* Make the container full width */
  overflow: hidden; /* Prevents scrolling if the content overflows */
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

.chat-content {
  flex-grow: 1; /* Allows the chat content to fill the remaining space */
  height: 100vh; /* Make it full height */
  overflow: hidden; /* Prevents scrolling within the chat content area */
}

iframe {
  width: 100%; /* Full width of its container */
  height: 100%; /* Full height of its container */
  border: none; /* Removes the default iframe border */
}
</style>

