import { defineStore } from 'pinia';

import {
  clearStoredSessionId,
  devLogin,
  getAuthOptions,
  getStoredSessionId,
  me,
  storeSessionId,
  logout as apiLogout,
  type AuthOptionsDto,
  type AuthProvider,
  type SessionDto,
  type UserRole,
} from '../lib/api';

interface SessionState {
  sessionId: string;
  externalUserId: string;
  nickname: string;
  role: UserRole;
  provider: AuthProvider;
  isAuthenticated: boolean;
  isBootstrapped: boolean;
  options: AuthOptionsDto | null;
  optionsLoadError: string | null;
}

const DEFAULT_SESSION: SessionState = {
  sessionId: '',
  externalUserId: '',
  nickname: 'guest',
  role: 'student',
  provider: 'dev',
  isAuthenticated: false,
  isBootstrapped: false,
  options: null,
  optionsLoadError: null,
};

function applySession(store: SessionState, payload: SessionDto): void {
  store.sessionId = payload.session_id;
  store.externalUserId = payload.external_user_id;
  store.nickname = payload.nickname;
  store.role = payload.role;
  store.provider = payload.provider;
  store.isAuthenticated = true;
}

export const useSessionStore = defineStore('session', {
  state: (): SessionState => ({ ...DEFAULT_SESSION }),
  actions: {
    async bootstrap(): Promise<void> {
      this.optionsLoadError = null;
      try {
        this.options = await getAuthOptions();
        const stored = getStoredSessionId();
        if (!stored) {
          this.optionsLoadError = null;
          return;
        }
        try {
          const session = await me();
          applySession(this, session);
        } catch {
          clearStoredSessionId();
        }
      } catch (error) {
        this.options = null;
        this.optionsLoadError =
          error instanceof Error ? error.message : 'Не удалось загрузить настройки входа';
      } finally {
        this.isBootstrapped = true;
      }
    },

    async refreshAuthOptions(): Promise<void> {
      this.optionsLoadError = null;
      try {
        this.options = await getAuthOptions();
      } catch (error) {
        this.options = null;
        this.optionsLoadError =
          error instanceof Error ? error.message : 'Не удалось загрузить настройки входа';
      }
    },

    async loginAsDev(nickname: string, role: UserRole): Promise<void> {
      const session = await devLogin({ nickname, role });
      storeSessionId(session.session_id);
      applySession(this, session);
    },

    async refreshMe(): Promise<void> {
      const session = await me();
      applySession(this, session);
    },

    async logout(): Promise<void> {
      if (this.sessionId) {
        try {
          await apiLogout();
        } catch {
          // ignore backend logout errors, session storage cleanup is still required
        }
      }
      clearStoredSessionId();
      this.$patch({ ...DEFAULT_SESSION, options: this.options, isBootstrapped: true });
    },
  },
});
