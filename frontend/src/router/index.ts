import { createRouter, createWebHistory } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: DefaultLayout,
      children: [
        { path: '', redirect: '/search' },
        { path: 'search', name: 'search', component: () => import('@/views/SearchView.vue'), meta: { title: '岗位搜索' } },
        { path: 'applications', name: 'applications', component: () => import('@/views/ApplicationsView.vue'), meta: { title: '投递记录' } },
        { path: 'chat', name: 'chat', component: () => import('@/views/ChatView.vue'), meta: { title: '聊天管理' } },
        { path: 'wechat', name: 'wechat', component: () => import('@/views/WechatView.vue'), meta: { title: '微信记录' } },
        { path: 'resume', name: 'resume', component: () => import('@/views/ResumeView.vue'), meta: { title: '简历优化' } },
        { path: 'agents', name: 'agents', component: () => import('@/views/AgentsView.vue'), meta: { title: 'Agent 配置' } },
        { path: 'settings', name: 'settings', component: () => import('@/views/SettingsView.vue'), meta: { title: '系统设置' } },
      ],
    },
  ],
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} - BOSS 自动化` : 'BOSS 自动化'
})

export default router
