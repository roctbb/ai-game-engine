import { describe, expect, it } from 'vitest';
import { shouldRedirectToGeekclass } from './automaticLogin';

const server = { options: { geekclass_enabled: true, dev_login_enabled: false }, ready: true,
  authenticated: false, loadError: null, callbackFailed: false };

describe('automatic Geekclass login', () => {
  it('starts login when Geekclass is the only configured login method', () => {
    expect(shouldRedirectToGeekclass(server)).toBe(true);
  });
  it('keeps the local development login available', () => {
    expect(shouldRedirectToGeekclass({ ...server, options: { geekclass_enabled: true, dev_login_enabled: true } })).toBe(false);
    expect(shouldRedirectToGeekclass({ ...server, options: { geekclass_enabled: false, dev_login_enabled: true } })).toBe(false);
  });
  it('waits until a saved session has been checked and never redirects an authenticated user', () => {
    expect(shouldRedirectToGeekclass({ ...server, ready: false })).toBe(false);
    expect(shouldRedirectToGeekclass({ ...server, authenticated: true })).toBe(false);
  });
  it('does not loop after an authorization failure or hide a network error', () => {
    expect(shouldRedirectToGeekclass({ ...server, callbackFailed: true })).toBe(false);
    expect(shouldRedirectToGeekclass({ ...server, loadError: 'Сервер недоступен' })).toBe(false);
    expect(shouldRedirectToGeekclass({ ...server, options: null })).toBe(false);
  });
});
