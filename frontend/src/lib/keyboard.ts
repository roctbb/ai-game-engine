export function isShortcutInput(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && Boolean(target.closest(
    '.cm-editor, input, textarea, select, button, a, summary, [contenteditable="true"], [role="dialog"]',
  ));
}
