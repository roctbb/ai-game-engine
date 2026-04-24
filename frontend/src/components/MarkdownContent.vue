<template>
  <div class="agp-markdown" v-html="renderedHtml"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  source: string;
}>();

const renderedHtml = computed(() => renderMarkdown(props.source));

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function renderInline(value: string): string {
  const codePlaceholders: string[] = [];
  let html = escapeHtml(value).replace(/`([^`]+)`/g, (_match, code: string) => {
    const token = `@@CODE${codePlaceholders.length}@@`;
    codePlaceholders.push(`<code>${code}</code>`);
    return token;
  });

  html = html
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>');

  for (const [index, code] of codePlaceholders.entries()) {
    html = html.replaceAll(`@@CODE${index}@@`, code);
  }
  return html;
}

function renderMarkdown(source: string): string {
  const lines = source.replace(/\r\n/g, '\n').split('\n');
  const blocks: string[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let listTag: 'ul' | 'ol' = 'ul';
  let codeLines: string[] = [];
  let inCodeBlock = false;

  const flushParagraph = (): void => {
    if (!paragraph.length) return;
    blocks.push(`<p>${renderInline(paragraph.join(' '))}</p>`);
    paragraph = [];
  };

  const flushList = (): void => {
    if (!listItems.length) return;
    blocks.push(`<${listTag}>${listItems.map((item) => `<li>${renderInline(item)}</li>`).join('')}</${listTag}>`);
    listItems = [];
    listTag = 'ul';
  };

  const flushCode = (): void => {
    blocks.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
    codeLines = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        flushCode();
        inCodeBlock = false;
      } else {
        flushParagraph();
        flushList();
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(rawLine);
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }

    const heading = /^(#{1,4})\s+(.+)$/.exec(line);
    if (heading) {
      flushParagraph();
      flushList();
      const level = heading[1].length;
      blocks.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
      continue;
    }

    const unorderedListItem = /^[-*]\s+(.+)$/.exec(line);
    if (unorderedListItem) {
      flushParagraph();
      if (listItems.length && listTag !== 'ul') flushList();
      listTag = 'ul';
      listItems.push(unorderedListItem[1]);
      continue;
    }

    const orderedListItem = /^\d+\.\s+(.+)$/.exec(line);
    if (orderedListItem) {
      flushParagraph();
      if (listItems.length && listTag !== 'ol') flushList();
      listTag = 'ol';
      listItems.push(orderedListItem[1]);
      continue;
    }

    flushList();
    paragraph.push(line.trim());
  }

  if (inCodeBlock) flushCode();
  flushParagraph();
  flushList();
  return blocks.join('');
}
</script>

<style scoped>
.agp-markdown {
  color: var(--agp-text);
  font-size: 0.95rem;
  line-height: 1.65;
}

.agp-markdown :deep(h1),
.agp-markdown :deep(h2),
.agp-markdown :deep(h3),
.agp-markdown :deep(h4) {
  margin: 1rem 0 0.45rem;
  color: var(--agp-text);
  line-height: 1.2;
}

.agp-markdown :deep(h1) {
  font-size: 1.55rem;
}

.agp-markdown :deep(h2) {
  font-size: 1.25rem;
}

.agp-markdown :deep(h3) {
  font-size: 1.05rem;
}

.agp-markdown :deep(p),
.agp-markdown :deep(ul),
.agp-markdown :deep(ol),
.agp-markdown :deep(pre) {
  margin: 0.6rem 0;
}

.agp-markdown :deep(ul),
.agp-markdown :deep(ol) {
  padding-left: 1.25rem;
}

.agp-markdown :deep(code) {
  border-radius: 0.3rem;
  background: #eef2f7;
  padding: 0.05rem 0.25rem;
  color: #0f172a;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.88em;
}

.agp-markdown :deep(pre) {
  overflow-x: auto;
  border: 1px solid var(--agp-border);
  border-radius: 0.45rem;
  background: #0f172a;
  padding: 0.75rem;
}

.agp-markdown :deep(pre code) {
  background: transparent;
  padding: 0;
  color: #e2e8f0;
}
</style>
