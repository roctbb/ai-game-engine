import { describe, expect, it } from 'vitest';
import { internalNextPath, primaryNavigation, profileNavigation, roleLandingPath, ROUTE_ROLES } from './roleNavigation';

describe('role-based user journeys', () => {
  it('starts each role at its main workflow', () => {
    expect(roleLandingPath('student')).toBe('/tasks');
    expect(roleLandingPath('teacher')).toBe('/lobbies');
    expect(roleLandingPath('admin')).toBe('/admin/game-sources');
  });

  it('keeps the game catalog in the admin profile, outside primary navigation', () => {
    for (const role of ['student', 'teacher', 'admin'] as const) {
      expect(primaryNavigation(role).some((item) => item.path === '/games')).toBe(false);
      expect(profileNavigation(role).some((item) => item.path === '/games')).toBe(role === 'admin');
    }
    expect(ROUTE_ROLES.games).toEqual(['admin']);
  });

  it('keeps infrastructure out of teaching and learning navigation', () => {
    expect(primaryNavigation('student').map((item) => item.path)).toEqual(['/tasks', '/lobbies']);
    expect(primaryNavigation('teacher').map((item) => item.path)).toEqual(['/tasks', '/lobbies']);
    expect(profileNavigation('student')).toEqual([]);
    expect(ROUTE_ROLES['admin-game-sources']).toEqual(['admin']);
    expect(ROUTE_ROLES['admin-catalog']).toContain('teacher');
  });

  it('preserves deep links and falls back safely after sign-in', () => {
    expect(internalNextPath('/lobbies/class-1', '/tasks')).toBe('/lobbies/class-1');
    expect(internalNextPath('//example.com', '/tasks')).toBe('/tasks');
    expect(internalNextPath('/login?next=/login', '/lobbies')).toBe('/lobbies');
    expect(internalNextPath(undefined, '/lobbies')).toBe('/lobbies');
  });
});
