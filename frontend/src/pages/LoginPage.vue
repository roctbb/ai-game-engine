<template>
  <section class="agp-login-page">
    <div class="agp-login-shell">
      <aside class="agp-login-hero" aria-hidden="true">
        <div class="agp-login-orbit">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <div class="agp-login-hero-content">
          <p>Игровая платформа</p>
          <h1>Код. Матчи. Турниры.</h1>
        </div>
      </aside>

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
            <span>{{ option.badge }}</span>
          </button>
        </div>
        <div class="agp-login-role-hint">
          {{ roleHint }}
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
  const candidate = typeof route.query.next === 'string' ? route.query.next : '/tasks';
  return candidate.startsWith('/') ? candidate : '/tasks';
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
.agp-login-page {
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: 1rem;
  background-color: #07101f;
  background-image:
    url("data:image/svg+xml,%3Csvg width='160' height='160' viewBox='0 0 160 160' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2322d3ee' stroke-opacity='.16' stroke-width='2'%3E%3Cpath d='M18 18h32v32H18zM110 18h32v32h-32zM18 110h32v32H18zM110 110h32v32h-32z'/%3E%3Cpath d='M80 0v32M80 128v32M0 80h32M128 80h32M64 80h32M80 64v32'/%3E%3C/g%3E%3C/svg%3E"),
    radial-gradient(circle at 15% 18%, rgba(20, 184, 166, 0.28), transparent 22rem),
    radial-gradient(circle at 86% 16%, rgba(245, 158, 11, 0.2), transparent 22rem),
    linear-gradient(135deg, #07101f 0%, #0b1930 56%, #020617 100%);
  background-size: 160px 160px, auto, auto, auto;
}

.agp-login-shell {
  width: min(100%, 62rem);
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(22rem, 0.8fr);
  align-items: stretch;
  gap: 1rem;
}

.agp-login-hero,
.agp-login-panel {
  position: relative;
  overflow: hidden;
  display: grid;
  border: 1px solid rgba(125, 211, 252, 0.24);
  border-radius: 0.75rem;
  box-shadow: 0 28px 80px rgba(0, 0, 0, 0.28);
}

.agp-login-hero {
  min-height: 34rem;
  align-content: end;
  padding: 1.3rem;
  background:
    url("data:image/svg+xml,%3Csvg width='210' height='126' viewBox='0 0 210 126' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%23ffffff' stroke-opacity='.18' stroke-width='2'%3E%3Cpath d='M24 24h36v36H24zM150 24h36v36h-36zM87 66h36v36H87z'/%3E%3Cpath d='M60 42h27M123 84h27M105 0v24M105 102v24M0 63h34M176 63h34'/%3E%3C/g%3E%3C/svg%3E") right 1.2rem top 1.2rem / 18rem auto no-repeat,
    radial-gradient(circle at 25% 18%, rgba(45, 212, 191, 0.42), transparent 18rem),
    radial-gradient(circle at 90% 26%, rgba(245, 158, 11, 0.32), transparent 16rem),
    linear-gradient(135deg, rgba(15, 118, 110, 0.96), rgba(37, 99, 235, 0.86) 56%, rgba(2, 6, 23, 0.96));
  color: #f8fbff;
}

.agp-login-orbit {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.agp-login-orbit span {
  position: absolute;
  width: 0.6rem;
  height: 0.6rem;
  border-radius: 50%;
  background: #facc15;
  box-shadow: 0 0 22px rgba(250, 204, 21, 0.72);
}

.agp-login-orbit span:nth-child(1) {
  left: 16%;
  top: 24%;
}

.agp-login-orbit span:nth-child(2) {
  right: 18%;
  top: 52%;
  background: #67e8f9;
}

.agp-login-orbit span:nth-child(3) {
  left: 48%;
  bottom: 28%;
  background: #5eead4;
}

.agp-login-hero-content {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 1rem;
}

.agp-login-hero-content > p {
  margin: 0;
  color: #b7f4ff;
  font-size: 0.78rem;
  font-weight: 900;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.agp-login-hero-content h1 {
  max-width: 32rem;
  margin: 0;
  font-size: clamp(2.35rem, 5vw, 4.25rem);
  font-weight: 950;
  line-height: 0.98;
}

.agp-login-hero-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.65rem;
}

.agp-login-hero-grid div {
  min-height: 6.4rem;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 0.65rem;
  display: grid;
  align-content: end;
  gap: 0.15rem;
  padding: 0.75rem;
  background: rgba(255, 255, 255, 0.09);
  backdrop-filter: blur(10px);
}

.agp-login-hero-grid strong {
  font-size: 1rem;
}

.agp-login-hero-grid span {
  color: rgba(248, 251, 255, 0.72);
  font-size: 0.78rem;
  line-height: 1.25;
}

.agp-login-panel {
  align-content: center;
  gap: 1rem;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.97), rgba(239, 246, 255, 0.94));
  padding: 2rem 1.5rem;
}

.agp-login-geekclass-btn {
  justify-self: start;
  padding: 0.5rem 1.5rem;
}

.agp-login-kicker {
  margin-bottom: 0.35rem;
  color: #0f766e;
  font-size: 0.78rem;
  font-weight: 900;
  letter-spacing: 0;
  text-transform: uppercase;
}

.agp-login-panel h1 {
  margin-bottom: 0.35rem;
  font-weight: 900;
}

.agp-login-form {
  display: grid;
  gap: 0.65rem;
}

.agp-login-role-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.45rem;
}

.agp-login-role-button {
  border: 1px solid rgba(148, 163, 184, 0.42);
  border-radius: 0.55rem;
  display: grid;
  gap: 0.08rem;
  min-height: 4.2rem;
  align-content: center;
  padding: 0.55rem;
  background: rgba(255, 255, 255, 0.72);
  color: var(--agp-text);
  text-align: left;
}

.agp-login-role-button strong {
  font-size: 0.92rem;
}

.agp-login-role-button span {
  color: var(--agp-text-muted);
  font-size: 0.72rem;
}

.agp-login-role-button.active {
  border-color: rgba(20, 184, 166, 0.62);
  background:
    url("data:image/svg+xml,%3Csvg width='58' height='40' viewBox='0 0 58 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2314b8a6' stroke-opacity='.2'%3E%3Cpath d='M8 8h12v12H8zM38 8h12v12H38zM23 20h12v12H23z'/%3E%3C/g%3E%3C/svg%3E") right 0.35rem center / 3.6rem auto no-repeat,
    linear-gradient(135deg, #dff7f4, #dbeafe);
  box-shadow: 0 10px 24px rgba(20, 184, 166, 0.12);
}

.agp-login-role-hint {
  border: 1px solid rgba(15, 118, 110, 0.14);
  border-radius: 0.55rem;
  background: rgba(223, 247, 244, 0.74);
  color: #31565a;
  padding: 0.65rem;
  font-size: 0.86rem;
}

@media (max-width: 860px) {
  .agp-login-shell {
    grid-template-columns: 1fr;
  }

  .agp-login-hero {
    min-height: auto;
  }

  .agp-login-hero-content h1 {
    font-size: 2.2rem;
  }
}

@media (max-width: 520px) {
  .agp-login-hero-grid,
  .agp-login-role-grid {
    grid-template-columns: 1fr;
  }
}
</style>
