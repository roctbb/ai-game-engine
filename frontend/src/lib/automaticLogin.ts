import type { AuthOptionsDto } from './api';

interface LoginState {
  options: AuthOptionsDto | null;
  ready: boolean;
  authenticated: boolean;
  loadError: string | null;
  callbackFailed: boolean;
}

export function shouldRedirectToGeekclass(state: LoginState): boolean {
  return Boolean(state.ready && !state.authenticated && !state.loadError && !state.callbackFailed &&
    state.options?.geekclass_enabled && !state.options.dev_login_enabled);
}
