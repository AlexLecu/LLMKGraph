<script setup lang="ts">
import { ref } from 'vue';

const links = [
  { to: '/', label: 'Graph', icon: '◉' },
  { to: '/chat', label: 'Chat', icon: '💬' },
  { to: '/evaluation', label: 'Evaluation', icon: '📊' },
];

const open = ref(false);
</script>

<template>
  <nav class="sidebar" :class="{ open }">
    <div class="brand">
      <span class="brand-mark">👁️</span>
      <span class="brand-name">LLMKGraph</span>
      <button class="burger" type="button" aria-label="Toggle navigation" @click="open = !open">☰</button>
    </div>
    <div class="links">
      <RouterLink
        v-for="l in links"
        :key="l.to"
        :to="l.to"
        class="link"
        active-class="active"
        @click="open = false"
      >
        <span class="icon" aria-hidden="true">{{ l.icon }}</span>
        {{ l.label }}
      </RouterLink>
    </div>
    <div class="foot">
      <a href="https://github.com/AlexLecu/LLMKGraph" target="_blank" rel="noopener">GitHub ↗</a>
    </div>
  </nav>
</template>

<style scoped>
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  width: var(--sidebar-width);
  height: 100vh;
  background: var(--sidebar-bg);
  color: var(--sidebar-text);
  display: flex;
  flex-direction: column;
  padding: 18px 14px;
  z-index: 20;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  color: #fff;
  font-size: 16px;
  padding: 4px 6px 18px;
}

.brand-mark {
  font-size: 18px;
}

.burger {
  display: none;
  margin-left: auto;
  background: transparent;
  border: 0;
  color: #fff;
  font-size: 20px;
  cursor: pointer;
}

.links {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  color: var(--sidebar-text);
  font-weight: 500;
  text-decoration: none;
  transition: background-color 0.15s, color 0.15s;
}

.link:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  text-decoration: none;
}

.link.active {
  background: var(--sidebar-active);
  color: #fff;
}

.icon {
  width: 20px;
  text-align: center;
}

.foot {
  margin-top: auto;
  font-size: 13px;
  padding: 6px;
}

.foot a {
  color: var(--sidebar-text);
}

@media (max-width: 1023px) {
  .sidebar {
    width: 100%;
    height: auto;
    padding: 10px 14px;
  }

  .brand {
    padding-bottom: 0;
  }

  .burger {
    display: block;
  }

  .links,
  .foot {
    display: none;
  }

  .sidebar.open .links {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 6px;
    padding-top: 10px;
  }
}
</style>
