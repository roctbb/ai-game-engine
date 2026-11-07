import type { UserRole } from './api';

export interface NavigationItem { path: string; label: string; shortLabel?: string; icon: string }

const learningNavigation: NavigationItem[] = [
  { path: '/tasks', label: 'Задачи', icon: 'tasks' },
  { path: '/lobbies', label: 'Лобби и соревнования', shortLabel: 'Лобби', icon: 'trophy' },
];

export const ROUTE_ROLES: Record<string, UserRole[]> = {
  games: ['admin'],
  'admin-game-sources': ['admin'],
  'admin-catalog': ['teacher', 'admin'],
  replays: ['teacher', 'admin'],
  'lobby-create': ['teacher', 'admin'],
};

export function roleLandingPath(role: UserRole): string {
  if (role === 'admin') return '/admin/game-sources';
  if (role === 'teacher') return '/lobbies';
  return '/tasks';
}

export function primaryNavigation(_role: UserRole): NavigationItem[] {
  return learningNavigation;
}

export function profileNavigation(role: UserRole): NavigationItem[] {
  if (role === 'student') return [];
  const teaching = [
    { path: '/admin/catalog', label: 'Управление задачами', icon: 'tasks' },
    { path: '/replays', label: 'Повторы матчей', icon: 'history' },
  ];
  return role === 'admin' ? [
    { path: '/admin/game-sources', label: 'Система', icon: 'settings' },
    { path: '/games', label: 'Каталог игр', icon: 'games' },
    ...teaching,
  ] : teaching;
}

export function internalNextPath(candidate: unknown, fallback: string): string {
  return typeof candidate === 'string' && candidate.startsWith('/') && !candidate.startsWith('//') && candidate.split(/[?#]/)[0] !== '/login'
    ? candidate : fallback;
}
