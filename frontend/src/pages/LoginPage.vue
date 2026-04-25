<template>
  <section class="agp-login-page">
    <div class="agp-login-panel">
      <div>
        <p class="agp-login-kicker">Игровая платформа</p>
        <h1>Вход в систему</h1>
        <p class="text-muted mb-0">
          Каталог задач, лобби, соревнования и просмотр матчей доступны только участникам.
        </p>
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
        <select v-model="role" class="form-select">
          <option value="student">Ученик</option>
          <option value="teacher">Преподаватель</option>
          <option value="admin">Администратор</option>
        </select>
        <div class="agp-login-role-hint">
          {{ roleHint }}
        </div>

        <button class="btn btn-primary w-100" :disabled="isSubmitting || !nickname" @click="loginAsDev">
          {{ isSubmitting ? 'Входим...' : 'Войти' }}
        </button>
      </div>

      <a
        v-if="sessionStore.options?.geekclass_enabled"
        class="btn btn-outline-primary w-100"
        :href="geekClassLoginUrl"
      >
        Войти через GeekClass
      </a>

      <div
        v-if="!sessionStore.isBootstrapped"
        class="alert alert-secondary mb-0 d-flex align-items-center gap-2"
      >
        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
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
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import type { UserRole } from '../lib/api';
import { useSessionStore } from '../stores/session';

const route = useRoute();
const router = useRouter();
const sessionStore = useSessionStore();

const nickname = ref('student');
const role = ref<UserRole>('student');
const isSubmitting = ref(false);
const errorMessage = ref('');

const nextPath = computed(() => {
  const candidate = typeof route.query.next === 'string' ? route.query.next : '/tasks';
  return candidate.startsWith('/') ? candidate : '/tasks';
});

const geekClassLoginUrl = computed(
  () => `/api/v1/auth/login?next=${encodeURIComponent(nextPath.value)}`
);
const roleHint = computed(() => {
  if (role.value === 'admin') return 'Полный доступ к настройкам системы и служебной диагностике.';
  if (role.value === 'teacher') return 'Создание лобби, соревнований и управление учебным каталогом.';
  return 'Решение задач, участие в лобби и просмотр своих матчей.';
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
