<script setup lang="ts">
// AMD research assistant. Talks to the chat API (backend/weaviate_rag/chat_api.py):
// every question is answered from relations retrieved from the knowledge graph.
import { computed, nextTick, onMounted, ref } from 'vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import AppSidebar from '@/components/AppSidebar.vue';
import { CHAT_API_URL } from '@/config';

interface Turn {
  role: 'user' | 'assistant';
  content: string;
  error?: boolean;
}

const MAX_CHARS = 500; // the API refuses longer questions
const STARTERS = [
  { title: 'Early signs of AMD', text: 'What subtle vision changes might indicate early stage AMD?' },
  { title: 'Emerging treatments', text: 'What emerging treatments show promise for dry AMD?' },
  { title: 'Wet AMD therapies', text: 'How do anti-VEGF injections compare to emerging gene therapies for wet AMD?' },
  { title: 'Risk factors', text: 'What are the main risk factors for AMD?' },
];

const turns = ref<Turn[]>([]);
const draft = ref('');
const busy = ref(false);
const phase = ref<'searching' | 'writing' | ''>('');
const models = ref<string[]>([]);
const model = ref('');
const scroller = ref<HTMLElement | null>(null);
const input = ref<HTMLTextAreaElement | null>(null);

const tooLong = computed(() => draft.value.length > MAX_CHARS);
const canSend = computed(() => !busy.value && draft.value.trim().length > 0 && !tooLong.value);

onMounted(async () => {
  try {
    const r = await fetch(`${CHAT_API_URL}/api/chat/models`);
    const data = await r.json();
    models.value = data.models ?? [];
    model.value = data.default ?? models.value[0] ?? '';
  } catch {
    /* the first question will report the error */
  }
  input.value?.focus();
});

function render(md: string) {
  return DOMPurify.sanitize(marked.parse(md, { async: false, breaks: true }) as string);
}

async function scrollDown() {
  await nextTick();
  scroller.value?.scrollTo({ top: scroller.value.scrollHeight, behavior: 'smooth' });
}

// "openai/gpt-oss-120b" -> "GPT-OSS 120B"
function prettyModel(m: string) {
  return m.replace(/^openai\//, '').replace(/^gpt-oss-(\w+)$/i, (_, size: string) => `GPT-OSS ${size.toUpperCase()}`);
}

async function send(text = draft.value) {
  const question = text.trim();
  if (!question || busy.value || question.length > MAX_CHARS) return;
  draft.value = '';
  turns.value.push({ role: 'user', content: question });
  // only the clean turns go back to the model
  const history = turns.value.filter((t) => !t.error).map(({ role, content }) => ({ role, content }));
  turns.value.push({ role: 'assistant', content: '' });
  const live = turns.value[turns.value.length - 1]!; // reactive proxy: updates render as tokens arrive
  busy.value = true;
  phase.value = 'searching';
  scrollDown();

  try {
    const r = await fetch(`${CHAT_API_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: history, model: model.value || undefined }),
    });
    if (!r.ok || !r.body) {
      let detail = `The chat service answered ${r.status}.`;
      try {
        detail = (await r.json()).detail ?? detail;
      } catch {
        /* not JSON */
      }
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      phase.value = 'writing';
      live.content += decoder.decode(value, { stream: true });
      scrollDown();
    }
    live.content += decoder.decode();
    if (!live.content.trim()) throw new Error('The model returned an empty answer. Please try again.');
  } catch (e: any) {
    live.error = true;
    live.content = e?.message?.includes('fetch') || e instanceof TypeError
      ? 'The chat service is not reachable right now. Please try again in a moment.'
      : e?.message ?? String(e);
  } finally {
    busy.value = false;
    phase.value = '';
    scrollDown();
    input.value?.focus();
  }
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    send();
  }
}

function newChat() {
  if (busy.value) return;
  turns.value = [];
  input.value?.focus();
}
</script>

<template>
  <div class="app-shell">
    <AppSidebar />
    <main class="page chat-page">
      <header class="chat-head">
        <div>
          <h1>AMD research assistant</h1>
          <p class="muted">Answers are written only from relations retrieved from the AMD knowledge graph.</p>
        </div>
        <div class="controls">
          <label v-if="models.length > 1" class="model">
            <span class="muted">Model</span>
            <select v-model="model" class="select" :disabled="busy">
              <option v-for="m in models" :key="m" :value="m">{{ prettyModel(m) }}</option>
            </select>
          </label>
          <button class="btn btn-secondary btn-sm" type="button" :disabled="busy || !turns.length" @click="newChat">
            New chat
          </button>
        </div>
      </header>

      <section ref="scroller" class="thread" aria-live="polite">
        <div class="column">
        <div v-if="!turns.length" class="empty">
          <div class="empty-mark" aria-hidden="true">👁️</div>
          <h2>Ask about age-related macular degeneration</h2>
          <p class="muted">Risk factors, symptoms, diagnosis, treatments… Try one of these:</p>
          <div class="starters">
            <button v-for="s in STARTERS" :key="s.title" type="button" class="starter" @click="send(s.text)">
              <strong>{{ s.title }}</strong>
              <span>{{ s.text }}</span>
            </button>
          </div>
        </div>

        <template v-for="(t, i) in turns" :key="i">
          <div v-if="t.role === 'user'" class="turn user">
            <div class="bubble">{{ t.content }}</div>
          </div>
          <div v-else class="turn assistant">
            <div class="avatar" aria-hidden="true">👁️</div>
            <div class="answer" :class="{ error: t.error }">
              <div v-if="!t.content && busy && i === turns.length - 1" class="status">
                <span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>
                {{ phase === 'searching' ? 'Searching the knowledge graph…' : 'Writing…' }}
              </div>
              <div v-else-if="t.error" class="msg msg-error">{{ t.content }}</div>
              <div v-else class="md" v-html="render(t.content)"></div>
            </div>
          </div>
        </template>
        </div>
      </section>

      <form class="composer card" @submit.prevent="send()">
        <textarea
          ref="input"
          v-model="draft"
          class="textarea"
          rows="2"
          :maxlength="MAX_CHARS + 200"
          placeholder="Ask a question about AMD…  (Enter to send, Shift+Enter for a new line)"
          aria-label="Your question"
          @keydown="onKey"
        ></textarea>
        <div class="composer-bar">
          <span class="muted" :class="{ over: tooLong }">{{ draft.length }} / {{ MAX_CHARS }}</span>
          <span class="muted disclaimer">Research information only, not medical advice.</span>
          <button class="btn btn-primary" type="submit" :disabled="!canSend">Send</button>
        </div>
      </form>
    </main>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100vh;
  /* the conversation and the composer share one centred reading column */
  --column: 880px;
}

@media (max-width: 1023px) {
  .chat-page {
    height: 100dvh;
  }
}

.chat-head {
  width: 100%;
  max-width: calc(var(--column) + 48px);
  margin: 0 auto;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.chat-head h1 {
  font-size: 24px;
}

.controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.model {
  display: flex;
  align-items: center;
  gap: 6px;
}

.model .select {
  width: auto;
  padding: 6px 8px;
}

/* No frame around the conversation: just the centred column, like chat apps */
.thread {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  padding: 12px 24px 24px;
}

.column {
  width: 100%;
  max-width: var(--column);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.empty {
  margin: auto;
  text-align: center;
  max-width: 720px;
  padding: 12px 0;
}

.empty-mark {
  font-size: 34px;
}

.empty h2 {
  font-size: 19px;
  margin: 6px 0 4px;
}

.starters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
  margin-top: 16px;
  text-align: left;
}

.starter {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  font: inherit;
  font-size: 13.5px;
  cursor: pointer;
  transition: border-color 0.15s, background-color 0.15s;
}

.starter:hover {
  border-color: var(--primary);
  background: var(--primary-soft);
}

.starter span {
  color: var(--text-muted);
}

.turn {
  display: flex;
  gap: 10px;
}

.turn.user {
  justify-content: flex-end;
}

.bubble {
  max-width: min(75%, 640px);
  background: var(--primary);
  color: #fff;
  padding: 10px 14px;
  border-radius: 14px 14px 4px 14px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 14.5px;
}

.avatar {
  flex: none;
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--surface-muted);
  border: 1px solid var(--border);
  font-size: 15px;
}

.answer {
  flex: 1;
  min-width: 0;
  font-size: 14.5px;
  line-height: 1.6;
  color: var(--text);
}

.status {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-muted);
  font-size: 13.5px;
  padding-top: 5px;
}

.dots {
  display: inline-flex;
  gap: 4px;
}

.dots i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: blink 1.2s infinite ease-in-out;
}

.dots i:nth-child(2) {
  animation-delay: 0.2s;
}

.dots i:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes blink {
  0%, 80%, 100% { opacity: 0.25; }
  40% { opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .dots i {
    animation: none;
    opacity: 0.6;
  }
}

.md :deep(p) {
  margin: 0 0 10px;
}

.md :deep(ul),
.md :deep(ol) {
  margin: 0 0 10px;
  padding-left: 22px;
}

.md :deep(li) {
  margin: 3px 0;
}

.md :deep(strong) {
  color: var(--heading);
}

.md :deep(code) {
  font-family: var(--font-mono);
  font-size: 12.5px;
  background: var(--surface-muted);
  padding: 1px 4px;
  border-radius: 4px;
}

.md :deep(:last-child) {
  margin-bottom: 0;
}

.composer {
  padding: 10px 12px;
  width: 100%;
  max-width: calc(var(--column) + 48px);
  margin: 0 auto;
}

.composer .textarea {
  resize: none;
  border: 0;
  background: transparent;
  padding: 4px 2px;
  box-shadow: none;
  font-size: 14.5px;
}

.composer .textarea:focus {
  outline: none;
}

.composer:focus-within {
  border-color: var(--primary);
}

.composer-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.disclaimer {
  margin-left: auto;
}

.over {
  color: var(--danger);
  font-weight: 600;
}

@media (max-width: 600px) {
  .thread {
    padding: 14px;
  }

  .disclaimer {
    display: none;
  }

  .composer-bar .btn {
    margin-left: auto;
  }

  .bubble {
    max-width: 88%;
  }
}
</style>
