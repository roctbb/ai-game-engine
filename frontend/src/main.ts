import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap';
import { createPinia } from 'pinia';
import { createApp } from 'vue';

import App from './App.vue';
import { router } from './router';
import { useSessionStore } from './stores/session';
import './style.css';

const app = createApp(App);
const pinia = createPinia();
app.use(pinia);
app.use(router);

const sessionStore = useSessionStore(pinia);
void sessionStore.bootstrap();

app.mount('#app');
