"""Exercise the actual Focus Guard code in a local, headless Chromium browser."""
from pathlib import Path
import argparse
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--chrome", required=True)
args = parser.parse_args()
source = (Path(__file__).resolve().parents[1] / "browser/focus-guard.js").read_text()
fixture = r'''<!doctype html><meta charset="utf-8">
<style>
body { margin:0; height:3000px }
.spacer { height:1000px }
#panel { margin:10px; height:250px; overflow:auto }
input,textarea,[contenteditable] { display:block; height:40px; width:400px; font-size:22px }
</style>
<div class="spacer"></div><div id="panel"><div class="spacer"></div>
<input id="search" type="search" value="스팀덱 검색 테스트">
<textarea id="text">한글 조합을 유지합니다</textarea>
<input id="password" type="password" value="local-fixture">
<div id="editable" contenteditable="true">테스트</div>
<div class="spacer"></div></div><div class="spacer"></div>
<script>__SOURCE__</script>
<script>
const results = [];
const ids = ['search','text','password','editable'];
let changes = 0;
document.addEventListener('input', () => changes++);
function next(i) {
  if (i === ids.length) {
    document.body.setAttribute('data-results', JSON.stringify(results));
    document.body.setAttribute('data-changes', String(changes));
    return;
  }
  const el = document.getElementById(ids[i]);
  window.scrollTo(0, 0);
  document.getElementById('panel').scrollTop = 0;
  const before = el.value === undefined ? el.textContent : el.value;
  el.focus({preventScroll:true});
  window.dispatchEvent(new Event('resize'));
  setTimeout(() => {
    const r = el.getBoundingClientRect();
    const after = el.value === undefined ? el.textContent : el.value;
    results.push({id:ids[i], visible:r.top >= 0 && r.bottom <= window.innerHeight,
      unchanged:before === after});
    next(i+1);
  }, 400);
}
next(0);
</script>'''.replace("__SOURCE__", source)

with tempfile.TemporaryDirectory(prefix="deck-input-browser-") as folder:
    page = Path(folder) / "fixture.html"
    page.write_text(fixture)
    result = subprocess.run([
        args.chrome, "--headless", "--disable-gpu", "--no-first-run",
        "--disable-background-networking", "--disable-extensions",
        "--user-data-dir=" + str(Path(folder) / "profile"),
        "--window-size=1280,420", "--virtual-time-budget=4000",
        "--dump-dom", page.as_uri(),
    ], capture_output=True, text=True, timeout=25)
    if result.returncode:
        raise SystemExit("Chrome exited with code " + str(result.returncode) + ": " + result.stderr[-1500:])
    from html.parser import HTMLParser
    import json

    class Attributes(HTMLParser):
        data = None
        def handle_starttag(self, tag, attrs):
            if tag == "body":
                self.data = dict(attrs)

    parsed = Attributes()
    parsed.feed(result.stdout)
    assert parsed.data and "data-results" in parsed.data, result.stdout[-1000:]
    results = json.loads(parsed.data["data-results"])
    assert len(results) == 4, results
    assert all(item["visible"] and item["unchanged"] for item in results), results
    assert parsed.data["data-changes"] == "0", parsed.data
    print("PASS: search, textarea, password, contenteditable in nested scrolling container")
    print("PASS: original Korean text unchanged; no synthetic input events")
