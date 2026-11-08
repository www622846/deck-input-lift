const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/patch.js', 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));

function setup() {
  const output = [], requests = [];
  const context = {process_key_event: async (...args) => { output.push(['native', ...args]); return true; },
    reset: async () => { output.push(['native-reset']); }};
  const originalProcess = context.process_key_event;
  const originalReset = context.reset;
  const manager = {HandleVirtualKeyDown: (...args) => { output.push(args); }};
  const originalHandle = manager.HandleVirtualKeyDown;
  const instance = {context, props:{bStandalone:true,VirtualKeyboardManager:manager},
    state:{standardLayout:{name:'korean'}},TypeKeyInternal(){}};
  const element = {__reactFiberTest:{stateNode:instance}};
  const timers = new Map(); let sequence = 0;
  const window = {__deckHangulNative: value => requests.push(JSON.parse(value))};
  vm.runInNewContext(source, {window, document:{querySelectorAll:()=>[element]},
    setInterval(fn){timers.set(++sequence,fn);return sequence;}, clearInterval(id){timers.delete(id);},
    setTimeout, clearTimeout, console});
  const api = window.__deckSteamHangul;
  return {window,api,context,manager,instance,output,requests,originalProcess,originalReset,originalHandle,
    reply(index,result){api.receive({id:requests[index].id,result});}, timers};
}

test('only one composing key is sent until the earlier edit is delivered', async () => {
  const s=setup();
  const first=s.context.process_key_event(114,19,0);
  const second=s.context.process_key_event(106,44,0);
  await settle(); assert.equal(s.requests.length,1);
  s.reply(0,{consumed:true,delete:0,insert:'ㄱ'}); await first; await settle();
  assert.equal(s.requests.length,2);
  s.reply(1,{consumed:true,delete:1,insert:'거'}); await second;
  assert.deepEqual(s.output,[['ㄱ',false],['Backspace',false],['거',false]]);
  s.api.uninstall();
});
test('native IBus reset notifications do not discard the custom composing syllable', async () => {
  const s=setup(); await s.context.reset();
  assert.deepEqual(s.output,[]); assert.equal(s.requests.length,0);
  s.api.uninstall();
});
test('English and other layouts keep the original input method', async () => {
  const s=setup(); s.instance.state.standardLayout.name='english';
  await s.context.process_key_event(114,19,0);
  assert.deepEqual(s.output,[['native',114,19,0]]); assert.equal(s.requests.length,0);
  s.api.uninstall();
});
test('literal/native controls wait for composing keys and preserve ordering', async () => {
  const s=setup(); const letter=s.context.process_key_event(114,19,0);
  const boundary=s.manager.HandleVirtualKeyDown('ArrowLeft',false);
  await settle(); s.reply(0,{consumed:true,delete:0,insert:'ㄱ'}); await letter; await settle();
  assert.equal(s.requests[1].op,'reset');
  s.reply(1,{consumed:true}); await boundary;
  assert.deepEqual(s.output,[['ㄱ',false],['ArrowLeft',false]]);
  s.api.uninstall();
});
test('backend failure restores stock functions and passes the key to stock IBus', async () => {
  const s=setup(); const key=s.context.process_key_event(114,19,0); await settle();
  s.api.receive({id:s.requests[0].id,error:true}); await key;
  assert.equal(s.context.process_key_event,s.originalProcess);
  assert.equal(s.context.reset,s.originalReset);
  assert.equal(s.manager.HandleVirtualKeyDown,s.originalHandle);
  assert.deepEqual(s.output,[['native',114,19,0]]);
});
test('uninstall restores all functions without changing target text', () => {
  const s=setup(); s.api.uninstall();
  assert.equal(s.context.process_key_event,s.originalProcess);
  assert.equal(s.context.reset,s.originalReset);
  assert.equal(s.manager.HandleVirtualKeyDown,s.originalHandle);
  assert.deepEqual(s.output,[]);
});
test('a reopened keyboard is hooked before its first key, without waiting for a poll', async () => {
  const s=setup();
  const proto={TypeKeyInternal(){return this.context.process_key_event(114,19,0);}};
  const originalType=proto.TypeKeyInternal;
  assert.equal(s.api.attachPrototype(proto),true);
  const next=Object.assign(Object.create(proto),{
    context:{process_key_event:async()=>{throw Error('first key reached stock');},reset:async()=>{}},
    props:{bStandalone:true,VirtualKeyboardManager:{HandleVirtualKeyDown:(...args)=>s.output.push(args)}},
    state:{standardLayout:{name:'korean'}}
  });
  const key=next.TypeKeyInternal();
  await settle(); assert.equal(s.requests[0].op,'reset');
  s.reply(0,{consumed:true}); await settle();
  assert.equal(s.requests[1].op,'key');
  s.reply(1,{consumed:true,delete:0,insert:'ㄱ'}); await key;
  assert.deepEqual(s.output,[['ㄱ',false]]);
  s.api.uninstall(); assert.equal(proto.TypeKeyInternal,originalType);
});
test('inline keyboards sharing a context retain the stock input path', async () => {
  const s=setup();
  const proto={TypeKeyInternal(){return this.context.process_key_event(114,19,0);}};
  s.api.attachPrototype(proto);
  const inline=Object.assign(Object.create(proto),{
    context:s.context,props:{bStandalone:false},state:{standardLayout:{name:'korean'}}
  });
  await inline.TypeKeyInternal(); await settle();
  assert.deepEqual(s.output,[['native',114,19,0]]);
  if (s.requests.length) s.reply(0,{consumed:true});
  s.api.uninstall();
});
