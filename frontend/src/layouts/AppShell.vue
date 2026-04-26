<template>
  <div class="agp-shell" :class="{ 'agp-shell--workspace': isChromeHiddenRoute }">
    <nav v-if="!isChromeHiddenRoute" class="agp-navbar">
      <div class="agp-topbar">
        <RouterLink class="agp-brand" to="/tasks">
          <span class="agp-brand-mark" aria-hidden="true"></span>
          <span class="agp-brand-copy">
            <strong>Игровая платформа</strong>
            <small>AI Arena</small>
          </span>
        </RouterLink>

        <div class="agp-primary-nav" aria-label="Главная навигация">
          <RouterLink class="agp-nav-link" to="/tasks">Задачи</RouterLink>
          <RouterLink class="agp-nav-link" to="/lobbies">Лобби и соревнования</RouterLink>
          <RouterLink class="agp-nav-link" to="/games">Игры</RouterLink>
          <RouterLink v-if="canManage" class="agp-nav-link" to="/admin/game-sources">
            {{ systemNavLabel }}
          </RouterLink>
        </div>

        <div
          ref="userMenuRef"
          class="agp-user-menu"
        >
          <button
            class="agp-user-trigger"
            type="button"
            :aria-expanded="isUserMenuOpen"
            aria-controls="agp-user-popover"
            @click.stop="toggleUserMenu"
          >
            <span class="agp-user-avatar" aria-hidden="true">{{ userInitial }}</span>
            <span class="agp-user-trigger-copy">
              <strong v-if="sessionStore.isAuthenticated">{{ sessionStore.nickname }}</strong>
              <strong v-else>Войти</strong>
              <small>{{ sessionStore.isAuthenticated ? roleLabel : 'Гость' }}</small>
            </span>
            <span class="agp-user-caret" aria-hidden="true"></span>
          </button>
          <div v-if="isUserMenuOpen" id="agp-user-popover" class="agp-user-popover">
            <div class="agp-user-card" v-if="sessionStore.isAuthenticated">
              <div>
                <div class="small text-muted">Пользователь</div>
                <strong>{{ sessionStore.nickname }}</strong>
              </div>
              <span class="agp-pill agp-pill--neutral">{{ roleLabel }}</span>
              <div class="small text-muted">{{ providerLabel }}</div>
            </div>

            <RouterLink v-if="canManage" class="btn btn-sm btn-outline-secondary w-100" to="/admin/catalog" @click="closeUserMenu">
              Каталог задач
            </RouterLink>
            <RouterLink v-if="canManage" class="btn btn-sm btn-outline-secondary w-100" to="/replays" @click="closeUserMenu">
              Повторы
            </RouterLink>

            <RouterLink
              v-if="!sessionStore.isAuthenticated"
              class="btn btn-sm btn-primary w-100"
              :to="{ name: 'login', query: { next: route.fullPath } }"
              @click="closeUserMenu"
            >
              Войти
            </RouterLink>

            <button
              v-if="sessionStore.isAuthenticated"
              class="btn btn-sm btn-outline-danger w-100"
              @click="logout"
            >
              Выйти
            </button>
          </div>
        </div>
      </div>
    </nav>

    <main class="agp-main" :class="{ 'agp-main--workspace': isWorkspaceRoute }">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router';

import { useSessionStore } from '../stores/session';

const route = useRoute();
const router = useRouter();
const sessionStore = useSessionStore();
const userMenuRef = ref<HTMLDivElement | null>(null);
const isUserMenuOpen = ref(false);
const canManage = computed(
  () => sessionStore.role === 'teacher' || sessionStore.role === 'admin'
);
const systemNavLabel = computed(() => (sessionStore.role === 'admin' ? 'Статус системы' : 'Источники игр'));
const roleLabel = computed(() => {
  if (sessionStore.role === 'admin') return 'администратор';
  if (sessionStore.role === 'teacher') return 'преподаватель';
  return 'ученик';
});
const providerLabel = computed(() => {
  if (sessionStore.provider === 'geekclass') return 'Вход через GeekClass';
  if (sessionStore.provider === 'dev') return 'Учебный вход';
  return 'Сессия активна';
});
const userInitial = computed(() => {
  const source = sessionStore.isAuthenticated ? sessionStore.nickname : '?';
  return source.trim().slice(0, 1).toUpperCase() || '?';
});
const isEmbeddedRoute = computed(() => route.query.embed === '1');
const isChromeHiddenRoute = computed(() =>
  ['login', 'task-run', 'run-watch', 'lobby'].includes(String(route.name ?? '')) || isEmbeddedRoute.value
);
const isWorkspaceRoute = computed(() =>
  ['login', 'task-run', 'run-watch', 'competition', 'player-code', 'lobby'].includes(String(route.name ?? ''))
);

function closeUserMenu(): void {
  isUserMenuOpen.value = false;
}

function toggleUserMenu(): void {
  isUserMenuOpen.value = !isUserMenuOpen.value;
}

function handleDocumentPointerDown(event: PointerEvent): void {
  const menu = userMenuRef.value;
  if (!menu || !isUserMenuOpen.value) return;
  if (event.target instanceof Node && menu.contains(event.target)) return;
  closeUserMenu();
}

function handleDocumentKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape') return;
  closeUserMenu();
}

async function logout(): Promise<void> {
  await sessionStore.logout();
  closeUserMenu();
  await router.replace({ name: 'login' });
}

watch(
  () => route.fullPath,
  () => closeUserMenu(),
);

onMounted(() => {
  document.addEventListener('pointerdown', handleDocumentPointerDown);
  document.addEventListener('keydown', handleDocumentKeydown);
});

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handleDocumentPointerDown);
  document.removeEventListener('keydown', handleDocumentKeydown);
});
</script>
