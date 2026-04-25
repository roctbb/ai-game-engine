import { createRouter, createWebHistory } from 'vue-router';

type AppRouteRole = 'student' | 'teacher' | 'admin';

const teacherAdmin: AppRouteRole[] = ['teacher', 'admin'];

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
    { path: '/tasks/sections/:section', name: 'tasks-section', component: () => import('../pages/TasksSectionPage.vue') },
    { path: '/lobbies', name: 'lobbies', component: () => import('../pages/LobbiesPage.vue') },
    { path: '/games', name: 'games', component: () => import('../pages/GamesPage.vue') },
    { path: '/games/:gameId/docs', name: 'game-docs', component: () => import('../pages/GameDocsPage.vue') },
    { path: '/lobbies/new', name: 'lobby-create', meta: { roles: teacherAdmin }, component: () => import('../pages/LobbyCreatePage.vue') },
    { path: '/competitions', redirect: '/lobbies' },
    { path: '/workspace/:teamId', redirect: (to) => ({ name: 'player-code', params: to.params }) },
    { path: '/players/:teamId/code', name: 'player-code', component: () => import('../pages/TeamWorkspacePage.vue') },
    { path: '/tasks/:gameId/run', name: 'task-run', component: () => import('../pages/TaskRunPage.vue') },
    { path: '/tasks/:gameId/attempts', name: 'task-attempts', component: () => import('../pages/SingleTaskAttemptsPage.vue') },
    {
      path: '/runs/:runId/watch',
      name: 'run-watch',
      component: () => import('../pages/MatchWatchPage.vue'),
    },
    { path: '/runs/:runId', redirect: (to) => ({ name: 'run-watch', params: to.params }) },
    { path: '/replays', name: 'replays', meta: { roles: teacherAdmin }, component: () => import('../pages/ReplayCatalogPage.vue') },
    { path: '/lobbies/:lobbyId', name: 'lobby', component: () => import('../pages/LobbyPage.vue') },
    { path: '/competitions/:competitionId', name: 'competition', component: () => import('../pages/CompetitionPage.vue') },
    { path: '/admin/catalog', name: 'admin-catalog', meta: { roles: teacherAdmin }, component: () => import('../pages/AdminCatalogPage.vue') },
    { path: '/admin/game-sources', name: 'admin-game-sources', meta: { roles: teacherAdmin }, component: () => import('../pages/AdminGameSourcesPage.vue') },
  ],
});
