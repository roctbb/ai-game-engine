<template>
  <section class="agp-grid">
    <header class="arena-materials-head">
      <RouterLink class="agp-back-link" to="/tasks" aria-label="К материалам"
        >←</RouterLink
      >
      <h1>{{ routeSection }}</h1>
      <span class="text-muted">{{ filteredTasks.length }} задач</span>
    </header>
    <div class="agp-card p-3 arena-material-filters">
      <label
        >Тег<select v-model="selectedTopic" class="form-select">
          <option value="">Все</option>
          <option v-for="topic in topicOptions" :key="topic">
            {{ topic }}
          </option>
        </select></label
      ><label
        >Сложность<select v-model="selectedDifficulty" class="form-select">
          <option value="">Любая</option>
          <option
            v-for="difficulty in difficultyOptions"
            :key="difficulty"
            :value="difficulty"
          >
            {{ difficultyLabel(difficulty) }}
          </option>
        </select></label
      ><button
        v-if="selectedTopic || selectedDifficulty"
        class="btn btn-outline-secondary"
        @click="
          selectedTopic = '';
          selectedDifficulty = '';
        "
      >
        Сбросить
      </button>
    </div>
    <LoadingSkeleton
      v-if="isLoading"
      :count="4"
      layout="list"
      label="Загрузка задач"
    />
    <p v-else-if="errorMessage" role="alert" class="text-danger">
      {{ errorMessage }}
    </p>
    <p v-else-if="!filteredTasks.length" class="text-muted">
      Задачи не найдены
    </p>
    <article
      v-for="task in filteredTasks"
      :key="task.game_id"
      class="agp-card p-3 arena-material-task"
    >
      <div>
        <h2>{{ task.title }}</h2>
        <p>{{ task.description }}</p>
        <div class="d-flex gap-2 flex-wrap">
          <span v-if="task.difficulty" class="agp-pill agp-pill--neutral">{{
            difficultyLabel(task.difficulty)
          }}</span
          ><span
            v-for="topic in task.topics"
            :key="topic"
            class="agp-pill agp-pill--neutral"
            >{{ topic }}</span
          >
        </div>
      </div>
      <RouterLink
        class="btn btn-outline-primary"
        :to="{ name: 'task', params: { gameId: task.game_id } }"
        >Открыть</RouterLink
      >
    </article>
  </section>
</template>
<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import {
  listSingleTaskCatalog,
  type SingleTaskCatalogItemDto,
} from "../lib/api";
import { difficultyLabel, difficultyOrder } from "../lib/taskCatalog";
const route = useRoute();
const router = useRouter();
const tasks = ref<SingleTaskCatalogItemDto[]>([]);
const isLoading = ref(true);
const errorMessage = ref("");
const routeSection = computed(() => String(route.params.section));
const selectedTopic = ref(
  typeof route.query.topic === "string" ? route.query.topic : "",
);
const selectedDifficulty = ref(
  typeof route.query.difficulty === "string" ? route.query.difficulty : "",
);
const sectionTasks = computed(() =>
  tasks.value.filter(
    (task) => (task.learning_section || "Другое") === routeSection.value,
  ),
);
const topicOptions = computed(() =>
  Array.from(new Set(sectionTasks.value.flatMap((task) => task.topics))).sort(),
);
const difficultyOptions = computed(() =>
  Array.from(
    new Set(
      sectionTasks.value
        .map((task) => task.difficulty)
        .filter((d): d is string => !!d),
    ),
  ).sort((a, b) => difficultyOrder(a) - difficultyOrder(b)),
);
const filteredTasks = computed(() =>
  sectionTasks.value.filter(
    (task) =>
      (!selectedTopic.value || task.topics.includes(selectedTopic.value)) &&
      (!selectedDifficulty.value ||
        task.difficulty === selectedDifficulty.value),
  ),
);
watch(
  [selectedTopic, selectedDifficulty],
  ([topic, difficulty]) =>
    void router.replace({
      query: { topic: topic || undefined, difficulty: difficulty || undefined },
    }),
);
watch(
  () => route.query,
  (query) => {
    selectedTopic.value = typeof query.topic === "string" ? query.topic : "";
    selectedDifficulty.value =
      typeof query.difficulty === "string" ? query.difficulty : "";
  },
);
onMounted(async () => {
  try {
    tasks.value = await listSingleTaskCatalog();
  } catch (e) {
    errorMessage.value =
      e instanceof Error ? e.message : "Не удалось загрузить задачи";
  } finally {
    isLoading.value = false;
  }
});
</script>
<style scoped>
.arena-materials-head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.arena-materials-head h1 {
  margin: 0;
}
.arena-materials-head > span {
  margin-left: auto;
  white-space: nowrap;
}
.arena-material-filters {
  display: flex;
  align-items: end;
  gap: 12px;
}
.arena-material-filters label {
  font-size: 12px;
  display: grid;
  gap: 4px;
  min-width: 180px;
}
.arena-material-task {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.arena-material-task h2 {
  margin: 0 0 8px;
}
.arena-material-task p {
  color: var(--agp-text-muted);
  margin: 0 0 12px;
}
@media (max-width: 600px) {
  .arena-material-filters {
    flex-wrap: wrap;
  }
  .arena-material-filters label {
    min-width: 0;
    flex: 1;
  }
  .arena-material-task {
    align-items: start;
  }
  .arena-materials-head h1 {
    font-size: 20px;
  }
}
</style>
