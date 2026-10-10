<script setup lang="ts">
import { onMounted, ref } from 'vue';

const props = defineProps<{
  /** URL of the external app to embed. */
  url: string;
  /** Human-readable name shown in the toolbar and the fallback. */
  name: string;
  /** Command that starts the service locally, shown when it is unreachable. */
  startHint: string;
  /** Vite env var that overrides the URL, shown in the fallback. */
  envVar: string;
}>();

type Status = 'checking' | 'up' | 'down';
const status = ref<Status>('checking');

async function probe() {
  status.value = 'checking';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    // A cross-origin fetch in no-cors mode resolves (opaque response) when the
    // server answers at all and rejects when the connection is refused, which
    // is exactly the signal we need to decide between iframe and fallback.
    await fetch(props.url, { mode: 'no-cors', cache: 'no-store', signal: controller.signal });
    status.value = 'up';
  } catch {
    status.value = 'down';
  } finally {
    clearTimeout(timer);
  }
}

onMounted(probe);
</script>

<template>
  <div class="embed-frame">
    <div class="embed-bar">
      <span class="muted">
        {{ name }} ·
        <code class="inline">{{ url }}</code>
      </span>
      <div class="btn-row">
        <button class="btn btn-secondary btn-sm" type="button" @click="probe">Reload</button>
        <a class="btn btn-secondary btn-sm" :href="url" target="_blank" rel="noopener">Open in new tab ↗</a>
      </div>
    </div>

    <div class="embed-body">
      <iframe v-if="status === 'up'" :src="url" :title="name" allow="clipboard-write"></iframe>

      <div v-else-if="status === 'checking'" class="embed-fallback">
        <p>Connecting to {{ name }}…</p>
      </div>

      <div v-else class="embed-fallback">
        <h2>{{ name }} is not running</h2>
        <p>
          Nothing answered at <code class="inline">{{ url }}</code>. Start the service locally,
          or point the frontend at a deployed instance with
          <code class="inline">{{ envVar }}</code> in <code class="inline">frontend/.env.local</code>.
        </p>
        <pre>{{ startHint }}</pre>
        <button class="btn btn-primary" type="button" @click="probe">Try again</button>
      </div>
    </div>
  </div>
</template>
