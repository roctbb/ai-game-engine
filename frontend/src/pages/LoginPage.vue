<template>
  <section class="agp-login-page">
    <div class="agp-login-panel">
      <div>
        <p class="agp-login-kicker">AI Game Platform</p>
        <h1>Вход в систему</h1>
        <p class="text-muted mb-0">
          Каталог задач, лобби и рабочие пространства доступны только участникам.
          По публичной ссылке можно открыть только просмотр матча.
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
          <option value="student">student</option>
          <option value="teacher">teacher</option>
          <option value="admin">admin</option>
        </select>

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

      <div v-if="errorMessage" class="alert alert-danger mb-0">{{ errorMessage }}</div>
      <div
        v-if="!sessionStore.options?.dev_login_enabled && !sessionStore.options?.geekclass_enabled"
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
</script>
