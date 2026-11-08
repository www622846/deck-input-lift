const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');
const code = readFileSync(new URL('../kwin/contents/code/main.js', `file://${__filename}`), 'utf8');
const copy = value => JSON.parse(JSON.stringify(value));

function signal() {
  const handlers = [];
  return { connect(fn) { handlers.push(fn); }, emit(...args) { handlers.slice().forEach(fn => fn(...args)); } };
}
function window(options = {}) {
  let geometry = { x: 0, y: 0, width: 1280, height: 760 };
  const w = {
    caption: 'Browser', resourceClass: 'firefox', normalWindow: true,
    resizeable: true, moveable: true, minimized: false, hidden: false,
    fullScreen: false, minSize: { width: 100, height: 100 },
    maxCalls: [],
    setMaximize(v, h) { this.maxCalls.push({ v, h }); },
    ...options
  };
  if (options.frameGeometry) geometry = copy(options.frameGeometry);
  for (const name of ['frameGeometryChanged', 'captionChanged', 'minimizedChanged', 'hiddenChanged',
    'desktopsChanged', 'activitiesChanged', 'windowShown', 'windowHidden', 'maximizedAboutToChange']) w[name] = signal();
  Object.defineProperty(w, 'frameGeometry', {
    get() { return copy(geometry); },
    set(value) {
      if (JSON.stringify(geometry) === JSON.stringify(value)) return;
      geometry = copy(value);
      w.frameGeometryChanged.emit();
    }
  });
  return w;
}
function keyboard(options = {}) {
  return window({ caption: 'Steam Input On-screen Keyboard', resourceClass: 'steam',
    normalWindow: false, specialWindow: true,
    frameGeometry: { x: 0, y: 420, width: 1280, height: 380 }, ...options });
}
function boot(app, options = {}) {
  let current = app;
  let toggle;
  const workspace = { stackingOrder: [app], currentDesktop: 1, currentActivity: 'default',
    clientArea() { return options.area || { x: 0, y: 0, width: 1280, height: 760 }; } };
  const added = signal(), removed = signal(), activated = signal();
  if (options.legacy) {
    delete workspace.stackingOrder;
    workspace.clientList = () => [app];
    workspace.clientAdded = added; workspace.clientRemoved = removed; workspace.clientActivated = activated;
    Object.defineProperty(workspace, 'activeClient', { get: () => current });
  } else {
    workspace.windowAdded = added; workspace.windowRemoved = removed; workspace.windowActivated = activated;
    Object.defineProperty(workspace, 'activeWindow', { get: () => current });
  }
  for (const name of ['currentDesktopChanged', 'currentActivityChanged', 'screensChanged']) workspace[name] = signal();
  vm.runInNewContext(code, { workspace, KWin: { MaximizeArea: 2 },
    callDBus() {},
    readConfig: (name, fallback) => options.config?.[name] ?? fallback,
    registerShortcut: (id, label, keys, fn) => { toggle = fn; } });
  return { workspace,
    add(w) { added.emit(w); },
    remove(w) { removed.emit(w); },
    activate(w) { current = w; activated.emit(w); },
    toggle() { toggle(); }
  };
}

test('bottom keyboard fits the browser above it, then restores geometry and maximization', () => {
  const app = window(); const original = app.frameGeometry; const env = boot(app); const k = keyboard();
  env.add(k);
  assert.deepEqual(app.frameGeometry, { x: 0, y: 0, width: 1280, height: 408 });
  env.activate(k); // keyboard activation must not forget the app receiving text
  assert.equal(app.frameGeometry.height, 408);
  env.remove(k);
  assert.deepEqual(app.frameGeometry, original);
  assert.deepEqual(app.maxCalls.at(-1), { v: true, h: true });
});
test('opening a keyboard does not change an already non-overlapping window', () => {
  const app = window({ frameGeometry: { x: 10, y: 20, width: 800, height: 250 } });
  const env = boot(app); env.add(keyboard());
  assert.equal(app.maxCalls.length, 0);
  assert.equal(app.frameGeometry.height, 250);
});
test('keyboard movement updates reserved space and moving it away restores', () => {
  const app = window(); const env = boot(app); const k = keyboard(); env.add(k);
  k.frameGeometry = { x: 0, y: 500, width: 1280, height: 300 };
  assert.equal(app.frameGeometry.height, 488);
  k.frameGeometry = { x: 1280, y: 0, width: 1280, height: 400 };
  assert.equal(app.frameGeometry.height, 760);
});
test('top-docked keyboard places browser below the keyboard', () => {
  const app = window(); const env = boot(app);
  env.add(keyboard({ frameGeometry: { x: 0, y: 0, width: 1280, height: 300 } }));
  assert.deepEqual(app.frameGeometry, { x: 0, y: 312, width: 1280, height: 448 });
});
test('activation switches the resized app and restores the previous one', () => {
  const app = window(); const env = boot(app); const other = window({ resourceClass: 'chromium' });
  env.add(other); env.add(keyboard()); env.activate(other);
  assert.equal(app.frameGeometry.height, 760);
  assert.equal(other.frameGeometry.height, 408);
});
test('hidden/reused Steam keyboard restores and fits again', () => {
  const app = window(); const env = boot(app); const k = keyboard(); env.add(k);
  k.windowHidden.emit(); assert.equal(app.frameGeometry.height, 760);
  k.windowShown.emit(); assert.equal(app.frameGeometry.height, 408);
  k.minimized = true; k.minimizedChanged.emit(); assert.equal(app.frameGeometry.height, 760);
  k.minimized = false; k.minimizedChanged.emit(); assert.equal(app.frameGeometry.height, 408);
});
test('shortcut restores immediately and toggles back on', () => {
  const app = window(); const env = boot(app); env.add(keyboard());
  env.toggle(); assert.equal(app.frameGeometry.height, 760);
  env.toggle(); assert.equal(app.frameGeometry.height, 408);
});
test('does not match browser tabs whose titles mention the Steam keyboard', () => {
  const app = window(); const env = boot(app);
  env.add(window({ caption: 'Steam Input On-screen Keyboard', resourceClass: 'chromium' }));
  assert.equal(app.frameGeometry.height, 760);
});
test('another monitor or desktop keyboard does not resize this browser', () => {
  const app = window(); const env = boot(app);
  env.add(keyboard({ frameGeometry: { x: -1280, y: 420, width: 1280, height: 380 } }));
  env.add(keyboard({ desktop: 2 }));
  assert.equal(app.frameGeometry.height, 760);
});
test('Plasma 6 desktop and activity filtering', () => {
  const app = window(); const env = boot(app); const desktop = {};
  env.workspace.currentDesktop = desktop;
  const k = keyboard({ desktops: [{}] }); env.add(k);
  assert.equal(app.frameGeometry.height, 760);
  k.desktops = [desktop]; k.desktopsChanged.emit();
  assert.equal(app.frameGeometry.height, 408);
  k.activities = ['other']; k.activitiesChanged.emit();
  assert.equal(app.frameGeometry.height, 760);
});
test('rejects a keyboard leaving less than the app minimum height', () => {
  const app = window({ minSize: { width: 600, height: 450 } });
  const env = boot(app); env.add(keyboard());
  assert.equal(app.frameGeometry.height, 760);
});
test('fullscreen is restored when keyboard closes', () => {
  const app = window({ fullScreen: true }); const env = boot(app); const k = keyboard();
  env.add(k); assert.equal(app.fullScreen, false);
  env.remove(k); assert.equal(app.fullScreen, true);
});
test('partially maximized axes tracked by KWin are restored', () => {
  const app = window(); const env = boot(app);
  app.maximizedAboutToChange.emit(1);
  const k = keyboard(); env.add(k); env.remove(k);
  assert.deepEqual(app.maxCalls.at(-1), { v: false, h: true });
});
test('closed target is never restored or dereferenced as a live app', () => {
  const app = window(); const env = boot(app); const k = keyboard(); env.add(k);
  env.remove(app); app.deleted = true;
  app.setMaximize = () => { throw Error('dead window'); };
  env.remove(k);
});
test('legacy Plasma workspace APIs', () => {
  const app = window(); const env = boot(app, { legacy: true }); const k = keyboard();
  env.add(k); assert.equal(app.frameGeometry.height, 408);
  env.remove(k); assert.equal(app.frameGeometry.height, 760);
});
test('logical scaled coordinates, negative monitor origin and panel area', () => {
  const app = window({ frameGeometry: { x: -1024, y: 24, width: 1024, height: 592 } });
  const env = boot(app, { area: { x: -1024, y: 24, width: 1024, height: 592 } });
  env.add(keyboard({ frameGeometry: { x: -1024, y: 340, width: 1024, height: 300 } }));
  assert.deepEqual(app.frameGeometry, { x: -1024, y: 24, width: 1024, height: 304 });
});
test('keyboard caption config and gap validation', () => {
  const app = window(); const env = boot(app, { config: { KeyboardCaption: '로컬 키보드', Gap: -1 } });
  env.add(keyboard({ caption: '로컬 키보드' }));
  assert.equal(app.frameGeometry.height, 408);
});
test('screen removal restores the current session', () => {
  const app = window(); const env = boot(app); env.add(keyboard());
  env.workspace.screensChanged.emit();
  assert.equal(app.frameGeometry.height, 760);
});
test('switching desktop does not resize the app left on another desktop', () => {
  const app = window({ desktop: 1 }); const env = boot(app); env.add(keyboard({ desktop: -1 }));
  env.workspace.currentDesktop = 2;
  env.workspace.currentDesktopChanged.emit();
  assert.equal(app.frameGeometry.height, 760);
});
test('localized Korean Steam keyboard is recognized on the real device', () => {
  const app = window(); const env = boot(app); const k = keyboard({ caption: 'Steam Input 가상 키보드' });
  env.add(k); assert.equal(app.frameGeometry.height, 408);
  env.remove(k); assert.equal(app.frameGeometry.height, 760);
});
test('native maximizeMode takes precedence over geometry inference', () => {
  const app = window({ maximizeMode: 0 }); const env = boot(app); const k = keyboard();
  env.add(k); env.remove(k);
  assert.deepEqual(app.maxCalls.at(-1), { v: false, h: false });
});
