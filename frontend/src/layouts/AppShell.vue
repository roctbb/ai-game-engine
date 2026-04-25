<template>
  <div class="agp-shell" :class="{ 'agp-shell--workspace': isChromeHiddenRoute }">
    <nav v-if="!isChromeHiddenRoute" class="agp-navbar">
      <div class="agp-topbar">
        <RouterLink class="agp-brand" to="/tasks">Игровая платформа</RouterLink>

        <div class="agp-primary-nav" aria-label="Главная навигация">
          <RouterLink class="agp-nav-link" to="/tasks">Задачи</RouterLink>
          <RouterLink class="agp-nav-link" to="/lobbies">Лобби и соревнования</RouterLink>
          <RouterLink class="agp-nav-link" to="/games">Игры</RouterLink>
          <RouterLink v-if="canManage" class="agp-nav-link" to="/admin/game-sources">
            {{ systemNavLabel }}
          </RouterLink>
        </div>

        <details
          ref="userMenuRef"
          class="agp-user-menu"
          @toggle="syncUserMenuOpen"
        >
          <summary>
            <span v-if="sessionStore.isAuthenticated">{{ sessionStore.nickname }}</span>
            <span v-else>Войти</span>
          </summary>
          <div class="agp-user-popover">
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

            <button
              v-if="sessionStore.isAuthenticated"
              class="btn btn-sm btn-outline-danger w-100"
              @click="logout"
            >
              Выйти
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router';

import { useSessionStore } from '../stores/session';

const route = useRoute();
const router = useRouter();
const sessionStore = useSessionStore();
const userMenuRef = ref<HTMLDetailsElement | null>(null);
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
const isEmbeddedRoute = computed(() => route.query.embed === '1');
const isChromeHiddenRoute = computed(() =>
  ['login', 'task-run', 'run-watch', 'lobby'].includes(String(route.name ?? '')) || isEmbeddedRoute.value
);
const isWorkspaceRoute = computed(() =>
  ['login', 'task-run', 'run-watch', 'competition', 'player-code', 'lobby'].includes(String(route.name ?? ''))
);

function closeUserMenu(): void {
  isUserMenuOpen.value = false;
  if (userMenuRef.value) userMenuRef.value.open = false;
}

function syncUserMenuOpen(event: Event): void {
  isUserMenuOpen.value = (event.currentTarget as HTMLDetailsElement).open;
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
