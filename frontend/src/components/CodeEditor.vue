<template>
  <div ref="host" class="agp-code-editor" :class="{ 'agp-code-editor--readonly': readonly }"></div>
</template>

<script setup lang="ts">
import { basicSetup } from 'codemirror';
import { history, historyKeymap, indentWithTab, defaultKeymap } from '@codemirror/commands';
import { Compartment, EditorState, type Extension } from '@codemirror/state';
import { python } from '@codemirror/lang-python';
import { oneDark } from '@codemirror/theme-one-dark';
import {
  drawSelection,
  EditorView,
  highlightActiveLine,
  keymap,
  lineNumbers,
} from '@codemirror/view';
import { onMounted, onUnmounted, ref, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    modelValue: string;
    readonly?: boolean;
    language?: 'python' | 'plain';
  }>(),
  {
    readonly: false,
    language: 'python',
  }
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
}>();

const host = ref<HTMLElement | null>(null);
let editorView: EditorView | null = null;
const languageCompartment = new Compartment();
const readOnlyCompartment = new Compartment();

function resolveLanguage(): Extension {
  if (props.language === 'python') {
    return python();
  }
  return [];
}

function ensureEditor(): void {
  if (!host.value || editorView) {
    return;
  }

  const updateListener = EditorView.updateListener.of((update) => {
    if (!update.docChanged) {
      return;
    }
    emit('update:modelValue', update.state.doc.toString());
  });

  const editorTheme = EditorView.theme({
    '&': {
      minHeight: '22rem',
      borderRadius: '0.75rem',
      border: '1px solid var(--agp-border)',
      overflow: 'hidden',
      fontSize: '0.9rem',
    },
    '.cm-scroller': {
      fontFamily: 'IBM Plex Mono, monospace',
      lineHeight: '1.5',
    },
    '.cm-content': {
      padding: '0.75rem 0',
    },
    '.cm-line': {
      padding: '0 0.75rem',
    },
  });

  const startState = EditorState.create({
    doc: props.modelValue ?? '',
    extensions: [
      basicSetup,
      history(),
      lineNumbers(),
      drawSelection(),
      highlightActiveLine(),
      keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
      EditorView.lineWrapping,
      oneDark,
      editorTheme,
      languageCompartment.of(resolveLanguage()),
      readOnlyCompartment.of(EditorState.readOnly.of(props.readonly)),
      updateListener,
    ],
  });

  editorView = new EditorView({
    state: startState,
    parent: host.value,
  });
}

onMounted(() => {
  ensureEditor();
});

onUnmounted(() => {
  if (editorView) {
    editorView.destroy();
    editorView = null;
  }
});

watch(
  () => props.modelValue,
  (nextValue) => {
    if (!editorView) return;
    const currentValue = editorView.state.doc.toString();
    const normalized = nextValue ?? '';
    if (currentValue === normalized) return;
    editorView.dispatch({
      changes: { from: 0, to: currentValue.length, insert: normalized },
    });
  }
);

watch(
  () => props.readonly,
  (nextReadonly) => {
    if (!editorView) return;
    editorView.dispatch({
      effects: readOnlyCompartment.reconfigure(EditorState.readOnly.of(nextReadonly)),
    });
  }
);

watch(
  () => props.language,
  () => {
    if (!editorView) return;
    editorView.dispatch({
      effects: languageCompartment.reconfigure(resolveLanguage()),
    });
  }
);
</script>

<style scoped>
.agp-code-editor {
  width: 100%;
}

.agp-code-editor--readonly :deep(.cm-content) {
  opacity: 0.92;
}
</style>
