<template>
  <div class="agp-shell" :class="{ 'agp-shell--workspace': isChromeHiddenRoute }">
    <nav v-if="!isChromeHiddenRoute" class="agp-navbar">
      <div class="agp-topbar">
        <RouterLink class="agp-brand" to="/tasks">AI Game Platform</RouterLink>

        <div class="agp-primary-nav" aria-label="Главная навигация">
          <RouterLink class="agp-nav-link" to="/tasks">Задачи</RouterLink>
          <RouterLink class="agp-nav-link" to="/lobbies">Лобби</RouterLink>
        </div>

        <details class="agp-user-menu">
          <summary>
            <span v-if="sessionStore.isAuthenticated">{{ sessionStore.nickname }}</span>
            <span v-else>Войти</span>
          </summary>
          <div class="agp-user-popover">
            <div class="small text-muted" v-if="sessionStore.isAuthenticated">
              {{ sessionStore.role }} · {{ sessionStore.provider }}
            </div>

            <template v-if="sessionStore.options?.dev_login_enabled">
              <input
                v-model.trim="nicknameInput"
                class="form-control form-control-sm"
                placeholder="Ник"
              />
              <select v-model="roleInput" class="form-select form-select-sm">
                <option value="student">student</option>
                <option value="teacher">teacher</option>
                <option value="admin">admin</option>
              </select>
              <button class="btn btn-sm btn-outline-primary w-100" @click="loginAsDev">Dev Login</button>
            </template>

            <RouterLink v-if="canManage" class="btn btn-sm btn-outline-secondary w-100" to="/admin/catalog">
              Каталог
            </RouterLink>
            <RouterLink v-if="canManage" class="btn btn-sm btn-outline-secondary w-100" to="/admin/game-sources">
              Система
            </RouterLink>
            <RouterLink class="btn btn-sm btn-outline-secondary w-100" to="/replays">
              Реплеи
            </RouterLink>

            <button
              v-if="sessionStore.isAuthenticated"
              class="btn btn-sm btn-outline-danger w-100"
              @click="logout"
            >
              Logout
            </button>
          </div>
        </details>
      </div>
    </nav>

    <main class="agp-main" :class="{ 'agp-main--workspace': isWorkspaceRoute }">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { RouterLink, RouterView, useRoute } from 'vue-router';

import { useSessionStore } from '../stores/session';

const route = useRoute();
const sessionStore = useSessionStore();
const nicknameInput = ref('debug-user');
const roleInput = ref<'student' | 'teacher' | 'admin'>('teacher');
const canManage = computed(
  () => sessionStore.role === 'teacher' || sessionStore.role === 'admin'
);
const isChromeHiddenRoute = computed(() => String(route.name ?? '') === 'task-run');
const isWorkspaceRoute = computed(() =>
  ['task-run', 'lobby', 'run-watch', 'competition', 'workspace'].includes(String(route.name ?? ''))
);

async function loginAsDev(): Promise<void> {
  const nickname = nicknameInput.value.trim();
  if (!nickname) {
    return;
  }
  await sessionStore.loginAsDev(nickname, roleInput.value);
}

async function logout(): Promise<void> {
  await sessionStore.logout();
}
</script>
