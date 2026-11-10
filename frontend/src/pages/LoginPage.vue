<template>
  <section class="agp-login-page">
    <div class="agp-login-shell">
      <aside class="agp-login-hero" aria-hidden="true">
        <ArenaBot class="arena-login-bot" />
        <div class="agp-login-hero-content">
          <p>Арена</p>
          <h1>Код. Матчи. Турниры.</h1>
        </div>
      </aside>

      <div class="agp-login-panel">
      <div>
        <p class="agp-login-kicker">Арена</p>
        <h1>Войти в Арену</h1>

      </div>

      <div v-if="sessionStore.options?.dev_login_enabled" class="agp-login-form">
        <label class="form-label">Ник</label>
        <input
          v-model.trim="nickname"
          class="form-control"
          autocomplete="username"
          placeholder="Например, student-1"
          @keyup.enter="loginAsDev"
        />

        <label class="form-label">Роль</label>
        <div class="agp-login-role-grid" role="group" aria-label="Роль">
          <button
            v-for="option in roleOptions"
            :key="option.value"
            class="agp-login-role-button"
            :class="{ active: role === option.value }"
            type="button"
            @click="role = option.value"
          >
            <strong>{{ option.label }}</strong>
          </button>
        </div>


        <button class="btn btn-primary w-100" :disabled="isSubmitting || !nickname" @click="loginAsDev">
          {{ isSubmitting ? 'Входим...' : 'Войти' }}
        </button>
      </div>

      <a
        v-if="sessionStore.options?.geekclass_enabled"
        class="btn btn-outline-primary agp-login-geekclass-btn"
        :href="geekClassLoginUrl"
      >
        Войти через GeekClass
      </a>

      <div
        v-if="!sessionStore.isBootstrapped"
        class="alert alert-secondary mb-0 d-flex align-items-center gap-2"
      >
        <SnakeLoader />
        Проверяем доступные способы входа...
      </div>

      <div v-if="errorMessage" class="alert alert-danger mb-0">{{ errorMessage }}</div>
      <div v-else-if="sessionStore.optionsLoadError" class="alert alert-danger mb-0">
        {{ sessionStore.optionsLoadError }}
        <button class="btn btn-sm btn-outline-danger mt-2 w-100" type="button" @click="reloadAuthOptions">
          Проверить снова
        </button>
      </div>
      <div
        v-else-if="sessionStore.isBootstrapped && !sessionStore.options?.dev_login_enabled && !sessionStore.options?.geekclass_enabled"
        class="alert alert-warning mb-0"
      >
        Способы входа временно недоступны.
      </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import ArenaBot from '../components/ArenaBot.vue';
import SnakeLoader from '../components/SnakeLoader.vue';
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import type { UserRole } from '../lib/api';
import { internalNextPath } from '../lib/roleNavigation';
import { useSessionStore } from '../stores/session';

const route = useRoute();
const router = useRouter();
const sessionStore = useSessionStore();

const nickname = ref('student');
const role = ref<UserRole>('student');
const isSubmitting = ref(false);
const errorMessage = ref('');
const roleOptions: Array<{ value: UserRole; label: string; badge: string; hint: string }> = [
  {
    value: 'student',
    label: 'Ученик',
    badge: 'играет',
    hint: 'Решение задач, участие в лобби и просмотр своих матчей.',
  },
  {
    value: 'teacher',
    label: 'Преподаватель',
    badge: 'ведет',
    hint: 'Создание лобби, соревнований и управление учебным каталогом.',
  },
  {
    value: 'admin',
    label: 'Админ',
    badge: 'настраивает',
    hint: 'Полный доступ к настройкам системы и служебной диагностике.',
  },
];

const nextPath = computed(() => {
  return internalNextPath(route.query.next, '/');
});

const geekClassLoginUrl = computed(
  () => `/api/v1/auth/login?next=${encodeURIComponent(nextPath.value)}`
);
const roleHint = computed(() => {
  return roleOptions.find((option) => option.value === role.value)?.hint ?? '';
});

async function loginAsDev(): Promise<void> {
  const cleanNickname = nickname.value.trim();
  if (!cleanNickname || isSubmitting.value) {
    return;
  }
  isSubmitting.value = true;
  errorMessage.value = '';
  try {
    await sessionStore.loginAsDev(cleanNickname, role.value);
    await router.replace(nextPath.value);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось войти';
  } finally {
    isSubmitting.value = false;
  }
}

async function reloadAuthOptions(): Promise<void> {
  await sessionStore.refreshAuthOptions();
}
</script>

<style scoped>
.agp-login-page { min-height: 100dvh; display: grid; place-items: center; padding: 24px; background: var(--agp-bg); color: var(--agp-text); }
.agp-login-shell { width: min(100%, 960px); display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; }
.agp-login-hero, .agp-login-panel { display: grid; align-content: center; gap: 24px; min-width: 0; padding: 32px; border: 1px solid var(--agp-border); border-radius: 10px; }
.agp-login-hero { min-height: 400px; background: var(--agp-primary-soft); }
.arena-login-bot { font-size: 112px; margin-bottom: 16px; }
.agp-login-hero-content { display: grid; gap: 12px; }
.agp-login-hero-content p, .agp-login-kicker { margin: 0; font-size: 14px; font-weight: 500; color: var(--agp-primary); }
.agp-login-hero-content h1 { margin: 0; max-width: 360px; font-size: 36px; line-height: 40px; font-weight: 600; }
.agp-login-panel { background: var(--agp-surface); }
.agp-login-panel h1 { margin: 8px 0 0; }
.agp-login-form { display: grid; gap: 12px; }
.agp-login-form .form-label { margin: 0; }
.agp-login-role-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.agp-login-role-button { min-height: 44px; padding: 8px; border: 1px solid var(--agp-border); border-radius: 6px; color: var(--agp-text); background: var(--agp-surface); font: inherit; }
.agp-login-role-button strong { font-size: 12px; font-weight: 500; }
.agp-login-role-button.active { border-color: var(--agp-primary); background: var(--agp-primary-soft); color: var(--agp-primary); }
.agp-login-geekclass-btn { justify-self: start; }
@media (max-width: 767px) {
 .agp-login-page { padding: 16px; }
 .agp-login-shell { max-width: 440px; grid-template-columns: 1fr; gap: 12px; }
 .agp-login-hero, .agp-login-panel { padding: 24px; }
 .agp-login-hero { min-height: 0; grid-template-columns: auto 1fr; align-items: center; gap: 24px; }
 .arena-login-bot { font-size: 64px; margin: 0; }
 .agp-login-hero-content { gap: 8px; }
 .agp-login-hero-content h1 { font-size: 24px; line-height: 28px; }
}
@media (max-width: 400px) { .agp-login-role-grid { grid-template-columns: 1fr; } }
</style>
