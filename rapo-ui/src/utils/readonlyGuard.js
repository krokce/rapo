// v-readonly-guard on an editor's form: while it has the `.editor-readonly` class (styles/app.sass), keys, paste, cut
// and drop never reach a field of a locked panel. The sheet's pointer-events stop only the mouse, so a field or button
// reached with Tab would still take them. The selectors mirror the sheet's: what it leaves usable stays usable.
const LOCKED = ".q-tab-panel:not(.editor-panel-open)";
const OPEN = ".cm-scroller, .editor-panel-open, .q-tabs, .email-sheet__head, .email-evaluate__head";
const OPEN_BUTTONS = ".email-sheet__head .q-btn, .email-evaluate__head .q-btn";
// Keys that only move the focus or copy: Tab, Escape, modifiers alone, and Ctrl/Cmd shortcuts but paste, cut, undo, redo.
const FREE_KEYS = new Set(["Tab", "Escape", "Shift", "Control", "Alt", "Meta"]);
const CHANGING_SHORTCUTS = new Set(["v", "x", "z", "y"]);
const BLOCKED_EVENTS = ["beforeinput", "paste", "cut", "drop"];

function locked(form, target) {
  if (!form.classList.contains("editor-readonly") || !(target instanceof Element)) {
    return false;
  }
  const panel = target.closest(LOCKED);
  if (!panel || !form.contains(panel)) {
    return false;
  }
  if (target.closest(OPEN_BUTTONS)) {
    return true;
  }
  const open = target.closest(OPEN);
  return !(open && panel.contains(open));
}

function freeKey(event) {
  if (FREE_KEYS.has(event.key)) {
    return true;
  }
  return (event.ctrlKey || event.metaKey) && !CHANGING_SHORTCUTS.has((event.key || "").toLowerCase());
}

function stop(event) {
  event.preventDefault();
  event.stopPropagation();
}

export const readonlyGuard = {
  mounted(el) {
    // Capturing on the form runs before the fields' own handlers, so a stopped event never reaches them.
    el._readonlyGuard = {
      keydown: (event) => {
        if (!freeKey(event) && locked(el, event.target)) {
          stop(event);
        }
      },
      other: (event) => {
        if (locked(el, event.target)) {
          stop(event);
        }
      },
    };
    el.addEventListener("keydown", el._readonlyGuard.keydown, true);
    for (const name of BLOCKED_EVENTS) {
      el.addEventListener(name, el._readonlyGuard.other, true);
    }
  },
  unmounted(el) {
    el.removeEventListener("keydown", el._readonlyGuard.keydown, true);
    for (const name of BLOCKED_EVENTS) {
      el.removeEventListener(name, el._readonlyGuard.other, true);
    }
  },
};
