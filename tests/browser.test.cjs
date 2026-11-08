const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const { readFileSync } = require('node:fs');
const code = readFileSync(new URL('../browser/focus-guard.js', `file://${__filename}`), 'utf8');

function setup(element) {
  const listeners = {};
  let timer;
  const w = { innerHeight: 320, addEventListener(name, fn) { listeners[name] = fn; } };
  const d = { activeElement: element, addEventListener(name, fn) { listeners[name] = fn; } };
  vm.runInNewContext(code, { window: w, document: d,
    clearTimeout() { timer = null; }, setTimeout(fn) { timer = fn; return 1; } });
  return { w, d, trigger(name = 'resize') { listeners[name](); timer(); } };
}
function input(box, properties = {}) {
  const el = { tagName: 'INPUT', type: 'search', calls: 0, getBoundingClientRect: () => box,
    scrollIntoView(options) { el.calls++; el.options = options; }, ...properties };
  Object.defineProperty(el, 'value', { get() { throw Error('must never read typed values'); } });
  return el;
}
test('browser resize scrolls an obscured original input without reading or copying text', () => {
  const el = input({ top: 500, bottom: 540 }); setup(el).trigger();
  assert.equal(el.calls, 1);
  assert.equal(el.options.block, 'center');
});
test('visible focused input does not jump while typing', () => {
  const el = input({ top: 100, bottom: 140 }); setup(el).trigger();
  assert.equal(el.calls, 0);
});
test('focusin handles nested scroll containers through native scrollIntoView', () => {
  const el = input({ top: 500, bottom: 540 }, { tagName: 'TEXTAREA' });
  setup(el).trigger('focusin'); assert.equal(el.calls, 1);
});
test('native password field uses geometry only', () => {
  const el = input({ top: 500, bottom: 540 }, { type: 'password' });
  setup(el).trigger(); assert.equal(el.calls, 1);
});
test('open shadow-root input receives scroll correction', () => {
  const el = input({ top: 500, bottom: 540 });
  setup({ shadowRoot: { activeElement: el } }).trigger(); assert.equal(el.calls, 1);
});
test('buttons and unfocused document are ignored', () => {
  const el = input({ top: 500, bottom: 540 }, { type: 'button' });
  setup(el).trigger(); assert.equal(el.calls, 0);
  setup(null).trigger();
});
test('contenteditable retains its native editor and composition', () => {
  const el = input({ top: -50, bottom: 10 }, { tagName: 'DIV', isContentEditable: true });
  setup(el).trigger(); assert.equal(el.calls, 1);
});
test('visual viewport offset is respected', () => {
  const el = input({ top: 20, bottom: 60 }); const env = setup(el);
  env.w.visualViewport = { offsetTop: 100, height: 200 };
  env.trigger(); assert.equal(el.calls, 1);
});
