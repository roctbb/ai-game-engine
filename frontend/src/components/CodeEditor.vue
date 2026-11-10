<template>
  <div ref="host" class="agp-code-editor" :class="{ 'agp-code-editor--readonly': readonly }"></div>
</template>

<script setup lang="ts">
import { basicSetup } from 'codemirror';
import { history, historyKeymap, indentWithTab, defaultKeymap } from '@codemirror/commands';
import { Compartment, EditorState, RangeSet, type Extension } from '@codemirror/state';
import { python } from '@codemirror/lang-python';
import { oneDark } from '@codemirror/theme-one-dark';
import {
  drawSelection,
  EditorView,
  highlightActiveLine,
  keymap,
  lineNumbers,
  Decoration,
  gutterLineClass,
  GutterMarker,
} from '@codemirror/view';
import { onMounted, onUnmounted, ref, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    modelValue: string;
    readonly?: boolean;
    language?: 'python' | 'plain';
    focusLine?: number;
    errorLine?: number;
  }>(),
  {
    readonly: false,
    language: 'python',
  }
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
  (e: 'run'): void;
}>();

const host = ref<HTMLElement | null>(null);
let editorView: EditorView | null = null;
const languageCompartment = new Compartment();
const readOnlyCompartment = new Compartment();
const errorCompartment = new Compartment();
const themeCompartment = new Compartment();
const darkMedia = window.matchMedia('(prefers-color-scheme: dark)');
class ErrorGutter extends GutterMarker { elementClass = 'arena-error-gutter'; }
function errorExtension(doc: EditorState['doc']): Extension {
  if (!props.errorLine || props.errorLine > doc.lines) return [];
  const at = doc.line(Math.max(1, props.errorLine)).from;
  return [EditorView.decorations.of(Decoration.set([Decoration.line({ class: 'arena-code-error' }).range(at)])), gutterLineClass.compute([], () => RangeSet.of([new ErrorGutter().range(at)]))];
}
function updateColorTheme(): void { editorView?.dispatch({ effects: themeCompartment.reconfigure(darkMedia.matches ? oneDark : []) }); }

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
      minHeight: '0',
      borderRadius: '0.75rem',
      border: '1px solid var(--agp-border)',
      overflow: 'hidden',
      fontSize: '13px',
    },
    '.cm-scroller': {
      fontFamily: 'JetBrains Mono, monospace',
      lineHeight: '22px',
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
      keymap.of([{ key: 'Mod-Enter', run: () => { emit('run'); return true; } }, ...defaultKeymap, ...historyKeymap, indentWithTab]),
      EditorView.lineWrapping,
      EditorView.contentAttributes.of({ 'aria-label': props.language === 'python' ? 'Редактор кода Python' : 'Редактор кода' }),
      themeCompartment.of(darkMedia.matches ? oneDark : []),
      errorCompartment.of([]),
      editorTheme,
      languageCompartment.of(resolveLanguage()),
      readOnlyCompartment.of([EditorState.readOnly.of(props.readonly), EditorView.editable.of(!props.readonly), EditorView.contentAttributes.of({ 'aria-readonly': String(props.readonly), tabindex: '0' })]),
      updateListener,
    ],
  });

  editorView = new EditorView({
    state: startState,
    parent: host.value,
  });
  updateError();
}

function updateError(): void { if (editorView) editorView.dispatch({ effects: errorCompartment.reconfigure(errorExtension(editorView.state.doc)) }); }
watch(() => props.errorLine, updateError);

function focusLine(line: number): void {
  if (!editorView) return;
  const target = editorView.state.doc.line(Math.max(1, Math.min(Math.floor(line), editorView.state.doc.lines)));
  editorView.dispatch({ selection: { anchor: target.from, head: target.to }, effects: EditorView.scrollIntoView(target.from, { y: 'center' }) });
  editorView.focus();
}
defineExpose({ focusLine });
watch(() => props.focusLine, line => { if (line) focusLine(line); });

onMounted(() => {
  ensureEditor();
  darkMedia.addEventListener('change', updateColorTheme);
  if (props.focusLine) focusLine(props.focusLine);
});

onUnmounted(() => {
  darkMedia.removeEventListener('change', updateColorTheme);
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
    updateError();
  }
);

watch(
  () => props.readonly,
  (nextReadonly) => {
    if (!editorView) return;
    editorView.dispatch({
      effects: readOnlyCompartment.reconfigure([EditorState.readOnly.of(nextReadonly), EditorView.editable.of(!nextReadonly), EditorView.contentAttributes.of({ 'aria-readonly': String(nextReadonly), tabindex: '0' })]),
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
.agp-code-editor :deep(.arena-code-error) { background: var(--arena-error-soft); box-shadow: inset 3px 0 var(--agp-danger); }
.agp-code-editor :deep(.arena-error-gutter) { color: var(--agp-danger); background: var(--arena-error-soft); font-weight: 700; }
</style>
