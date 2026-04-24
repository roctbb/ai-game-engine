<template>
  <div class="agp-shell" :class="{ 'agp-shell--workspace': isChromeHiddenRoute }">
    <nav v-if="!isChromeHiddenRoute" class="agp-navbar">
      <div class="agp-topbar">
        <RouterLink class="agp-brand" to="/tasks">AI Game Platform</RouterLink>

        <div class="agp-primary-nav" aria-label="Главная навигация">
          <RouterLink class="agp-nav-link" to="/tasks">Задачи</RouterLink>
          <RouterLink class="agp-nav-link" to="/lobbies">Лобби и соревнования</RouterLink>
          <RouterLink class="agp-nav-link" to="/games">Игры</RouterLink>
          <RouterLink v-if="sessionStore.role === 'admin'" class="agp-nav-link" to="/admin/game-sources">
            Статус системы
          </RouterLink>
        </div>

        <details
          ref="userMenuRef"
          class="agp-user-menu"
          :open="isUserMenuOpen"
          @toggle="syncUserMenuOpen"
        >
          <summary>
            <span v-if="sessionStore.isAuthenticated">{{ sessionStore.nickname }}</span>
            <span v-else>Войти</span>
          </summary>
          <div class="agp-user-popover">
            <div class="small text-muted" v-if="sessionStore.isAuthenticated">
              {{ sessionStore.role }} · {{ sessionStore.provider }}
            </div>

            <RouterLink v-if="canManage" class="btn btn-sm btn-outline-secondary w-100" to="/admin/catalog" @click="closeUserMenu">
              Каталог задач
            </RouterLink>
            <RouterLink v-if="canManage" class="btn btn-sm btn-outline-secondary w-100" to="/replays" @click="closeUserMenu">
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
const isEmbeddedRoute = computed(() => route.query.embed === '1');
const isChromeHiddenRoute = computed(() =>
  ['login', 'task-run', 'run-watch'].includes(String(route.name ?? '')) || isEmbeddedRoute.value
);
const isWorkspaceRoute = computed(() =>
  ['task-run', 'run-watch', 'competition', 'workspace'].includes(String(route.name ?? ''))
);

function closeUserMenu(): void {
  isUserMenuOpen.value = false;
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
