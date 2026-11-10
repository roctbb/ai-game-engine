<template>
  <div class="arena-roster">
    <div v-if="teamIds.length <= 5" class="arena-roster-list">
      <div
        v-for="id in teamIds"
        :key="id"
        :class="{ 'arena-roster-self': id === myTeamId }"
      >
        <span>{{ nameFor(id) }}<small v-if="id === myTeamId"> · вы</small></span
        ><strong
          >{{ scores?.[id] ?? "—"
          }}<span v-if="advanced?.includes(id)" class="text-success">
            ✓</span
          ></strong
        >
      </div>
    </div>
    <template v-else
      ><div
        v-if="myTeamId && teamIds.includes(myTeamId)"
        class="arena-roster-personal"
      >
        Ваш результат <strong>{{ scores?.[myTeamId] ?? "—" }}</strong>
      </div>
      <details>
        <summary>{{ teamIds.length }} игроков · состав и результаты</summary>
        <ol>
          <li v-for="id in teamIds" :key="id">
            <div class="arena-roster-result">
              <span
                >{{ nameFor(id)
                }}<small v-if="id === myTeamId"> · вы</small></span
              ><strong
                >{{ scores?.[id] ?? "—"
                }}<span v-if="advanced?.includes(id)" class="text-success">
                  ✓</span
                ></strong
              >
            </div>
          </li>
        </ol>
      </details></template
    >
  </div>
</template>
<script setup lang="ts">
defineProps<{
  teamIds: string[];
  nameFor: (id: string) => string;
  scores?: Record<string, number>;
  advanced?: string[];
  myTeamId?: string | null;
}>();
</script>
<style scoped>
.arena-roster-list {
  display: grid;
  gap: 4px;
}
.arena-roster-list > div,
.arena-roster-result,
.arena-roster-personal {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 8px;
  border-radius: 6px;
}
.arena-roster-self {
  background: var(--agp-primary-soft);
}
.arena-roster strong {
  font-family: "JetBrains Mono", monospace;
  font-weight: 500;
}
.arena-roster small {
  color: var(--agp-text-muted);
}
.arena-roster-personal {
  padding-left: 0;
  margin-bottom: 4px;
}
</style>
