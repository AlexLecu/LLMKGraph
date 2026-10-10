<script setup lang="ts">
import AppSidebar from '@/components/AppSidebar.vue';
import EmbeddedApp from '@/components/EmbeddedApp.vue';
import { CHAT_URL } from '@/config';

const startHint = `cd backend/weaviate_rag
chainlit run chatbot.py -w        # serves http://localhost:8000`;
</script>

<template>
  <div class="app-shell">
    <AppSidebar />
    <main class="page">
      <EmbeddedApp :url="CHAT_URL" name="AMD chat assistant" env-var="VITE_CHAT_URL" :start-hint="startHint" />
    </main>
  </div>
</template>
