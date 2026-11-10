<template>
  <section class="agp-grid tasks-catalog-page">
    <header class="arena-materials-head">
      <h1>Материалы</h1>
      <RouterLink class="btn btn-outline-secondary" to="/admin/catalog"
        >Управление задачами</RouterLink
      >
    </header>
    <LoadingSkeleton v-if="isLoading" :count="6" label="Загрузка материалов" />
    <p v-else-if="errorMessage" role="alert" class="text-danger">
      {{ errorMessage }}
    </p>
    <div v-else class="section-card-grid">
      <RouterLink
        v-for="section in sections"
        :key="section.name"
        class="agp-card p-3 arena-material-section"
        :to="{ name: 'tasks-section', params: { section: section.name } }"
        ><h2>{{ section.name }}</h2>
        <p>{{ sectionDescription(section.name) }}</p>
        <span>{{ section.total }} задач →</span></RouterLink
      >
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import {
  listSingleTaskCatalog,
  type SingleTaskCatalogItemDto,
} from "../lib/api";
import { sectionDescription, sectionOrder } from "../lib/taskCatalog";
const tasks = ref<SingleTaskCatalogItemDto[]>([]);
const isLoading = ref(true);
const errorMessage = ref("");
const sections = computed(() => {
  const counts = new Map<string, number>();
  for (const task of tasks.value) {
    const name = task.learning_section || "Другое";
    counts.set(name, (counts.get(name) || 0) + 1);
  }
  return Array.from(counts, ([name, total]) => ({ name, total })).sort(
    (a, b) =>
      sectionOrder(a.name) - sectionOrder(b.name) ||
      a.name.localeCompare(b.name, "ru"),
  );
});
onMounted(async () => {
  try {
    tasks.value = await listSingleTaskCatalog();
  } catch (e) {
    errorMessage.value =
      e instanceof Error ? e.message : "Не удалось загрузить материалы";
  } finally {
    isLoading.value = false;
  }
});
</script>
<style scoped>
.arena-materials-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.arena-materials-head h1 {
  margin: 0;
}
.arena-material-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  color: var(--agp-text);
  text-decoration: none;
}
.arena-material-section h2,
.arena-material-section p {
  margin: 0;
}
.arena-material-section p {
  color: var(--agp-text-muted);
}
.arena-material-section span {
  color: var(--agp-primary);
  margin-top: auto;
}
.arena-material-section:hover {
  border-color: var(--agp-primary);
}
@media (max-width: 600px) {
  .arena-materials-head {
    align-items: flex-start;
  }
  .arena-materials-head .btn {
    font-size: 12px;
  }
}
</style>
