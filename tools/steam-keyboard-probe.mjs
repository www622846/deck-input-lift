// Developer-only: press actual Steam keyboard keys through a loopback CDP tunnel.
// Reads key labels and positions, never the target application's text.
const options = process.argv.slice(2);
const domClick = options.includes('--dom-click');
const touch = options.includes('--touch');
const delay = Number(options.find(x=>x.startsWith('--delay='))?.slice(8) ?? 250);
const labels = options.filter(x=>!x.startsWith('--'));
const endpoint = 'http://127.0.0.1:18081/json';
const pages = await (await fetch(endpoint)).json();
const page = pages.find(p => ['Steam Input 가상 키보드', 'Steam Input On-screen Keyboard'].includes(p.title));
if (!page) throw Error('Steam keyboard target not found');
const ws = new WebSocket(page.webSocketDebuggerUrl.replace(':8081/', ':18081/'));
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
let sequence = 0;
const pending = new Map();
ws.onmessage = event => {
  const result = JSON.parse(event.data);
  const callback = pending.get(result.id);
  if (callback) { pending.delete(result.id); callback(result); }
};
function command(method, params) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(Error('CDP timeout')); }, 8000);
    pending.set(id, result => {
      clearTimeout(timer);
      if (result.error) reject(Error(JSON.stringify(result.error)));
      else resolve(result.result);
    });
    ws.send(JSON.stringify({id, method, params}));
  });
}
try {
  for (const label of labels) {
    const expression = `(() => {
      const label = ${JSON.stringify(label)};
      let key, point;
      const matches = e => e && (e.innerText.split('\\n').at(-1) === label || e.getAttribute('aria-label') === label);
      // Steam can retain occluded layout copies. Hit-test the keyboard's own
      // viewport to select an actually displayed key, without capturing pixels.
      outer: for(let y=8;y<innerHeight;y+=12) for(let x=8;x<innerWidth;x+=12) {
        const e=document.elementFromPoint(x,y)?.closest('[role="button"],button');
        if(matches(e)) {key=e;point={x,y};break outer;}
      }
      if (!key) throw Error('Key not found');
      if (${domClick}) key.click();
      return point;
    })()`;
    const result = await command('Runtime.evaluate', {expression, returnByValue:true});
    if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
    const point = result.result.value;
    if (touch) {
      await command('Input.dispatchTouchEvent', {type:'touchStart',touchPoints:[{...point,id:0,radiusX:2,radiusY:2,force:1}]});
      await command('Input.dispatchTouchEvent', {type:'touchEnd',touchPoints:[]});
    } else if (!domClick) {
      await command('Input.dispatchMouseEvent', {type:'mouseMoved',...point});
      await command('Input.dispatchMouseEvent', {type:'mousePressed',...point,button:'left',clickCount:1});
      await command('Input.dispatchMouseEvent', {type:'mouseReleased',...point,button:'left',clickCount:1});
    }
    await new Promise(resolve => setTimeout(resolve, delay));
  }
  console.log('Pressed Steam keyboard keys:', labels.join(' '));
} finally {
  ws.close();
}
