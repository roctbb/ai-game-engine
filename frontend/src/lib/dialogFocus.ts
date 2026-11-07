import { nextTick, type ObjectDirective } from 'vue';

const dialogs: HTMLElement[] = [];
const cleanups = new WeakMap<HTMLElement, () => void>();
let previousOverflow = '';

function focusable(element: HTMLElement): HTMLElement[] {
  return Array.from(element.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"]), [contenteditable="true"]'))
    .filter((item) => item.getClientRects().length > 0 && !item.closest('[inert]'));
}

export const dialogFocus: ObjectDirective<HTMLElement, (() => void) | undefined> = {
  mounted(element, binding) {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    element.setAttribute('aria-modal', 'true');
    element.tabIndex = -1;
    if (dialogs.length === 0) {
      previousOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
    }
    dialogs.push(element);

    const focusFirst = () => (focusable(element)[0] ?? element).focus({ preventScroll: true });
    const onKeydown = (event: KeyboardEvent) => {
      if (dialogs.at(-1) !== element) return;
      if (event.key === 'Escape' && binding.value) {
        event.preventDefault();
        event.stopImmediatePropagation();
        binding.value();
      }
      if (event.key !== 'Tab') return;
      const items = focusable(element);
      const current = items.indexOf(document.activeElement as HTMLElement);
      if (!items.length || (event.shiftKey && current <= 0) || (!event.shiftKey && (current === items.length - 1 || current === -1))) {
        event.preventDefault();
        (event.shiftKey ? items.at(-1) ?? element : items[0] ?? element).focus();
      }
    };
    const onFocus = (event: FocusEvent) => {
      if (dialogs.at(-1) === element && event.target instanceof Node && !element.contains(event.target)) focusFirst();
    };
    document.addEventListener('keydown', onKeydown, true);
    document.addEventListener('focusin', onFocus, true);
    void nextTick(() => { if (element.isConnected && dialogs.at(-1) === element) focusFirst(); });

    cleanups.set(element, () => {
      document.removeEventListener('keydown', onKeydown, true);
      document.removeEventListener('focusin', onFocus, true);
      const index = dialogs.indexOf(element);
      if (index !== -1) dialogs.splice(index, 1);
      if (!dialogs.length) document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
      cleanups.delete(element);
    });
  },
  beforeUnmount(element) {
    cleanups.get(element)?.();
  },
};
