import { createRouter, createWebHistory } from 'vue-router';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/tasks' },
    {
      path: '/login',
      name: 'login',
      meta: { public: true },
      component: () => import('../pages/LoginPage.vue'),
    },
    { path: '/tasks', name: 'tasks', component: () => import('../pages/TasksCatalogPage.vue') },
    { path: '/lobbies', name: 'lobbies', component: () => import('../pages/LobbiesPage.vue') },
    { path: '/games', name: 'games', component: () => import('../pages/GamesPage.vue') },
    { path: '/games/:gameId/docs', name: 'game-docs', component: () => import('../pages/GameDocsPage.vue') },
    { path: '/lobbies/new', name: 'lobby-create', component: () => import('../pages/LobbyCreatePage.vue') },
    { path: '/competitions', redirect: '/lobbies' },
    { path: '/workspace/:teamId', name: 'workspace', component: () => import('../pages/TeamWorkspacePage.vue') },
    { path: '/tasks/:gameId/run', name: 'task-run', component: () => import('../pages/TaskRunPage.vue') },
    { path: '/tasks/:gameId/attempts', name: 'task-attempts', component: () => import('../pages/SingleTaskAttemptsPage.vue') },
    {
      path: '/runs/:runId/watch',
      name: 'run-watch',
      component: () => import('../pages/MatchWatchPage.vue'),
    },
    { path: '/replays', name: 'replays', component: () => import('../pages/ReplayCatalogPage.vue') },
    { path: '/lobbies/:lobbyId', name: 'lobby', component: () => import('../pages/LobbyPage.vue') },
    { path: '/competitions/:competitionId', name: 'competition', component: () => import('../pages/CompetitionPage.vue') },
    { path: '/admin/catalog', name: 'admin-catalog', component: () => import('../pages/AdminCatalogPage.vue') },
    { path: '/admin/game-sources', name: 'admin-game-sources', component: () => import('../pages/AdminGameSourcesPage.vue') },
  ],
});
