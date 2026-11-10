import type { UserRole } from './api';

export interface NavigationItem { path: string; label: string; shortLabel?: string; icon: string }

export const ROUTE_ROLES: Record<string, UserRole[]> = {
  games: ['admin'],
  tasks: ['teacher', 'admin'],
  'tasks-section': ['teacher', 'admin'],
  'admin-game-sources': ['admin'],
  'admin-catalog': ['teacher', 'admin'],
  replays: ['teacher', 'admin'],
  'lobby-create': ['teacher', 'admin'],
};

export function roleLandingPath(_role: UserRole): string { return '/lobbies'; }

export function primaryNavigation(role: UserRole): NavigationItem[] {
  const lobbies = { path: '/lobbies', label: 'Лобби', icon: 'trophy' };
  return role === 'student' ? [lobbies] : [lobbies, { path: '/tasks', label: 'Материалы', icon: 'tasks' }];
}

export function profileNavigation(role: UserRole): NavigationItem[] {
  if (role === 'student') return [];
  const teaching = [
    { path: '/lobbies?all=1', label: 'Управление лобби', icon: 'trophy' },
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
