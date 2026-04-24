import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap';
import { createPinia } from 'pinia';
import { createApp } from 'vue';

import App from './App.vue';
import { storeSessionId } from './lib/api';
import { router } from './router';
import { useSessionStore } from './stores/session';
import './style.css';

const app = createApp(App);
const pinia = createPinia();
app.use(pinia);

const sessionStore = useSessionStore(pinia);
const sessionReady = sessionStore.bootstrap();

router.beforeEach(async (to) => {
  await sessionReady;

  const callbackSessionId = Array.isArray(to.query.session_id)
    ? to.query.session_id[0]
    : to.query.session_id;
  if (typeof callbackSessionId === 'string' && callbackSessionId.trim()) {
    storeSessionId(callbackSessionId.trim());
    await sessionStore.refreshMe();
    const query = { ...to.query };
    delete query.session_id;
    return { path: to.path, query, hash: to.hash, replace: true };
  }

  if (to.meta.public) {
    if (to.name === 'login' && sessionStore.isAuthenticated) {
      const next = typeof to.query.next === 'string' && to.query.next.startsWith('/')
        ? to.query.next
        : '/tasks';
      return next;
    }
    return true;
  }

  if (!sessionStore.isAuthenticated) {
    return { name: 'login', query: { next: to.fullPath } };
  }

  return true;
});

app.use(router);

app.mount('#app');
