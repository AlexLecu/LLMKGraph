<script setup lang="ts">
import AppSidebar from '@/components/AppSidebar.vue';
import EmbeddedApp from '@/components/EmbeddedApp.vue';
import { EVAL_URL } from '@/config';

const startHint = `cd backend
streamlit run streamlit/streamlit_app_evaluation.py --server.port 8502`;
</script>

<template>
  <div class="app-shell">
    <AppSidebar />
    <main class="page">
      <EmbeddedApp :url="EVAL_URL" name="Graph comparison (Streamlit)" env-var="VITE_EVAL_URL" :start-hint="startHint" />
    </main>
  </div>
</template>
