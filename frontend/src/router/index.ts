import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
      meta: { title: 'AMD Knowledge Graph' }
    },
    {
      path: '/chat',
      name: 'chat',
      // route level code-splitting: lazy-loaded when the route is visited
      component: () => import('../views/ChatView.vue'),
      meta: { title: 'AMD Research Assistant' }
    },
    {
      path: '/evaluation',
      name: 'evaluation',
      component: () => import('../views/EvaluationView.vue'),
      meta: { title: 'LLM Comparison' }
    }
  ]
})

// Browser tab: "<page> · LLMKGraph"
router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · LLMKGraph` : 'LLMKGraph'
})

export default router
