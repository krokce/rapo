// v-keyboard makes a clickable element that is not a button reachable with Tab and activated by Enter or Space.
// `v-keyboard:button` also gives it role="button"; a false value switches it off (a sortable column that is not).
function apply(el, binding) {
  if (binding.value === false) {
    el.removeAttribute("tabindex");
    el.removeAttribute("role");
    return;
  }
  el.setAttribute("tabindex", "0");
  if (binding.arg) {
    el.setAttribute("role", binding.arg);
  }
}

export const keyboard = {
  mounted(el, binding) {
    el.addEventListener("keydown", (event) => {
      if (el.hasAttribute("tabindex") && event.target === el && (event.key === "Enter" || event.key === " ")) {
        event.preventDefault();
        el.click();
      }
    });
    apply(el, binding);
  },
  updated: apply,
};
