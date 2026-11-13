"""
E-Waste Fault Identifier: complete project in ONE file.

Run locally:
    pip install flask anthropic
    set ANTHROPIC_API_KEY=your_key      (Windows)   |   export ANTHROPIC_API_KEY=your_key  (Mac/Linux)
    python app.py                       -> open http://localhost:5000
"""
import base64, json
from flask import Flask, request, jsonify, Response
import anthropic

app = Flask(__name__)
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
MODEL = "claude-sonnet-5-5"

PROMPT = r"""You are an expert electronics repair technician and e-waste recycling specialist. Analyze the attached photo of an electronic device / PCB. Return ONLY valid JSON (no markdown fences, no commentary) with exactly this shape:
{
 "device": {"type":"", "likely_model_or_category":"", "description":"2-3 sentences", "estimated_condition":"", "visible_damage":["..."]},
 "components": [{"name":"e.g. Electrolytic capacitor","count":"approx number or 'several'","location":"where on the board","status":"reusable"|"recyclable"|"waste","reason":"short reason"}],
 "metals": [{"metal":"Copper","where_found":"","approx_share":"low/medium/high","recovery_note":""}],
 "faults": [{"fault":"","evidence":"what in the image suggests it","likelihood":"low|medium|high","repairable":true|false,"repair_steps":["step 1","step 2"],"tools_needed":["..."]}],
 "verdict": {"repairable":true|false,"summary":"","reuse_advice":""},
 "disposal": {"hazardous_materials":["e.g. lead solder, lithium battery, brominated flame retardants"],"safe_disposal_steps":["..."],"do_not":["..."]},
 "confidence_note":"state limits of what can be seen in the photo"
}
Rules: list every distinct component type you can see (resistors, capacitors, ICs, transistors, diodes, inductors, connectors, batteries, displays, heat sinks, fans, switches, crystals, relays, wires etc). Mark status "reusable" if likely functional and desoldering-worthy (e.g. connectors, heatsinks, ICs, relays, intact passives), "recyclable" if it mainly holds recoverable material (e.g. PCB with copper/gold, batteries via certified recyclers, aluminium casings), "waste" if burnt/cracked/leaking/obsolete or has no recovery value. Be honest about uncertainty. If the image is not an electronic device, return {"error":"explanation"}."""

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" fill="#1f8a4c"/><text x="256" y="350" font-size="300" text-anchor="middle" fill="#fff">&#9851;</text></svg>"""

MANIFEST = {
    "name": "E-Waste Fault Identifier", "short_name": "E-Waste AI",
    "start_url": "/", "scope": "/", "display": "standalone",
    "background_color": "#0f1712", "theme_color": "#1f8a4c",
    "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"}],
}

SW_JS = """const CACHE='ewaste-v1';
self.addEventListener('install',e=>{self.skipWaiting();});
self.addEventListener('activate',e=>{self.clients.claim();});
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET')return;
  e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));
});
"""

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#1f8a4c">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="E-Waste AI">
<link rel="apple-touch-icon" href="/icon.svg">
<title>E-Waste Fault Identifier</title>
<style>
:root{--bg:#f5f8f5;--card:#fff;--text:#16241b;--muted:#5b6b60;--line:#dbe5dd;--accent:#1f8a4c;--accent-t:#fff;
--reuse:#1f8a4c;--reuse-bg:#e0f3e6;--rec:#b7791f;--rec-bg:#fbefd5;--waste:#c0392b;--waste-bg:#fbe3e0;
box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1712;--card:#18231c;--text:#e6f0e8;--muted:#98aa9e;--line:#2a3a2f;--accent:#3fbf76;--accent-t:#06150c;--reuse:#5fd38d;--reuse-bg:#1b3a27;--rec:#e8b04a;--rec-bg:#3a2e14;--waste:#f0786a;--waste-bg:#3d1e1a}}
:root[data-theme="dark"]{--bg:#0f1712;--card:#18231c;--text:#e6f0e8;--muted:#98aa9e;--line:#2a3a2f;--accent:#3fbf76;--accent-t:#06150c;--reuse:#5fd38d;--reuse-bg:#1b3a27;--rec:#e8b04a;--rec-bg:#3a2e14;--waste:#f0786a;--waste-bg:#3d1e1a}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.5}
.wrap{max-width:980px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:1.6rem;margin:0 0 4px}
.sub{color:var(--muted);margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:16px}
h2{font-size:1.1rem;margin:0 0 12px}
.drop{border:2px dashed var(--line);border-radius:12px;padding:28px;text-align:center;cursor:pointer;color:var(--muted)}
.drop:hover{border-color:var(--accent)}
#preview{max-width:100%;max-height:340px;border-radius:10px;display:none;margin:0 auto 12px}
button{background:var(--accent);color:var(--accent-t);border:0;border-radius:10px;padding:11px 20px;font-size:1rem;font-weight:600;cursor:pointer}
button:disabled{opacity:.5;cursor:not-allowed}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:12px}
.msg{color:var(--muted)}
.err{color:var(--waste)}
.tablewrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:560px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top;font-size:.93rem}
th{color:var(--muted);font-weight:600;font-size:.82rem;text-transform:uppercase;letter-spacing:.03em}
.badge{display:inline-block;padding:2px 10px;border-radius:99px;font-size:.8rem;font-weight:700}
.b-reuse{background:var(--reuse-bg);color:var(--reuse)}
.b-recycle{background:var(--rec-bg);color:var(--rec)}
.b-waste{background:var(--waste-bg);color:var(--waste)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}
.kv{background:var(--bg);border-radius:10px;padding:10px 12px}
.kv b{display:block;font-size:.78rem;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
.fault{border:1px solid var(--line);border-radius:10px;padding:12px;margin-bottom:10px}
.fault h3{margin:0 0 6px;font-size:1rem}
ol,ul{margin:6px 0;padding-left:20px}
.warn{background:var(--waste-bg);color:var(--text);border-left:4px solid var(--waste);border-radius:8px;padding:10px 14px}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.stat{flex:1;min-width:110px;border-radius:10px;padding:10px;text-align:center}
.stat b{display:block;font-size:1.5rem}
.hidden{display:none}
.note{font-size:.82rem;color:var(--muted);margin-top:14px}
</style>
</head>
<body>
<div class="wrap">
  <h1>♻️ E-Waste Fault Identifier</h1>
  <p class="sub">Upload a photo of an electronic device or circuit board to identify its components, faults, repair options, recoverable metals and safe disposal route.</p>

  <div class="card">
    <h2>1. Upload device image</h2>
    <img id="preview" alt="Uploaded device preview">
    <div class="drop" id="drop">Click to choose an image (or drag and drop)<br><small>JPG / PNG · clear, well-lit, close-up photos work best</small></div>
    <input type="file" id="file" accept="image/*" class="hidden">
    <input type="file" id="cam" accept="image/*" capture="environment" class="hidden">
    <div class="row">
      <button id="camBtn" type="button" style="background:var(--card);color:var(--text);border:1px solid var(--line)">📷 Take photo</button>
      <button id="go" disabled>Analyze device</button>
      <span id="status" class="msg"></span>
    </div>
  </div>

  <div id="results" class="hidden"></div>
  <p class="note">Results are AI estimates from a photo and may miss hidden or tiny parts. Always verify with a multimeter and follow local e-waste regulations. De-energize and discharge capacitors before opening any device.</p>
</div>

<script>
const $ = id => document.getElementById(id);
let blob = null;



$('drop').onclick = () => $('file').click();
$('drop').ondragover = e => e.preventDefault();
$('drop').ondrop = e => { e.preventDefault(); if (e.dataTransfer.files[0]) load(e.dataTransfer.files[0]); };
$('camBtn').onclick = () => $('cam').click();
$('cam').onchange = e => { if (e.target.files[0]) load(e.target.files[0]); };
$('file').onchange = e => { if (e.target.files[0]) load(e.target.files[0]); };

function load(f) {
  if (!f.type.startsWith('image/')) { $('status').textContent = 'Please choose an image file.'; return; }
  const img = new Image();
  img.onload = () => {
    const max = 1400, s = Math.min(1, max / Math.max(img.width, img.height));
    const c = document.createElement('canvas');
    c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
    c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
    c.toBlob(b => { blob = b; $('go').disabled = false; $('status').textContent = ''; }, 'image/jpeg', 0.88);
    $('preview').src = c.toDataURL('image/jpeg', 0.7);
    $('preview').style.display = 'block';
    $('drop').textContent = 'Click to choose a different image';
  };
  img.src = URL.createObjectURL(f);
}

const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const list = a => (a && a.length) ? '<ul>' + a.map(x => '<li>' + esc(x) + '</li>').join('') + '</ul>' : '<span class="msg">None noted</span>';
const badge = s => { s = String(s).toLowerCase(); const k = s.startsWith('reus') ? 'reuse' : s.startsWith('recyc') ? 'recycle' : 'waste'; return `<span class="badge b-${k}">${esc(s)}</span>`; };

$('go').onclick = async () => {
  if (!blob) return;
  $('go').disabled = true; $('status').className = 'msg'; $('status').textContent = 'Analyzing… this can take 20–40 seconds.';
  try {
    const fd = new FormData();
    fd.append('image', blob, 'device.jpg');
    const res = await fetch('/analyze', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Server error ' + res.status);
    render(data);
    $('status').textContent = '';
  } catch (e) {
    $('status').className = 'err';
    $('status').textContent = 'Could not analyze: ' + (e.message || e.code || e);
  }
  $('go').disabled = false;
};

function render(d) {
  const R = $('results'); R.classList.remove('hidden');
  if (d.error) { R.innerHTML = `<div class="card"><h2>Not an electronic device</h2><p>${esc(d.error)}</p></div>`; return; }
  const comps = d.components || [];
  const n = k => comps.filter(c => String(c.status).toLowerCase().startsWith(k)).length;
  const dv = d.device || {}, v = d.verdict || {}, ds = d.disposal || {};
  R.innerHTML = `
  <div class="card"><h2>2. Device information</h2>
    <div class="grid">
      <div class="kv"><b>Device type</b>${esc(dv.type)}</div>
      <div class="kv"><b>Model / category</b>${esc(dv.likely_model_or_category)}</div>
      <div class="kv"><b>Condition</b>${esc(dv.estimated_condition)}</div>
      <div class="kv"><b>Repairable?</b>${v.repairable ? '✅ Yes' : '❌ Unlikely'}</div>
    </div>
    <p>${esc(dv.description)}</p>
    ${(dv.visible_damage||[]).length ? '<b>Visible damage</b>' + list(dv.visible_damage) : ''}
  </div>

  <div class="card"><h2>3. Components found</h2>
    <div class="stats">
      <div class="stat b-reuse"><b>${n('reus')}</b>Reusable</div>
      <div class="stat b-recycle"><b>${n('recyc')}</b>Recyclable</div>
      <div class="stat b-waste"><b>${n('waste')}</b>Waste</div>
    </div>
    <div class="tablewrap"><table>
      <tr><th>Component</th><th>Qty</th><th>Location</th><th>Status</th><th>Why</th></tr>
      ${comps.map(c => `<tr><td><b>${esc(c.name)}</b></td><td>${esc(c.count)}</td><td>${esc(c.location)}</td><td>${badge(c.status)}</td><td>${esc(c.reason)}</td></tr>`).join('')}
    </table></div>
  </div>

  <div class="card"><h2>4. Metals present</h2>
    <div class="tablewrap"><table>
      <tr><th>Metal</th><th>Found in</th><th>Amount</th><th>Recovery note</th></tr>
      ${(d.metals||[]).map(m => `<tr><td><b>${esc(m.metal)}</b></td><td>${esc(m.where_found)}</td><td>${esc(m.approx_share)}</td><td>${esc(m.recovery_note)}</td></tr>`).join('')}
    </table></div>
  </div>

  <div class="card"><h2>5. Possible faults &amp; repair</h2>
    ${(d.faults||[]).map(f => `<div class="fault">
      <h3>${esc(f.fault)} <span class="badge ${f.repairable ? 'b-reuse' : 'b-waste'}">${f.repairable ? 'repairable' : 'not economical'}</span>
      <span class="badge b-recycle">${esc(f.likelihood)} likelihood</span></h3>
      <div class="msg">Evidence: ${esc(f.evidence)}</div>
      <b>How to repair</b><ol>${(f.repair_steps||[]).map(s => '<li>' + esc(s) + '</li>').join('')}</ol>
      <div class="msg">Tools: ${esc((f.tools_needed||[]).join(', '))}</div></div>`).join('')}
    <p><b>Verdict:</b> ${esc(v.summary)}</p>
    <p><b>Reuse advice:</b> ${esc(v.reuse_advice)}</p>
  </div>

  <div class="card"><h2>6. Safe disposal (if not repairable)</h2>
    <div class="warn"><b>Hazardous materials</b>${list(ds.hazardous_materials)}</div>
    <p><b>Steps</b></p><ol>${(ds.safe_disposal_steps||[]).map(s => '<li>' + esc(s) + '</li>').join('')}</ol>
    <p><b>Do not</b></p>${list(ds.do_not)}
  </div>
  <p class="note">${esc(d.confidence_note)}</p>`;
  R.scrollIntoView({behavior: 'smooth'});
}
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{});
</script>
</body>
</html>
"""


@app.get("/")
def home():
    return Response(INDEX_HTML, mimetype="text/html")

@app.get("/manifest.json")
def manifest():
    return jsonify(MANIFEST)

@app.get("/icon.svg")
def icon():
    return Response(ICON_SVG, mimetype="image/svg+xml")

@app.get("/sw.js")
def sw():
    return Response(SW_JS, mimetype="text/javascript",
                    headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})

@app.post("/analyze")
def analyze():
    f = request.files.get("image")
    if not f:
        return jsonify(error="No image uploaded"), 400
    img_b64 = base64.b64encode(f.read()).decode()
    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                {"type": "text", "text": PROMPT},
            ]}],
        )
        text = msg.content[0].text.strip().replace("```json", "").replace("```", "")
        return jsonify(json.loads(text[text.index("{"): text.rindex("}") + 1]))
    except Exception as e:
        return jsonify(error=str(e)), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
