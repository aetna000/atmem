"""Functional two-state dashboard for OpenClaw memory takeover.

The dashboard has no external assets or JavaScript dependencies. It presents
only the customer decisions that matter: inspect/search the mirror, activate
AtMem, or restore OpenClaw.
"""

APP_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AtMem for OpenClaw</title>
<style>
:root{
  --bg:#f3f5f8;--card:#fff;--card-raised:#fff;--ink:#101828;--muted:#667085;--line:#e4e7ec;
  --brand:#2f2b29;--brand-soft:#eceae8;--on-brand:#fff;--blue:#4d4845;--blue-soft:#f0efee;
  --good:#18794e;--good-soft:#e4f2e9;--warn:#9a5b00;--warn-soft:#f7eddc;
  --bad:#b42318;--bad-soft:#fce8e6;--danger-action:#d92d20;
  --shadow:0 1px 2px #0e1f1b08,0 1px 1px #0e1f1b0a;
  --shadow-md:0 2px 4px #0e1f1b08,0 16px 32px -12px #0e1f1b1a;
  --shadow-lg:0 4px 10px #0e1f1b0d,0 24px 48px -16px #0e1f1b26;
  --radius:16px;--radius-sm:10px
}
@media(prefers-color-scheme:dark){:root{
  --bg:#080808;--card:#151515;--card-raised:#1d1c1b;--ink:#feffff;--muted:#aaa6a3;--line:#34302e;
  --brand:#feffff;--brand-soft:#2f2b29;--on-brand:#080808;--blue:#feffff;--blue-soft:#2f2b29;
  --good:#6ce9a6;--good-soft:#123126;--warn:#fdbf6f;--warn-soft:#3a2812;
  --bad:#fda29b;--bad-soft:#3b191c;--danger-action:#f04438;
  --shadow:0 1px 2px #0006,0 1px 1px #0004;
  --shadow-md:0 2px 4px #0006,0 16px 32px -12px #0009;
  --shadow-lg:0 4px 10px #0007,0 24px 48px -16px #000c
}}
:root[data-theme="light"]{
  --bg:#f3f5f8;--card:#fff;--card-raised:#fff;--ink:#101828;--muted:#667085;--line:#e4e7ec;
  --brand:#2f2b29;--brand-soft:#eceae8;--on-brand:#fff;--blue:#4d4845;--blue-soft:#f0efee;
  --good:#18794e;--good-soft:#e4f2e9;--warn:#9a5b00;--warn-soft:#f7eddc;
  --bad:#b42318;--bad-soft:#fce8e6;--danger-action:#d92d20;
  --shadow:0 1px 2px #0e1f1b08,0 1px 1px #0e1f1b0a;
  --shadow-md:0 2px 4px #0e1f1b08,0 16px 32px -12px #0e1f1b1a;
  --shadow-lg:0 4px 10px #0e1f1b0d,0 24px 48px -16px #0e1f1b26
}
:root[data-theme="dark"]{
  --bg:#080808;--card:#151515;--card-raised:#1d1c1b;--ink:#feffff;--muted:#aaa6a3;--line:#34302e;
  --brand:#feffff;--brand-soft:#2f2b29;--on-brand:#080808;--blue:#feffff;--blue-soft:#2f2b29;
  --good:#6ce9a6;--good-soft:#123126;--warn:#fdbf6f;--warn-soft:#3a2812;
  --bad:#fda29b;--bad-soft:#3b191c;--danger-action:#f04438;
  --shadow:0 1px 2px #0006,0 1px 1px #0004;
  --shadow-md:0 2px 4px #0006,0 16px 32px -12px #0009;
  --shadow-lg:0 4px 10px #0007,0 24px 48px -16px #000c
}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:
radial-gradient(circle at 8% -10%,color-mix(in srgb,var(--brand) 11%,transparent),transparent 34rem),
radial-gradient(circle at 92% 8%,color-mix(in srgb,var(--blue) 9%,transparent),transparent 30rem),var(--bg);color:var(--ink);
font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;min-height:100vh}
button,input{font:inherit}button{cursor:pointer}.mono{font-family:ui-monospace,"SFMono-Regular",
Consolas,monospace;font-variant-numeric:tabular-nums}.wrap{max-width:1240px;margin:0 auto;padding:0 30px}
header{height:68px;position:sticky;top:0;z-index:15;background:color-mix(in srgb,var(--bg) 78%,transparent);
backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border-bottom:1px solid color-mix(in srgb,var(--line) 78%,transparent);display:flex;align-items:center}
.head{display:flex;align-items:center;gap:12px;width:100%}.logo{display:flex;align-items:center;gap:10px;font-size:17px;font-weight:850;letter-spacing:-.03em}
.brandmark{width:40px;height:40px;object-fit:cover;border-radius:10px;display:block;border:1px solid #ffffff24;box-shadow:0 7px 20px #0004;filter:invert(1)}
@media(prefers-color-scheme:dark){.brandmark{filter:none}}:root[data-theme="light"] .brandmark{filter:invert(1)}:root[data-theme="dark"] .brandmark{filter:none}
.logo strong{color:var(--ink)}.grow{flex:1}.small{font-size:12px;color:var(--muted)}
.state{display:inline-flex;align-items:center;gap:7px;border-radius:99px;padding:6px 11px;
font-size:12px;font-weight:750;background:var(--blue-soft);color:var(--blue)}
.state:before{content:"";width:8px;height:8px;border-radius:50%;background:currentColor}
.state.active{background:var(--good-soft);color:var(--good)}
.repolink{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--line);border-radius:9px;
padding:7px 11px;color:var(--ink);background:var(--card);font-size:12px;font-weight:800;text-decoration:none}
.repolink:hover{border-color:var(--brand);color:var(--brand)}.repolink svg{width:16px;height:16px;fill:currentColor}
.themebtn{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:9px;padding:7px 11px;color:var(--ink);background:var(--card);font-size:12px;font-weight:800}.themebtn:before{content:"";width:14px;height:14px;border-radius:50%;background:linear-gradient(90deg,var(--ink) 50%,var(--card) 50%);border:1px solid var(--ink)}.themebtn:hover{border-color:var(--brand)}
.statusbanner{display:flex;gap:17px;align-items:center;padding:20px 22px;border-radius:20px;margin:0 0 22px;
border:1px solid color-mix(in srgb,var(--good) 30%,var(--line));background:linear-gradient(115deg,var(--good-soft),color-mix(in srgb,var(--card) 94%,var(--good)));box-shadow:var(--shadow-md)}
.statusbanner.bad{border-color:color-mix(in srgb,var(--bad) 35%,var(--line));background:var(--bad-soft)}
.statusicon{width:38px;height:38px;flex:0 0 auto;display:grid;place-items:center;border-radius:50%;
font-size:18px;line-height:1;color:#fff;background:var(--good);box-shadow:0 2px 6px color-mix(in srgb,var(--good) 45%,transparent)}
.statusbanner.bad .statusicon{background:var(--bad);box-shadow:0 2px 6px color-mix(in srgb,var(--bad) 45%,transparent)}
.statusbanner>div:nth-child(2){min-width:0;flex:1}.statuslabel{display:block;color:var(--good);font-size:10px;font-weight:850;letter-spacing:.1em;text-transform:uppercase;margin-bottom:2px}.statusbanner.bad .statuslabel{color:var(--bad)}
.statusbanner b{display:block;font-size:20px;letter-spacing:-.025em}.statusbanner p{margin:3px 0 0;color:var(--muted);max-width:75ch}
.statusbanner .statusaction{margin-left:auto;flex:0 0 auto}
.tabnav{display:flex;gap:5px;margin:2px 0 28px;padding:5px;width:max-content;border-radius:15px;
background:color-mix(in srgb,var(--card) 76%,transparent);border:1px solid var(--line);box-shadow:var(--shadow)}
.tabbtn{border:1px solid transparent;background:transparent;color:var(--muted);border-radius:var(--radius-sm);
padding:9px 18px;font-weight:760;font-size:13px;transition:background .12s ease,color .12s ease,box-shadow .12s ease}
.tabbtn:hover{color:var(--ink)}.tabbtn.active{background:var(--card);border-color:var(--line);color:var(--ink);box-shadow:var(--shadow)}
.tabbtn span{font-size:10px;color:var(--muted);margin-right:6px}.tabbtn.active span{color:var(--brand)}
.tabpanel{display:none}.tabpanel.active{display:block;animation:tabin .15s ease}
@keyframes tabin{from{opacity:0;transform:translateY(2px)}to{opacity:1;transform:none}}
main{padding:26px 0 70px}.hero,.card{background:color-mix(in srgb,var(--card) 96%,transparent);border:1px solid var(--line);
border-radius:20px;box-shadow:var(--shadow)}.hero{padding:24px 26px;margin-bottom:22px;
display:grid;grid-template-columns:minmax(0,1fr) auto;gap:24px;align-items:center;
box-shadow:var(--shadow-md);position:relative;overflow:hidden}
.hero:before{content:"";position:absolute;inset:0 0 auto 0;height:2px;
background:linear-gradient(90deg,var(--brand),color-mix(in srgb,var(--brand) 40%,var(--blue)))}
.eyebrow{display:inline-flex;align-items:center;gap:5px;font-size:10.5px;letter-spacing:.08em;
text-transform:uppercase;color:var(--brand);font-weight:800;background:var(--brand-soft);
border-radius:99px;padding:4px 10px 4px 8px}
.eyebrow:before{content:"";width:5px;height:5px;border-radius:50%;background:currentColor}
h1{font-size:30px;line-height:1.12;letter-spacing:-.04em;margin:9px 0 8px}
.hero p{color:var(--muted);margin:0;max-width:66ch}.actions{display:flex;gap:9px;align-items:center}
.primary,.secondary{border-radius:var(--radius-sm);padding:10px 15px;font-weight:750;white-space:nowrap;
transition:filter .12s ease,background .12s ease,border-color .12s ease,transform .05s ease}
.primary{background:var(--brand);border:1px solid var(--brand);color:var(--on-brand);box-shadow:0 1px 2px #0e1f1b1a}
.primary:hover{filter:brightness(1.07)}.primary:active{transform:translateY(1px)}
.primary.danger{background:var(--danger-action);border-color:var(--danger-action);color:#fff;box-shadow:0 8px 22px color-mix(in srgb,var(--danger-action) 28%,transparent)}
.primary.danger:hover{filter:brightness(1.08)}
.primary:disabled{opacity:.45;cursor:not-allowed;filter:none}.secondary{background:var(--card);
border:1px solid var(--line);color:var(--ink)}.secondary:hover{background:var(--bg);border-color:color-mix(in srgb,var(--brand) 35%,var(--line))}
.grid{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(300px,.8fr);gap:20px}
.card{padding:24px;margin-bottom:22px;transition:box-shadow .15s ease}
.card h2{font-size:19px;margin:0 0 5px;letter-spacing:-.025em;font-weight:770}
.sub{color:var(--muted);font-size:13px;margin:0 0 16px}.metrics{display:grid;
grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}.metric{background:var(--card);
border:1px solid var(--line);border-radius:var(--radius-sm);padding:14px 15px;position:relative;
overflow:hidden;box-shadow:var(--shadow)}
.metric:before{content:"";position:absolute;inset:0 auto auto 0;width:100%;height:2.5px;background:var(--brand-soft)}
.metric b{display:block;font-size:22px;line-height:1.2;letter-spacing:-.01em}
.metric span{font-size:11px;color:var(--muted);font-weight:650}
.search{display:flex;gap:8px}.search input{flex:1;min-width:0;border:1px solid var(--line);
border-radius:9px;background:var(--bg);color:var(--ink);padding:10px 12px}
.results{margin-top:14px}.result{border-top:1px solid var(--line);padding:13px 10px;margin:0 -10px;
border-radius:8px;transition:background .12s ease}.result:hover{background:var(--bg)}
.result:first-child{border-top:0}.result p{margin:0 0 6px;white-space:pre-wrap}.meta{font-size:11px;
color:var(--muted);display:flex;gap:8px;flex-wrap:wrap}.pill{background:var(--brand-soft);
color:var(--brand);border-radius:99px;padding:2px 7px;font-weight:700}.recordlink{border:0;background:none;color:var(--blue);
padding:0;text-decoration:underline;text-underline-offset:3px;font:inherit}.empty{color:var(--muted);padding:16px 2px}
.source{border-top:1px solid var(--line);padding:12px 10px;margin:0 -10px;border-radius:8px;
transition:background .12s ease}.source:hover{background:var(--bg)}.source:first-child{border-top:0}
.sourcehead{display:flex;gap:10px;align-items:baseline}.sourcehead b{overflow-wrap:anywhere}
.plane{margin-left:auto;border-radius:99px;background:var(--blue-soft);color:var(--blue);
font-size:10px;font-weight:800;padding:2px 7px;text-transform:uppercase}.digest{font-size:10px;
color:var(--muted);overflow-wrap:anywhere;margin-top:4px}.check{display:flex;align-items:center;
gap:9px;padding:9px 0;border-top:1px solid var(--line)}.check:first-child{border-top:0}
.check i{width:20px;height:20px;border-radius:50%;display:grid;place-items:center;
background:var(--good-soft);color:var(--good);font-style:normal;font-weight:900}.check.pending i{
background:var(--warn-soft);color:var(--warn)}.check span{font-size:12px;color:var(--muted)}
.notice{display:none;border:1px solid var(--bad);background:var(--bad-soft);color:var(--bad);
border-radius:10px;padding:11px 13px;margin-bottom:16px}.notice.show{display:block}
.progressbox{display:none;background:var(--card);border:1px solid var(--brand);
border-radius:12px;padding:15px 17px;margin-bottom:16px;box-shadow:var(--shadow)}
.progressbox.show{display:block}.progresshead{display:flex;justify-content:space-between;
gap:16px;margin-bottom:8px}.progresshead b{font-size:14px}.progresshead span{font-size:12px;
color:var(--muted)}.progressbar{height:8px;border-radius:99px;background:var(--brand-soft);
overflow:hidden}.progressbar span{display:block;width:38%;height:100%;border-radius:99px;
background:var(--brand);animation:working 1.15s ease-in-out infinite}
@keyframes working{0%{transform:translateX(-110%)}100%{transform:translateX(365%)}}
@media(prefers-reduced-motion:reduce){.progressbar span{animation-duration:2.5s}}
.zeroloading{display:flex;align-items:center;gap:13px;color:var(--muted);font-size:12px;font-weight:700}.zeros{display:inline-flex;gap:5px;color:var(--ink);font:900 18px/1 ui-monospace,"SFMono-Regular",Consolas,monospace;letter-spacing:-.08em}.zeros span{display:inline-grid;place-items:center;width:17px;height:22px;animation:zerowave 1.25s cubic-bezier(.22,.8,.35,1) infinite;transform-origin:center}.zeros span:nth-child(2){animation-delay:.12s}.zeros span:nth-child(3){animation-delay:.24s}.zeros span:nth-child(4){animation-delay:.36s}.zeros.compact{gap:2px;font-size:12px}.zeros.compact span{width:11px;height:15px}
.zeroloading .sub{margin:0}
@keyframes zerowave{0%,55%,100%{opacity:.25;transform:translateY(0) scale(.86)}22%{opacity:1;transform:translateY(-4px) scale(1.08);text-shadow:0 0 18px color-mix(in srgb,var(--ink) 45%,transparent)}}
@media(prefers-reduced-motion:reduce){.zeros span{animation:none;opacity:.7}}
.foot{font-size:11px;color:var(--muted);margin-top:4px}.loading{opacity:.55;pointer-events:none}
button:focus-visible,input:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
.backdrop{display:none;position:fixed;inset:0;background:#07110f99;z-index:20;overflow:hidden}
.backdrop.show{display:block}.drawer{position:fixed;right:0;top:0;bottom:0;height:100vh;height:100dvh;
max-height:100vh;max-height:100dvh;width:min(720px,94vw);background:var(--bg);box-shadow:-20px 0 60px #0004;
padding:0 22px 28px;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;scrollbar-gutter:stable}
.drawerhead{display:flex;gap:14px;align-items:start;position:sticky;top:0;background:var(--bg);
padding:22px 0 16px;z-index:2;border-bottom:1px solid var(--line)}.drawerhead>div{min-width:0;flex:1}
.drawerhead h2{font-size:22px;margin:2px 0}.close{margin-left:auto;flex:0 0 auto;width:38px;height:38px;
border-radius:9px;border:1px solid var(--line);background:var(--card);color:var(--ink);font-size:21px}
.auditorbody{padding-top:18px}.recordcontent{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;
max-height:150px;overflow:auto;padding-right:6px}.evidencegrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
gap:9px}.evidence{border:1px solid var(--line);background:var(--card);border-radius:10px;padding:11px;
min-width:0}.evidence span{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;
letter-spacing:.06em}.evidence b{display:block;margin-top:3px;overflow-wrap:anywhere;word-break:break-word}
.evidence b.mono{word-break:break-all}.chain{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));
gap:6px;align-items:stretch;padding:4px 0}.chainstep{min-width:0;overflow:hidden;border:1px solid var(--line);
border-radius:9px;padding:9px;background:var(--card);font-size:11px}.chainstep b{display:block;font-size:12px}
.chainstep span{display:block;margin-top:2px;overflow-wrap:anywhere;word-break:break-word}
.chainstep.ok{border-color:var(--good);background:var(--good-soft)}.chainstep.missing{color:var(--muted)}
.timeline{border-left:2px solid var(--line);margin-left:7px;padding-left:17px}.event{position:relative;
padding:0 0 17px}.event:before{content:"";position:absolute;left:-23px;top:5px;width:10px;height:10px;
border-radius:50%;background:var(--brand);border:2px solid var(--bg)}.event b{display:block}.event p{margin:2px 0;
color:var(--muted);font-size:12px}.downloads{display:flex;gap:8px;flex-wrap:wrap}.downloads a{display:inline-flex;
text-decoration:none}.delivery{border:1px solid var(--line);border-radius:11px;padding:0;background:var(--card);margin-top:9px;overflow:hidden}
.delivery>summary{cursor:pointer;list-style:none;padding:13px 14px;font-weight:800}.delivery>summary::-webkit-details-marker{display:none}
.delivery>summary:after{content:"Open details";float:right;color:var(--blue);font-size:11px;font-weight:750}
.delivery[open]>summary{border-bottom:1px solid var(--line)}.delivery[open]>summary:after{content:"Hide details"}
.deliverybody{padding:12px 14px}.deliverybody p{margin:0 0 9px}.delivery.used{border-color:var(--good)}
.delivery.returned{border-color:var(--warn)}.delivery.used>summary{background:var(--good-soft)}
.delivery.returned>summary{background:var(--warn-soft)}.backlink{margin:0 0 12px}
.integrity{color:var(--good);font-weight:800}.integrity.bad{color:var(--bad)}
.reviewhead{display:flex;align-items:center;gap:9px}.reviewhead .secondary{margin-left:auto;padding:6px 10px;
font-size:12px}.reviewcount{display:inline-grid;place-items:center;
min-width:24px;height:24px;border-radius:99px;padding:0 7px;background:var(--warn-soft);color:var(--warn);
font-size:11px;font-weight:850}.reviewitem{border-top:1px solid var(--line);padding:15px 10px;
margin:0 -10px;border-radius:8px;transition:background .12s ease}.reviewitem:hover{background:var(--bg)}
.reviewitem:first-child{border-top:0}.reviewcontent{margin:0 0 8px;white-space:pre-wrap;
overflow-wrap:anywhere}.reviewmeta{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:11px}
.reviewcompare{display:grid;grid-template-columns:minmax(220px,.8fr) minmax(0,1.2fr);gap:12px;margin:10px 0 12px}
.reviewpane{min-width:0;border:1px solid var(--line);border-radius:11px;background:var(--bg);padding:12px}
.reviewpane h3{margin:0 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}
.reviewimage{display:block;width:100%;max-height:320px;object-fit:contain;border-radius:8px;background:#0a0f0e}
.reviewboundary{margin:9px 0 0;color:var(--muted);font-size:12px}.reviewboundary strong{color:var(--ink)}
.previewstatus{margin:8px 0 0;font-size:12px;color:var(--muted)}.previewstatus.bad{color:var(--bad)}
.reviewactions{display:flex;gap:8px;flex-wrap:wrap}.reviewactions button{border-radius:9px;padding:9px 13px;
font-weight:750}.approve{background:var(--good);border-color:var(--good)}
.reviewactions button:disabled{opacity:.48;cursor:not-allowed;filter:none}
.reject{background:var(--card);border:1px solid var(--bad);color:var(--bad)}.reject:hover{background:var(--bad-soft)}
.auditcard{margin-top:18px;padding:0;overflow:hidden}.audithead{padding:20px 22px 15px;border-bottom:1px solid var(--line);
display:flex;gap:18px;align-items:start}.audithead>div:first-child{flex:1}.audittoolbar{display:flex;gap:7px;flex-wrap:wrap;
justify-content:flex-end}.auditfilters{padding:16px 22px;display:grid;grid-template-columns:2fr repeat(3,minmax(145px,1fr));
gap:10px;border-bottom:1px solid var(--line);background:color-mix(in srgb,var(--card) 88%,var(--bg))}
.field{min-width:0}.field label{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.07em;
font-weight:800;color:var(--muted);margin:0 0 4px}.field input,.field select{width:100%;border:1px solid var(--line);
border-radius:8px;background:var(--card);color:var(--ink);padding:9px 10px;min-height:39px}.filteractions{display:flex;
gap:8px;align-items:end}.quickrange{padding:10px 22px;border-bottom:1px solid var(--line);display:flex;gap:7px;
align-items:center;flex-wrap:wrap}.quickrange button{border:1px solid var(--line);background:var(--card);color:var(--ink);
border-radius:99px;padding:5px 10px;font-size:11px}.quickrange button:hover{border-color:var(--brand);color:var(--brand)}
.histogram{height:100px;padding:14px 22px 8px;display:flex;gap:3px;align-items:end;border-bottom:1px solid var(--line)}
.histbar{flex:1;min-width:3px;max-width:28px;background:var(--brand);opacity:.72;border-radius:3px 3px 0 0;
border:0;padding:0}.histbar:hover{opacity:1}.auditmeta{padding:10px 22px;display:flex;gap:12px;align-items:center;
border-bottom:1px solid var(--line);color:var(--muted);font-size:12px}.auditmeta .grow{flex:1}.auditviewport{overflow:auto;
max-height:600px}.audittable{width:100%;border-collapse:separate;border-spacing:0;min-width:1040px}.audittable th{
position:sticky;top:0;z-index:1;background:var(--card);text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);
font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}.audittable td{padding:10px 12px;
border-bottom:1px solid var(--line);vertical-align:top;font-size:12px}.audittable tr:hover td{background:var(--brand-soft)}
.eventbutton{border:0;background:none;color:var(--ink);padding:0;font-weight:750;text-align:left}.pivot{border:0;
background:none;color:var(--blue);padding:0;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.auditpager{padding:12px 22px;display:flex;align-items:center;gap:8px}.eventpayload{white-space:pre-wrap;word-break:break-word;
background:var(--bg);border:1px solid var(--line);border-radius:9px;padding:12px;font-size:11px;max-height:320px;overflow:auto}
.savedview{max-width:190px}.integritychip{display:inline-flex;gap:6px;align-items:center;color:var(--good);font-weight:800}
.integritychip.bad{color:var(--bad)}
.blackboxhead{display:flex;gap:18px;align-items:start}.blackboxhead>div:first-child{flex:1}
.blackboxsummary{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.flights{margin-top:13px}
.flightfilters{display:grid;grid-template-columns:minmax(220px,2fr) minmax(130px,.7fr) repeat(2,minmax(145px,.8fr)) auto;gap:9px;align-items:end;margin-top:15px;padding:13px;border:1px solid var(--line);border-radius:11px;background:var(--bg)}
.flightpresets{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px}.flightpresets button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:99px;padding:5px 10px;font-size:11px}.flightpresets button.active{border-color:var(--brand);background:var(--brand-soft);color:var(--brand)}
.flight{display:grid;grid-template-columns:minmax(0,1.4fr) repeat(4,minmax(85px,.55fr)) auto;
gap:12px;align-items:center;border-top:1px solid var(--line);padding:12px 10px;margin:0 -10px;
border-radius:8px;transition:background .12s ease}.flight:hover{background:var(--bg)}.flight:first-child{border-top:0}
.flight b,.flight span{min-width:0;overflow:hidden;text-overflow:ellipsis}.flightstat small{display:block;color:var(--muted)}
.flightverdict{font-weight:800;color:var(--good)}.flightverdict.pending{color:var(--warn)}
.attentionhero{display:flex;gap:18px;align-items:center;margin:14px 0 16px;padding:17px 18px;
border-radius:12px;background:var(--good-soft);border:1px solid color-mix(in srgb,var(--good) 35%,var(--line))}
.attentionhero.bad{background:var(--bad-soft);border-color:color-mix(in srgb,var(--bad) 40%,var(--line))}
.attentionhero b{font-size:22px;line-height:1.2}.attentionhero p{margin:2px 0 0;color:var(--muted)}
.attentionchecks{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:15px}
.attentioncheck{display:flex;text-align:left;gap:12px;align-items:start;border:1px solid var(--line);border-radius:11px;
background:var(--card);color:var(--ink);padding:13px}.attentioncheck.ok{border-color:color-mix(in srgb,var(--good) 35%,var(--line));background:var(--good-soft)}
.attentioncheck.bad{border-color:color-mix(in srgb,var(--bad) 40%,var(--line));background:var(--bad-soft)}
.attentioncheck .checknumber{display:grid;place-items:center;width:27px;height:27px;flex:0 0 auto;border-radius:50%;
background:var(--good);color:#fff;font-weight:850}.attentioncheck.bad .checknumber{background:var(--bad)}
.attentioncheck b{display:block}.attentioncheck span{display:block;color:var(--muted);font-size:11px}
.attentionlist{display:grid;gap:9px}.attentionitem{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:12px;
align-items:start;border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:10px;padding:13px;background:var(--card)}
.attentionitem.critical,.attentionitem.high{border-left-color:var(--bad)}.severity{border-radius:99px;padding:3px 8px;
font-size:10px;font-weight:850;text-transform:uppercase;background:var(--warn-soft);color:var(--warn)}
.critical .severity,.high .severity{background:var(--bad-soft);color:var(--bad)}.attentioncopy b{display:block;font-size:14px}
.attentioncopy p{margin:2px 0;color:var(--muted);font-size:12px}.attentionaction{color:var(--ink)!important}.attentionmeta{margin-top:5px}
.flightarchive{margin-top:16px;border-top:1px solid var(--line);padding-top:13px}.flightarchive summary{cursor:pointer;font-weight:800;color:var(--muted)}
.historicalnote{border:1px solid var(--line);background:var(--blue-soft);border-radius:11px;padding:14px 15px;margin-bottom:14px}
.historicalnote b{display:block;font-size:16px}.historicalnote p{margin:3px 0 0;color:var(--muted)}
.technical{margin-top:14px;border-top:1px solid var(--line);padding-top:13px}.technical>summary{cursor:pointer;font-weight:800;color:var(--muted);padding:5px 0 12px}
.storyflow{display:grid;gap:10px}.storystep{display:grid;grid-template-columns:34px minmax(0,1fr);gap:12px;
border:1px solid var(--line);border-radius:11px;padding:13px;background:var(--card)}
.storynumber{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:var(--brand);color:var(--on-brand);font-weight:850}
.storystep h3{margin:0 0 5px;font-size:14px}.storytext{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;color:var(--ink)}
.memoryline{display:block;width:100%;text-align:left;border:1px solid var(--line);background:var(--bg);color:var(--ink);
border-radius:8px;padding:9px 10px;margin-top:6px}.memoryline:hover{border-color:var(--brand);background:var(--brand-soft)}
.memoryline small{display:block;color:var(--blue);margin-top:3px}.evidencechips{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}
.evidencechip{border:1px solid var(--line);background:var(--bg);color:var(--blue);border-radius:99px;padding:4px 8px;
font:10px ui-monospace,"SFMono-Regular",Consolas,monospace;max-width:100%;overflow:hidden;text-overflow:ellipsis}
.event.focused{background:var(--blue-soft);border-radius:8px;padding:9px 9px 17px}.technical>summary{font-size:15px;color:var(--blue)}
.productfoot{margin-top:22px;padding:20px 22px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:18px 22px;align-items:center;background:var(--card);
border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}.productfoot>div:first-child{min-width:0}
.productfoot b{display:block;font-size:16px;letter-spacing:-.015em}.productfoot p{margin:3px 0 0;color:var(--muted)}
.productlinks{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end}.productlinks a{color:var(--blue);
text-decoration:none;font-weight:750;white-space:nowrap}.productlinks a:hover{text-decoration:underline}.productlinks span{color:var(--line)}
.versionbar{grid-column:1/-1;display:flex;align-items:center;gap:9px;flex-wrap:wrap;padding-top:16px;border-top:1px solid var(--line)}.versionlabel{margin-right:2px;color:var(--muted);font-size:10px;font-weight:850;letter-spacing:.09em;text-transform:uppercase}.versionchip{display:inline-flex;align-items:center;gap:6px;min-height:30px;padding:5px 9px;border:1px solid var(--line);border-radius:9px;background:var(--bg);font-size:11px;color:var(--muted)}.versionchip b{color:var(--ink);font:800 11px/1 ui-monospace,"SFMono-Regular",Consolas,monospace}.xlink{margin-left:auto;display:inline-flex;align-items:center;gap:7px;border-radius:9px;padding:6px 10px;background:var(--ink);color:var(--bg);text-decoration:none;font-size:12px;font-weight:850}.xlink:hover{opacity:.86}.xmark{font-size:15px;line-height:1}
.pageheading{display:flex;align-items:end;justify-content:space-between;gap:24px;margin:0 2px 24px}.pageheading h1{font-size:34px;margin:10px 0 7px}.pageheading p{margin:0;color:var(--muted);font-size:15px;max-width:68ch}
.pagecontext{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px;font-weight:700;white-space:nowrap;padding:9px 12px;border:1px solid var(--line);border-radius:99px;background:var(--card)}
.livepulse{width:8px;height:8px;border-radius:50%;background:var(--good);box-shadow:0 0 0 4px color-mix(in srgb,var(--good) 18%,transparent)}
.sectionnumber{display:inline-grid;place-items:center;min-width:28px;height:22px;padding:0 7px;border-radius:7px;background:var(--blue-soft);color:var(--blue);font:800 10px/1 ui-monospace,"SFMono-Regular",monospace;margin-bottom:9px}
.sectiondivider{display:flex;align-items:baseline;gap:13px;margin:32px 2px 14px;padding-top:4px}.sectiondivider span{font-size:19px;font-weight:800;letter-spacing:-.025em}.sectiondivider p{margin:0;color:var(--muted);font-size:13px}
.providerhero{background:linear-gradient(125deg,color-mix(in srgb,var(--card) 94%,var(--brand)),var(--card));box-shadow:var(--shadow)}.providerhero h1{font-size:23px;margin-top:7px}
#blackboxCard{padding:28px;border-color:color-mix(in srgb,var(--brand) 24%,var(--line));box-shadow:var(--shadow-lg);position:relative;overflow:hidden}
#blackboxCard:after{content:"";position:absolute;width:240px;height:240px;border-radius:50%;right:-130px;top:-150px;background:color-mix(in srgb,var(--brand) 8%,transparent);pointer-events:none}
#reviewCard{min-height:220px}.grid aside .card{background:color-mix(in srgb,var(--card) 92%,var(--bg))}
.sectionnav{position:sticky;top:80px;z-index:10;display:flex;gap:7px;flex-wrap:wrap;margin:0 0 22px;padding:7px;border:1px solid var(--line);border-radius:16px;background:color-mix(in srgb,var(--bg) 82%,transparent);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);box-shadow:var(--shadow)}
.sectionnav a{display:inline-flex;align-items:center;gap:7px;padding:8px 12px;border-radius:10px;color:var(--muted);font-size:12px;font-weight:760;text-decoration:none}.sectionnav a:hover{background:var(--card);color:var(--ink)}.sectionnav span{font:800 9px/1 ui-monospace,"SFMono-Regular",monospace;color:var(--brand)}
#blackboxArchiveCard,#memorySearchCard,#mirrorCard,#auditExplorer{scroll-margin-top:145px}
#blackboxArchiveCard{box-shadow:var(--shadow-md)}.auditcard{box-shadow:var(--shadow-md)}
.attentionhero{position:relative;overflow:hidden}.attentionhero:after{content:"CURRENT";position:absolute;right:16px;top:13px;font-size:9px;font-weight:900;letter-spacing:.12em;color:var(--good)}.attentionhero.bad:after{color:var(--bad)}
.attentioncheck{min-height:78px}.attentioncheck b{font-size:13px}.attentioncheck span{margin-top:3px}
.flight{padding-top:15px;padding-bottom:15px}.flight:hover{background:color-mix(in srgb,var(--brand-soft) 50%,var(--card))}
@media(max-width:780px){.wrap{padding:0 14px}.hero{grid-template-columns:1fr;padding:20px}.reviewcompare{grid-template-columns:1fr}
.actions{width:100%}.actions button{flex:1}.grid{grid-template-columns:1fr}.metrics{
grid-template-columns:repeat(2,1fr)}header .small{display:none}.evidencegrid{grid-template-columns:1fr}
.chain{grid-template-columns:repeat(2,minmax(0,1fr))}.drawer{width:100vw;padding-left:16px;padding-right:16px}
.auditfilters{grid-template-columns:1fr}.audithead{display:block}.audittoolbar{justify-content:flex-start;margin-top:12px}
.productfoot{display:block}.productlinks{justify-content:flex-start;margin-top:12px}.versionbar{margin-top:16px}.xlink{margin-left:0}.repolink span{display:none}.pageheading{display:block}.pageheading h1{font-size:28px}.pagecontext{display:none}.statusbanner{align-items:flex-start;flex-wrap:wrap}.statusbanner .statusaction{width:100%;margin-left:55px}.sectiondivider{display:block}.sectiondivider p{margin-top:3px}.sectionnav{top:72px;overflow-x:auto;flex-wrap:nowrap}.sectionnav a{white-space:nowrap}}
@media(max-width:780px){.flight{grid-template-columns:1fr 1fr}.flight .primary{grid-column:1/-1}.blackboxhead{display:block}.flightfilters{grid-template-columns:1fr}}
@media(max-width:780px){.attentionchecks{grid-template-columns:1fr}.attentionitem{grid-template-columns:1fr}.attentionhero{align-items:start}}
</style>
</head>
<body>
<header><div class="wrap head">
  <div class="logo"><img class="brandmark" src="/assets/atmem.jpg" alt="AtMem logo"><strong>AtMem</strong></div>
  <div class="small">OpenClaw memory</div>
  <div class="grow"></div>
  <button class="themebtn" id="themeToggle" type="button">Light mode</button>
  <a class="repolink" href="https://github.com/aetna000/atmem" target="_blank" rel="noopener noreferrer" aria-label="View AtMem on GitHub">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 .7a11.5 11.5 0 0 0-3.64 22.4c.58.1.79-.25.79-.56v-2.23c-3.22.7-3.9-1.37-3.9-1.37-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.7.08-.7 1.16.08 1.78 1.2 1.78 1.2 1.03 1.77 2.71 1.26 3.37.96.1-.75.4-1.26.73-1.55-2.57-.29-5.28-1.29-5.28-5.68 0-1.26.45-2.28 1.19-3.08-.12-.29-.52-1.46.11-3.04 0 0 .97-.31 3.16 1.18a10.9 10.9 0 0 1 5.76 0c2.19-1.49 3.16-1.18 3.16-1.18.63 1.58.23 2.75.11 3.04.74.8 1.19 1.82 1.19 3.08 0 4.4-2.71 5.38-5.29 5.67.42.36.79 1.06.79 2.14v3.18c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .7Z"/></svg>
    <span>Star on GitHub</span>
  </a>
  <div class="state" id="stateChip"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span></div>
</div></header>
<main class="wrap">
  <div class="notice" id="error" role="alert"></div>
  <div class="progressbox" id="progress" role="status" aria-live="polite">
    <div class="progresshead">
      <b id="progressTitle">Working…</b>
      <span class="mono" id="progressTime">0s</span>
    </div>
    <div class="zeroloading"><span class="zeros" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span><p class="sub" id="progressDetail">Please keep this page open.</p></div>
    <div class="progressbar" aria-hidden="true"><span></span></div>
  </div>

  <div class="tabnav" role="tablist">
    <button class="tabbtn active" id="tabBtnOverview" type="button" role="tab" aria-selected="true"><span>01</span> Monitor</button>
    <button class="tabbtn" id="tabBtnTechnical" type="button" role="tab" aria-selected="false"><span>02</span> Investigate</button>
  </div>

  <div class="tabpanel active" id="tabOverview">
  <div class="pageheading"><div><div class="eyebrow">Live oversight</div><h1>Agent memory control</h1><p>See what requires action now. Historical evidence stays out of the way until you investigate it.</p></div><div class="pagecontext"><span class="livepulse"></span> Live local evidence</div></div>

  <section class="statusbanner" id="statusBanner">
    <div class="statusicon" id="statusIcon">…</div>
    <div><span class="statuslabel">Current condition</span><b id="statusHeadline"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span></b><p id="statusDetail">Loading verified evidence…</p></div>
    <button class="primary statusaction" id="statusAction" type="button" style="display:none">Open issue</button>
  </section>

  <section class="card" id="blackboxCard">
    <div class="blackboxhead">
      <div><div class="sectionnumber">01</div><div class="eyebrow">Latest agent run</div><h2>What happened most recently?</h2>
      <p class="sub">Only the newest activity controls this panel. Older failures remain searchable under Investigate.</p></div>
      <div class="actions"><button class="primary" id="bridgeRefresh" type="button" style="display:none">Upgrade bridge &amp; run test</button>
      <button class="secondary" id="blackboxRefresh" type="button">Refresh checks</button></div>
    </div>
    <div class="attentionhero" id="attentionHero"><div><b id="attentionHeadline"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span></b>
      <p id="attentionSummary">AtMem is deciding whether you need to act now.</p></div></div>
    <div class="attentionchecks" id="attentionChecks"></div>
    <div class="attentionlist" id="attentionList"><div class="empty zeroloading"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span><span>Loading attention points…</span></div></div>
  </section>

  <div class="sectiondivider"><span>Memory governance</span><p>Approve new memory and control which provider OpenClaw uses.</p></div>

  <section class="hero providerhero" id="hero">
    <div>
      <div class="sectionnumber">02</div><div class="eyebrow" id="eyebrow">Memory provider</div>
      <h1 id="title"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span></h1>
      <p id="summary">AtMem is verifying the mirrored copy and the restore snapshot.</p>
    </div>
    <div class="actions">
      <button class="secondary" id="refreshBtn">Refresh mirror</button>
      <button class="primary" id="switchBtn" disabled>Activate AtMem</button>
    </div>
  </section>

  <div class="grid">
    <div>
      <section class="card" id="reviewCard">
        <div class="sectionnumber">03</div><div class="reviewhead"><h2>Memory decisions</h2><span class="reviewcount" id="reviewCount">0</span><button class="secondary" id="reviewRefresh" type="button">Refresh</button></div>
        <p class="sub">External observations stay out of agent recall until you approve them. Rejection permanently purges the candidate content.</p>
        <div id="reviews"><div class="empty zeroloading"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span><span>Checking for quarantined memories…</span></div></div>
      </section>
    </div>

    <aside>
      <section class="card">
        <div class="sectionnumber">04</div>
        <h2 id="switchTitle">Ready to switch?</h2>
        <p class="sub" id="switchCopy">AtMem checks every safety condition before changing OpenClaw.</p>
        <div id="checks"></div>
        <button class="secondary" id="verifyBtn" type="button">Verify now</button>
        <button class="secondary" id="drillBtn" type="button">Test file restoration</button>
        <div class="small" id="verifyStatus" style="margin-top:12px;line-height:1.7"></div>
        <div class="small" id="drillStatus" style="margin-top:12px;line-height:1.7"></div>
      </section>
      <section class="card">
        <h2>What changes</h2>
        <div class="check"><i>✓</i><div>OpenClaw keeps using <span class="mono">memory_search</span> and <span class="mono">memory_get</span>.</div></div>
        <div class="check"><i>✓</i><div>AtMem becomes the memory store and records searches and reads.</div></div>
        <div class="check"><i>✓</i><div>The original OpenClaw memory is frozen and can be restored.</div></div>
        <div class="check"><i>✓</i><div>Identity, tools, skills and transcripts stay with OpenClaw.</div></div>
      </section>
      <p class="foot mono" id="identity"></p>
    </aside>
  </div>
  </div>

  <div class="tabpanel" id="tabTechnical">
  <div class="pageheading"><div><div class="eyebrow">For investigation</div><h1>Evidence workspace</h1><p>Start with flights, then move into exact memory events only when the question requires it.</p></div></div>
  <nav class="sectionnav" aria-label="Investigation sections"><a href="#blackboxArchiveCard"><span>01</span> Flights</a><a href="#memorySearchCard"><span>02</span> Memory search</a><a href="#mirrorCard"><span>03</span> Mirrored sources</a><a href="#auditExplorer"><span>04</span> Event evidence</a></nav>
  <div class="metrics">
    <div class="metric"><b class="mono" id="sourceCount">—</b><span>mirrored files</span></div>
    <div class="metric"><b class="mono" id="recordCount">—</b><span>searchable memories</span></div>
    <div class="metric"><b class="mono" id="sourceBytes">—</b><span>source bytes preserved</span></div>
    <div class="metric"><b id="verified">—</b><span>mirror verification</span></div>
  </div>

  <section class="card" id="blackboxArchiveCard">
    <div class="blackboxhead">
      <div><div class="sectionnumber">01</div><div class="eyebrow">Agent Black Box</div><h2>All recorded agent flights</h2>
      <p class="sub">Technical history. AtMem stores digests and bounded metadata, not raw prompts, responses, tool parameters or results.</p>
      <p class="sub" id="blackboxCount">Loading recent agent runs…</p></div>
      <div class="blackboxsummary"><span id="blackboxIntegrity" class="integritychip"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span></span></div>
    </div>
    <div class="flightpresets" aria-label="Flight history time range">
      <button type="button" data-flight-range="today">Today</button><button type="button" data-flight-range="yesterday">Yesterday</button><button type="button" data-flight-range="7d" class="active">Last 7 days</button><button type="button" data-flight-range="all">All recorded</button>
    </div>
    <div class="flightfilters">
      <div class="field"><label for="flightQuery">Search flights</label><input id="flightQuery" placeholder="Request, reply, tool, website, model or ID…"></div>
      <div class="field"><label for="flightStatus">Result</label><select id="flightStatus"><option value="">All results</option><option value="healthy">Healthy</option><option value="attention">Needs attention</option><option value="failed">Failed or incomplete</option></select></div>
      <div class="field"><label for="flightSince">From date</label><input id="flightSince" type="date"></div>
      <div class="field"><label for="flightUntil">Through date</label><input id="flightUntil" type="date"></div>
      <button class="primary" id="flightSearch" type="button">Find flights</button>
    </div>
    <div class="flights" id="blackboxFlights"><div class="empty zeroloading"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span><span>Loading recent agent runs…</span></div></div>
  </section>

  <section class="card" id="memorySearchCard">
    <div class="sectionnumber">02</div><h2>Search memory</h2>
    <p class="sub">Search the AtMem copy using ordinary words. This works before and after switching.</p>
    <div class="search">
      <input id="query" placeholder="For example: TypeScript preference" autocomplete="off">
      <button class="primary" id="searchBtn">Search</button>
    </div>
    <div class="results" id="results"><div class="empty">Enter a question to inspect the mirrored memory.</div></div>
  </section>

  <section class="card" id="mirrorCard">
    <div class="sectionnumber">03</div><h2>Exactly what is mirrored</h2>
    <p class="sub" id="sourceSummary">Loading the verified source manifest…</p>
    <div id="sources"><div class="empty zeroloading"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span><span>Loading sources…</span></div></div>
  </section>

  <section class="card auditcard" id="auditExplorer">
    <div class="audithead">
      <div><div class="sectionnumber">04</div><div class="eyebrow">Global evidence investigation</div><h2>Audit Explorer</h2>
      <p class="sub">Search the complete memory audit chain, narrow the evidence, then drill into records, sessions and exact events.</p></div>
      <div class="audittoolbar">
        <select class="secondary savedview" id="auditSaved"><option value="">Saved views…</option></select>
        <button class="secondary" id="auditSave" type="button">Save view</button>
        <button class="secondary" id="auditReset" type="button">Reset</button>
      </div>
    </div>
    <div class="quickrange"><span class="small">Time range</span>
      <button type="button" data-range="15">15 minutes</button><button type="button" data-range="60">1 hour</button>
      <button type="button" data-range="1440">24 hours</button><button type="button" data-range="10080">7 days</button>
      <button type="button" data-range="0">All time</button>
      <span class="small" style="margin-left:10px">Evidence stage</span>
      <button type="button" data-event-pattern="memory.record*">Admission</button>
      <button type="button" data-event-pattern="memory.recall">Recall</button>
      <button type="button" data-event-pattern="memory.context_injected">Injection</button>
      <button type="button" data-event-pattern="agent.response_after_memory">Response</button>
      <button type="button" data-event-pattern="memory.forget">Deletion</button>
    </div>
    <div class="auditfilters">
      <div class="field"><label for="auditQuery">Search event IDs, payloads and evidence</label><input id="auditQuery" placeholder="memory, model, digest, ID…"></div>
      <div class="field"><label for="auditType">Event type</label><select id="auditType"><option value="">All event types</option></select></div>
      <div class="field"><label for="auditActor">Actor</label><select id="auditActor"><option value="">All actors</option></select></div>
      <div class="field"><label for="auditSession">Session ID</label><input id="auditSession" placeholder="agent:main:…"></div>
      <div class="field"><label for="auditRecord">Record ID</label><input id="auditRecord" placeholder="rec_…"></div>
      <div class="field"><label for="auditSince">From</label><input id="auditSince" type="datetime-local"></div>
      <div class="field"><label for="auditUntil">To</label><input id="auditUntil" type="datetime-local"></div>
      <div class="filteractions"><button class="primary" id="auditRun" type="button">Run search</button></div>
    </div>
    <div class="histogram" id="auditHistogram" aria-label="Audit events over time"></div>
    <div class="auditmeta"><span id="auditIntegrity" class="integritychip"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span></span>
      <span id="auditCount">—</span><span class="mono" id="auditDigest"></span><span class="grow"></span>
      <select id="auditDirection" class="secondary"><option value="desc">Newest first</option><option value="asc">Oldest first</option></select>
      <select id="auditLimit" class="secondary"><option>50</option><option selected>100</option><option>250</option><option>500</option></select>
    </div>
    <div class="auditviewport"><table class="audittable"><thead><tr><th>Time</th><th>Event</th><th>Actor</th><th>Record</th><th>Session / turn</th><th>Evidence ID</th><th>Integrity</th></tr></thead>
      <tbody id="auditRows"><tr><td colspan="7" class="empty"><div class="zeroloading"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span><span>Loading audit evidence…</span></div></td></tr></tbody></table></div>
    <div class="auditpager"><button class="secondary" id="auditBack" type="button" disabled>Previous</button>
      <button class="secondary" id="auditNext" type="button" disabled>Next</button><span class="small" id="auditPage">Page 1</span>
      <span class="grow"></span><a class="secondary auditexport" data-format="csv">CSV</a><a class="secondary auditexport" data-format="json">JSON</a>
      <a class="secondary auditexport" data-format="ndjson">NDJSON</a><a class="secondary auditexport" data-format="text">Text</a></div>
  </section>
  </div>

  <footer class="productfoot">
    <div>
      <b>AtMem — governed memory for AI agents</b>
      <p>Search what an agent remembers, approve what becomes trusted, and follow the evidence behind every recall.</p>
    </div>
    <nav class="productlinks" aria-label="AtMem resources">
      <a href="https://github.com/aetna000/atmem" target="_blank" rel="noopener noreferrer">GitHub repository</a><span>·</span>
      <a href="https://github.com/aetna000/atmem/blob/main/docs/openclaw-setup.md" target="_blank" rel="noopener noreferrer">OpenClaw guide</a><span>·</span>
      <a href="https://github.com/aetna000/atmem/blob/main/docs/audit-search.md" target="_blank" rel="noopener noreferrer">Audit guide</a><span>·</span>
      <a href="https://github.com/aetna000/atmem/issues" target="_blank" rel="noopener noreferrer">Feedback</a>
    </nav>
    <div class="versionbar" aria-label="Installed product versions">
      <span class="versionlabel">Installed versions</span>
      <span class="versionchip">OpenClaw <b id="versionOpenClaw"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span></b></span>
      <span class="versionchip">AtMem pip <b id="versionPip"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span></b></span>
      <span class="versionchip">AtMem npm <b id="versionNpm"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span></b></span>
      <a class="xlink" href="https://x.com/AtMemX" target="_blank" rel="noopener noreferrer" aria-label="Follow AtMem on X"><span class="xmark">𝕏</span> @AtMemX</a>
    </div>
  </footer>
</main>
<div class="backdrop" id="auditorBackdrop" aria-hidden="true">
  <aside class="drawer" role="dialog" aria-modal="true" aria-labelledby="auditorTitle">
    <div class="drawerhead">
      <div><div class="eyebrow" id="auditorEyebrow">Evidence investigation</div><h2 id="auditorTitle"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span></h2>
      <div class="mono small" id="auditorId"></div></div>
      <button class="close" id="auditorClose" aria-label="Close record history">×</button>
    </div>
    <div class="auditorbody" id="auditorBody"><div class="empty zeroloading"><span class="zeros compact" aria-hidden="true"><span>0</span><span>0</span><span>0</span><span>0</span></span><span>Loading the verified audit chain…</span></div></div>
  </aside>
</div>
<script>
(function(){
"use strict";
var state=null,reviewQueue={records:[]},productInfo={},blackboxIndex={runs:[]},blackboxArchiveRows=[],blackboxStories={},flightRange="7d",bridgeRefreshStatus={available:false},attentionFilter="all",csrf="",progressTimer=null,progressStarted=0;
var auditCursors=[null],auditPageIndex=0,auditLast=null,auditFacetsLoaded=false;
var $=function(id){return document.getElementById(id)};
function text(id,value){$(id).textContent=value==null?"—":String(value)}
function number(value){return Number(value||0).toLocaleString()}
function showError(error){text("error",error&&error.message?error.message:error);$("error").classList.add("show")}
function clearError(){$("error").classList.remove("show")}
function showProgress(title,detail){
 text("progressTitle",title);text("progressDetail",detail);progressStarted=Date.now();
 text("progressTime","0s");$("progress").classList.add("show");$("hero").classList.add("loading");
 $("switchBtn").disabled=true;$("refreshBtn").disabled=true;
 if(progressTimer)clearInterval(progressTimer);
 progressTimer=setInterval(function(){text("progressTime",Math.floor((Date.now()-progressStarted)/1000)+"s")},1000)
}
function hideProgress(){
 if(progressTimer)clearInterval(progressTimer);progressTimer=null;$("progress").classList.remove("show");
 $("hero").classList.remove("loading");$("refreshBtn").disabled=false;
 var readiness=state&&state.readiness?state.readiness:{};
 $("switchBtn").disabled=active()?false:!readiness.ready_for_active
}
async function working(title,detail,operation){
 clearError();showProgress(title,detail);
 try{return await operation()}finally{hideProgress()}
}
async function get(path){var r=await fetch(path,{headers:{"Accept":"application/json"}});var v=await r.json();if(!r.ok)throw new Error(v.error||"Request failed");return v}
async function post(path,body){var r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":csrf},body:JSON.stringify(body||{})});var v=await r.json();if(!r.ok)throw new Error(v.error||"Request failed");return v}
function element(name,className,value){var node=document.createElement(name);if(className)node.className=className;if(value!=null)node.textContent=value;return node}
function zeroSequence(compact){var zeros=element("span","zeros"+(compact?" compact":""));zeros.setAttribute("aria-hidden","true");for(var i=0;i<4;i++)zeros.appendChild(element("span","","0"));return zeros}
function loadingNode(label,className){var node=element("div",(className?className+" ":"")+"zeroloading");node.setAttribute("role","status");node.append(zeroSequence(true),element("span","",label));return node}
function tableLoading(label){var row=element("tr"),cell=element("td","empty");cell.colSpan=7;cell.appendChild(loadingNode(label));row.appendChild(cell);return row}
function preferredTheme(){try{var saved=localStorage.getItem("atmem-theme");if(saved==="light"||saved==="dark")return saved}catch(_){}return window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}
function applyTheme(theme,persist){document.documentElement.dataset.theme=theme;var button=$("themeToggle"),next=theme==="dark"?"Light":"Dark";text("themeToggle",next+" mode");button.setAttribute("aria-label","Switch to "+next.toLowerCase()+" mode");button.setAttribute("aria-pressed",theme==="light"?"true":"false");if(persist){try{localStorage.setItem("atmem-theme",theme)}catch(_){}}}
function renderProductVersions(){var verification=(state&&state.verification)||{},npmVersion=bridgeRefreshStatus.runtime_version||bridgeRefreshStatus.installed_version||productInfo.atmem_npm_version;text("versionOpenClaw",verification.host_version||"not detected");text("versionPip",productInfo.atmem_pip_version||"not detected");text("versionNpm",npmVersion||"not detected")}
function active(){return !!(state&&state.takeover&&state.takeover.active)}
function recovery(){return !!(state&&state.takeover&&state.takeover.requires_restore)}
function shortDigest(value){return value?String(value).slice(0,16)+"…":"not recorded"}
function displayTime(value){if(!value)return "not recorded";var date=new Date(value);return Number.isNaN(date.getTime())?String(value):date.toLocaleString([], {dateStyle:"medium",timeStyle:"short"})}
function evidence(label,value,mono){var box=element("div","evidence"),name=element("span","",label),body=element("b",mono?"mono":"",value||"not recorded");box.append(name,body);return box}
function chainStep(label,ok,detail){var box=element("div","chainstep "+(ok?"ok":"missing"));box.append(element("b","",label),element("span","",detail));return box}
function blackboxEventDetail(event){var p=event.payload||{},parts=[];if(p.tool_name)parts.push(p.tool_name);if(p.model)parts.push([p.provider,p.model].filter(Boolean).join(" / "));if(p.outcome)parts.push(p.outcome);if(event.tool_call_id)parts.push(event.tool_call_id);return parts.join(" · ")||"digest-bound host event"}
function storyStep(position,title,content){var box=element("div","storystep"),numberBox=element("span","storynumber",position),copy=element("div");copy.append(element("h3","",title));if(typeof content==="string")copy.append(element("p","storytext",content));else if(content)copy.append(content);box.append(numberBox,copy);return box}
function flightEventTitle(type){return ({"turn.input":"Request received","context.disposition":"Memory added to the request","model.input":"Request sent to the model","model.output":"Model replied","turn.ended":"Flight finished","tool.requested":"Tool requested","tool.completed":"Tool finished"})[type]||String(type||"Evidence event").replaceAll("."," ")}
function focusFlightEvidence(value){var technical=document.querySelector("#auditorBody .technical");if(technical)technical.open=true;var events=Array.from(document.querySelectorAll("#auditorBody .event[data-evidence]")),match=events.find(function(item){return item.dataset.evidence.indexOf(String(value))>=0});events.forEach(function(item){item.classList.remove("focused")});if(match){match.classList.add("focused");if(match.tagName==="DETAILS")match.open=true;match.scrollIntoView({behavior:"smooth",block:"center"})}}
function evidenceChip(label,value){var button=element("button","evidencechip",label+": "+value);button.type="button";button.title="Open the event containing "+value;button.onclick=function(){focusFlightEvidence(value)};return button}
function currentRun(){return (blackboxIndex.runs||[])[0]||null}
function attentionGroups(filter){var groups={},rank={critical:0,high:1,medium:2},row=currentRun();if(!row)return[];(row.attention_points||[]).forEach(function(point){if(filter!=="all"&&point.check!==filter)return;if(!groups[point.code])groups[point.code]={point:point,rows:[row]}});return Object.values(groups).sort(function(a,b){return (rank[a.point.severity]??9)-(rank[b.point.severity]??9)})}
function renderAttention(filter){
 attentionFilter=filter||"all";var list=$("attentionList"),groups=attentionGroups(attentionFilter);list.replaceChildren();
 if(!groups.length){list.style.display="none";return}list.style.display="grid";
 groups.forEach(function(group){var row=group.rows[0],point=group.point,item=element("div","attentionitem "+point.severity),copy=element("div","attentioncopy"),title=element("b","",point.title),detail=element("p","",point.detail),action=element("p","attentionaction","Do this: "+point.action),inspect=element("button","primary","Show what failed");inspect.type="button";inspect.onclick=function(){inspectBlackbox(row.run_id)};copy.append(title,detail,action);item.append(copy,inspect);list.appendChild(item)})
}
function renderBlackbox(){
 var rows=blackboxArchiveRows,chain=blackboxIndex.chain||{},attention=blackboxIndex.attention||{},box=$("blackboxFlights"),checks=$("attentionChecks");box.replaceChildren();checks.replaceChildren();
 var latest=currentRun(),groups=attentionGroups("all"),first=groups[0],hero=$("attentionHero"),hasCurrentIssue=!!first;hero.className="attentionhero"+(hasCurrentIssue?" bad":"");
 if(!latest){text("attentionHeadline","No agent activity recorded yet");text("attentionSummary","Run the agent once, then refresh this page.")}
 else if(hasCurrentIssue){text("attentionHeadline","Action needed: "+first.point.title);text("attentionSummary","Do this: "+first.point.action)}
 else{text("attentionHeadline","Healthy — no action needed");text("attentionSummary","The latest agent activity completed successfully and its audit evidence is complete. Last activity: "+displayTime(latest.ended_at)+".")}
 var legacyUpgrade=groups.some(function(group){return group.point.code==="legacy_evidence_contract"}),bridgeButton=$("bridgeRefresh");bridgeButton.style.display=legacyUpgrade?"inline-block":"none";bridgeButton.disabled=!bridgeRefreshStatus.available;text("bridgeRefresh",bridgeRefreshStatus.available?"Upgrade bridge & run test":"New bridge release required");bridgeButton.title=bridgeRefreshStatus.reason||"";
 var currentPoints=latest?(latest.attention_points||[]):[],completionBad=!latest||latest.verdict!=="completed_successfully"||currentPoints.some(function(p){return p.check==="completion"}),toolsBad=currentPoints.some(function(p){return p.check==="tools"}),evidenceBad=!latest||latest.coverage_status!=="covered"||currentPoints.some(function(p){return p.check==="context_model"});
 [[completionBad,"Flight completed",completionBad?"The latest activity did not close cleanly.":"Latest activity finished normally."],[toolsBad,"Tools worked",toolsBad?"A tool failed in the latest activity.":"No tool failure in the latest activity."],[evidenceBad,"Audit evidence complete",evidenceBad?"The latest activity is missing required evidence.":"Latest activity has complete audit evidence."]].forEach(function(value){var item=element("div","attentioncheck "+(value[0]?"bad":"ok")),badge=element("span","checknumber",value[0]?"!":"✓"),copy=element("div");copy.append(element("b","",value[1]),element("span","",value[2]));item.append(badge,copy);checks.appendChild(item)});
 $("blackboxIntegrity").className="integritychip"+(chain.valid===false?" bad":"");text("blackboxIntegrity",chain.valid===false?"✕ Audit history verification failed":"✓ Audit history verified");text("blackboxCount",number(rows.length)+" matching flight"+(rows.length===1?"":"s")+" · "+number(blackboxIndex.total_runs)+" recorded in total");
 if(!rows.length){box.appendChild(element("div","empty","No flights match this search and date range. Change the dates or select All recorded."));renderAttention(attentionFilter);return}
 rows.forEach(function(row){var item=element("div","flight"),identity=element("div"),run=element("b","mono",row.run_id),session=element("div","small mono",row.session_id||"no session ID");identity.append(run,session);
  var verdict=element("div","flightstat");verdict.append(element("b","",String(row.verdict||"unknown").replaceAll("_"," ")),element("small","","verdict"));var model=element("div","flightstat");model.append(element("b","",[row.provider,row.model].filter(Boolean).join(" / ")||"not observed"),element("small","","provider / model"));var context=element("div","flightstat");context.append(element("b","",String(row.context_disposition||"missing").replaceAll("_"," ")),element("small","","memory context"));var time=element("div","flightstat");time.append(element("b","",displayTime(row.ended_at)),element("small","","last observed"));var inspect=element("button","secondary","Inspect evidence");inspect.type="button";inspect.onclick=function(){inspectBlackbox(row.run_id)};item.append(identity,verdict,model,context,time,inspect);box.appendChild(item)});renderAttention(attentionFilter)
 updateStatusBanner();renderProductVersions()
}
function updateStatusBanner(){
 var banner=$("statusBanner");if(!banner)return;
 var reviewCount=(reviewQueue.records||[]).length;
 var latest=currentRun(),latestPoints=latest?(latest.attention_points||[]):[],attentionTotal=latestPoints.length;
 var chain=blackboxIndex.chain||{},chainValid=chain.valid!==false;
 var verification=(state&&state.verification)||{},verificationChecked=!!verification.report_sha256,verificationBad=verificationChecked&&verification.valid===false;
 var issues=reviewCount+attentionTotal+(chainValid?0:1)+(verificationBad?1:0);
 var headline="Nothing needs your attention",detail="Approvals are clear, the latest agent activity is healthy, and the audit chain is verified."+(verification.ended_at?" Last checked "+displayTime(verification.ended_at)+".":""),action=$("statusAction");action.style.display="none";action.onclick=null;
 if(reviewCount){headline=reviewCount+" memor"+(reviewCount===1?"y needs":"ies need")+" your decision";detail="These memories are quarantined and cannot reach the agent until you approve them. Open each one, then approve or permanently reject it.";text("statusAction","Review memories");action.style.display="inline-block";action.onclick=function(){$("reviewCard").scrollIntoView({behavior:"smooth",block:"start"})}}
 else if(attentionTotal){var point=latestPoints[0];headline="Latest flight: "+point.title;detail=(point.detail?"What happened: "+point.detail+" ":"")+"Next action: "+point.action+(attentionTotal>1?" · "+(attentionTotal-1)+" more issue"+(attentionTotal===2?"":"s")+" in this flight.":"");text("statusAction","Inspect this flight");action.style.display="inline-block";action.onclick=function(){inspectBlackbox(latest.run_id)}}
 else if(!chainValid){headline="Audit history cannot be verified";detail="The evidence chain failed integrity verification. Do not rely on flight history until the broken chain is investigated.";text("statusAction","Open Audit Explorer");action.style.display="inline-block";action.onclick=function(){showTab("Technical");$("auditExplorer").scrollIntoView({behavior:"smooth",block:"start"})}}
 else if(verificationBad){headline="AtMem safety verification failed";detail="The latest control-plane safety check failed. Open Technical detail and inspect the failed verification before switching or restoring memory.";text("statusAction","Open technical detail");action.style.display="inline-block";action.onclick=function(){showTab("Technical")}}
 banner.className="statusbanner"+(issues?" bad":" good");
 text("statusIcon",issues?"⚠":"✓");
 text("statusHeadline",headline);text("statusDetail",detail)
}
function localDateValue(date){var y=date.getFullYear(),m=String(date.getMonth()+1).padStart(2,"0"),d=String(date.getDate()).padStart(2,"0");return y+"-"+m+"-"+d}
function setFlightRange(range,runSearch){flightRange=range;var now=new Date(),start=new Date(now.getFullYear(),now.getMonth(),now.getDate()),end=new Date(start);if(range==="today"){end.setDate(end.getDate()+1)}else if(range==="yesterday"){end=new Date(start);start.setDate(start.getDate()-1)}else if(range==="7d"){end.setDate(end.getDate()+1);start.setDate(start.getDate()-6)}else{start=null;end=null}$("flightSince").value=start?localDateValue(start):"";if(end){var inclusive=new Date(end);inclusive.setDate(inclusive.getDate()-1);$("flightUntil").value=localDateValue(inclusive)}else $("flightUntil").value="";document.querySelectorAll("[data-flight-range]").forEach(function(button){button.classList.toggle("active",button.dataset.flightRange===range)});if(runSearch)filterBlackboxArchive()}
function flightDateBounds(){var since=$("flightSince").value?new Date($("flightSince").value+"T00:00:00"):null,until=$("flightUntil").value?new Date($("flightUntil").value+"T00:00:00"):null;if(until)until.setDate(until.getDate()+1);return{since:since,until:until}}
function flightMetadata(row){return [row.run_id,row.session_id,row.provider,row.model,row.verdict,row.coverage_status,row.context_disposition].filter(Boolean).join(" ").toLowerCase()}
function flightStoryText(story){return [story.request_text,story.response_text,story.provider,story.model,(story.tools||[]).join(" "),(story.websites||[]).join(" "),story.blocked_by,story.compromise_assessment,story.outcome_evidence].filter(Boolean).join(" ").toLowerCase()}
async function filterBlackboxArchive(){var box=$("blackboxFlights"),bounds=flightDateBounds(),status=$("flightStatus").value,query=$("flightQuery").value.trim().toLowerCase(),rows=(blackboxIndex.runs||[]).filter(function(row){var at=new Date(row.ended_at||row.started_at||0);if(bounds.since&&at<bounds.since)return false;if(bounds.until&&at>=bounds.until)return false;if(status==="healthy"&&(row.attention_points||[]).length)return false;if(status==="attention"&&!(row.attention_points||[]).length)return false;if(status==="failed"&&row.verdict==="completed_successfully")return false;return true});if(query){box.replaceChildren(loadingNode("Searching request, response, tools, websites and audit metadata…","empty"));var pending=rows.filter(function(row){return flightMetadata(row).indexOf(query)<0&&!blackboxStories[row.run_id]});for(var offset=0;offset<pending.length;offset+=8){await Promise.all(pending.slice(offset,offset+8).map(async function(row){try{blackboxStories[row.run_id]=await get("/api/blackbox/story?run_id="+encodeURIComponent(row.run_id))}catch(_){blackboxStories[row.run_id]={}}}))}rows=rows.filter(function(row){return flightMetadata(row).indexOf(query)>=0||flightStoryText(blackboxStories[row.run_id]||{}).indexOf(query)>=0})}blackboxArchiveRows=rows;renderBlackbox()}
async function loadBlackbox(){try{blackboxIndex=await get("/api/blackbox/runs?limit=500");try{bridgeRefreshStatus=await get("/api/bridge/status")}catch(_){bridgeRefreshStatus={available:false,reason:"Bridge status is unavailable."}}renderProductVersions();if(!$("flightSince").value&&!$("flightUntil").value)setFlightRange("7d",false);await filterBlackboxArchive()}catch(error){showError(error)}}
async function inspectBlackbox(runId){
 clearError();document.body.style.overflow="hidden";$("auditorBackdrop").classList.add("show");$("auditorBackdrop").setAttribute("aria-hidden","false");$("auditorBackdrop").querySelector(".drawer").scrollTop=0;text("auditorEyebrow","Flight investigation");text("auditorTitle","What this agent run did");$("auditorId").replaceChildren(evidenceChip("run",runId));$("auditorBody").replaceChildren(loadingNode("Building the flight story…","empty"));
 try{var values=await Promise.all([get("/api/blackbox/flight?run_id="+encodeURIComponent(runId)),get("/api/blackbox/story?run_id="+encodeURIComponent(runId)).catch(function(){return{}})]),report=values[0],story=values[1]||{},body=$("auditorBody"),latest=currentRun();body.replaceChildren();var matrix=report.coverage_matrix||{},overall=matrix.overall_status||"unknown",ok=overall==="covered",reportPoints=report.attention_points||[],historical=!!(latest&&latest.run_id!==runId),tools=report.tools||{},coverage=report.coverage||{},components=matrix.components||{},context=report.context||{};
  var decision=element("section","historicalnote"),decisionTitle,decisionCopy;
  if(historical){decisionTitle="Past activity — not a current alert";decisionCopy=reportPoints.length?"This flight recorded: "+reportPoints[0].title+". A later flight is healthy, so no action is required now. This record remains only for audit history.":"This is an older audit record. It does not affect the current healthy status."}
  else if(reportPoints.length){decision.className="historicalnote attentionitem high";decisionTitle="Action required now: "+reportPoints[0].title;decisionCopy="Do this: "+reportPoints[0].action}
  else{decisionTitle="Healthy — no action needed";decisionCopy="This is the latest activity. It completed normally and the required audit evidence is present."}
  decision.append(element("b","",decisionTitle),element("p","",decisionCopy));body.appendChild(decision);
  var storyCard=element("section","card"),storyFlow=element("div","storyflow"),requestText=story.request_text||"Exact request text is unavailable. AtMem retained its digest, but no matching local OpenClaw transcript was found.",responseText=story.response_text||"Exact response text is unavailable. AtMem retained its digest, but no matching local OpenClaw transcript was found.";storyCard.append(element("h2","","What happened"),element("p","sub","Read this from top to bottom. Select any memory to open its complete record history."));storyFlow.appendChild(storyStep("1","OpenClaw received this request",requestText));
  var memoryBox=element("div");if((story.memories||[]).length){(story.memories||[]).forEach(function(memory){var button=element("button","memoryline",memory.content||"Memory text unavailable"),id=element("small","mono",memory.record_id);button.type="button";button.appendChild(id);button.onclick=function(){inspectRecord(memory.record_id,function(){inspectBlackbox(runId)})};memoryBox.appendChild(button)})}else memoryBox.appendChild(element("p","storytext",Number(story.memory_count||0)?"Memory IDs were recorded, but their text is no longer available in the local mirror.":"No memory was added to this request."));storyFlow.appendChild(storyStep("2","AtMem added this memory before the model ran",memoryBox));
  storyFlow.appendChild(storyStep("3",[story.provider,story.model].filter(Boolean).join(" / ")||"The model","Model received the request plus the memory shown above."));storyFlow.appendChild(storyStep("4","The model replied",responseText));storyFlow.appendChild(storyStep("5","Tools and outcome",(story.tools||[]).length?"Tools called: "+story.tools.join(", "):"No tools were called. The flight "+(story.success?"finished successfully":"did not finish successfully")+(story.duration_ms!=null?" in "+(Number(story.duration_ms)/1000).toFixed(1)+" seconds.":".")));storyCard.appendChild(storyFlow);storyCard.appendChild(element("p","small",story.source_note||""));body.appendChild(storyCard);
  var impact=element("section","card"),impactFlow=element("div","storyflow"),usage=story.usage||{},externalBox=element("div");if(!(story.websites||[]).length&&!(story.tools||[]).length)externalBox.appendChild(element("p","storytext","No website was contacted and no external tool was called."));(story.websites||[]).forEach(function(url){var link=element("a","memoryline",url);link.href=url;link.target="_blank";link.rel="noopener noreferrer";externalBox.appendChild(link)});(story.tools||[]).forEach(function(name){var button=element("button","memoryline","Tool: "+name);button.type="button";button.onclick=function(){focusFlightEvidence(name)};externalBox.appendChild(button)});var usageText=usage.total_tokens!=null?number(usage.total_tokens)+" tokens ("+number(usage.input_tokens)+" input, "+number(usage.output_tokens)+" output).":"Token usage was not recorded.";usageText+=" "+(usage.recorded_cost_usd!=null?"Recorded model cost: $"+Number(usage.recorded_cost_usd).toFixed(4)+" USD.":"Monetary cost was not recorded, so the dashboard cannot honestly show a dollar amount.");impact.append(element("h2","","Impact, cost and risk"),element("p","sub","What left the machine, what could have changed, and what was or was not proven."));impactFlow.appendChild(storyStep("6","External systems and websites",externalBox));impactFlow.appendChild(storyStep("7","Tokens and cost",usageText));impactFlow.appendChild(storyStep("8","Data exposure and risk",(story.risks||[]).length?(story.risks||[]).join("\n"):"No additional risk was identified from the retained evidence."));impactFlow.appendChild(storyStep("9","What blocked or failed",story.blocked_by||"Nothing blocked this flight and no failure was recorded."));impactFlow.appendChild(storyStep("10","Compromise and outcome proof",(story.compromise_assessment||"No compromise assessment is available.")+"\n"+(story.outcome_evidence||"No independent outcome evidence is available.")));impact.appendChild(impactFlow);body.appendChild(impact);
  if(!historical&&reportPoints.length){var actionCard=element("section","card"),actionBody=element("div","attentionlist");actionCard.append(element("h2","","What to do now"));reportPoints.forEach(function(point){var item=element("div","attentionitem "+point.severity),copy=element("div","attentioncopy");copy.append(element("b","",point.title),element("p","",point.detail),element("p","attentionaction","Do this: "+point.action));item.append(copy);actionBody.appendChild(item)});actionCard.appendChild(actionBody);body.appendChild(actionCard)}
  var technical=element("details","technical"),technicalSummary=element("summary","","Show technical evidence, IDs and hashes");technical.appendChild(technicalSummary);
  var technicalOverview=element("section","card"),technicalGrid=element("div","evidencegrid");technicalOverview.append(element("h2","","Coverage checks"));technicalGrid.append(evidence("Overall coverage",overall.toUpperCase(),false),evidence("Integrity",components.integrity||"missing",false),evidence("Lifecycle",components.lifecycle||"missing",false),evidence("Context",components.context||"missing",false),evidence("Model",components.model||"missing",false),evidence("Tools",components.tools||"missing",false),evidence("Response",components.response||"missing",false),evidence("Events",String(report.events||0),true),evidence("Tool closure",String(tools.completed||0)+" / "+String(tools.requested||0),true),evidence("Response bound",coverage.response_digest_bound?"yes":"no",false));technicalOverview.appendChild(technicalGrid);technical.appendChild(technicalOverview);
  var correlation=report.correlation||{},correlationCard=element("section","card"),correlationGrid=element("div","evidencegrid");correlationCard.append(element("h2","","Linked evidence IDs"),element("p","sub","Select an ID to jump to the exact event that contains it."));[["Run ID",[report.run_id]],["Session IDs",correlation.session_ids],["Turn IDs",correlation.turn_ids],["Retrieval IDs",correlation.retrieval_ids],["Context event IDs",correlation.context_event_ids],["Context receipt IDs",correlation.context_receipt_ids],["Outcome IDs",correlation.outcome_ids]].forEach(function(pair){var box=element("div","evidence"),label=element("span","",pair[0]),chips=element("div","evidencechips");(pair[1]||[]).forEach(function(value){chips.appendChild(evidenceChip("open",value))});if(!chips.childNodes.length)chips.appendChild(element("b","","not recorded"));box.append(label,chips);correlationGrid.appendChild(box)});correlationCard.appendChild(correlationGrid);technical.appendChild(correlationCard);
  var timelineCard=element("section","card"),timeline=element("div","timeline");timelineCard.append(element("h2","","Evidence timeline"),element("p","sub","Open any step to see its exact IDs, hashes and retained payload."));(report.timeline||[]).forEach(function(event){var item=element("details","event");item.dataset.evidence=JSON.stringify(event);var summary=element("summary","",flightEventTitle(event.event_type)+" — "+displayTime(event.recorded_at)),chips=element("div","evidencechips");[["run",event.run_id],["turn",event.turn_id],["retrieval",event.retrieval_id],["context",event.context_event_id],["receipt",event.context_receipt_id],["outcome",event.outcome_id],["entry hash",event.entry_sha256]].forEach(function(pair){if(pair[1])chips.appendChild(evidenceChip(pair[0],pair[1]))});item.append(summary,element("p","",blackboxEventDetail(event)),chips,element("pre","eventpayload mono",JSON.stringify(event.payload||{},null,2)));timeline.appendChild(item)});timelineCard.appendChild(timeline);technical.appendChild(timelineCard);
  var boundary=element("section","card");boundary.append(element("h2","","What this proves"),element("p","",report.claim_boundary||""));technical.appendChild(boundary);var downloads=element("section","card"),links=element("div","downloads");downloads.append(element("h2","","Export evidence"));[["JSON report","json"],["Text report","text"]].forEach(function(pair){var a=element("a","secondary",pair[0]);a.href="/api/blackbox/export?run_id="+encodeURIComponent(runId)+"&format="+pair[1];links.appendChild(a)});downloads.appendChild(links);technical.appendChild(downloads);body.appendChild(technical)
 }catch(error){$("auditorBody").replaceChildren(element("div","notice show",error.message||String(error)))}
}
function isoInput(value){if(!value)return "";var d=new Date(value);return Number.isNaN(d.getTime())?"":new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16)}
function auditFilters(){
 return {query:$("auditQuery").value.trim(),event_type:$("auditType").value,actor:$("auditActor").value,
  session_id:$("auditSession").value.trim(),record_id:$("auditRecord").value.trim(),
  since:$("auditSince").value?new Date($("auditSince").value).toISOString():"",
  until:$("auditUntil").value?new Date($("auditUntil").value).toISOString():"",direction:$("auditDirection").value}
}
function auditQueryString(filters,extra){var p=new URLSearchParams();Object.keys(filters).forEach(function(k){if(filters[k])p.set(k,filters[k])});Object.keys(extra||{}).forEach(function(k){if(extra[k]!=null&&extra[k]!=="")p.set(k,extra[k])});return p.toString()}
function pivotAudit(field,value){if(!value)return;if(field==="record")$("auditRecord").value=value;if(field==="session")$("auditSession").value=value;if(field==="actor")$("auditActor").value=value;if(field==="type")$("auditType").value=value;auditSearch(true)}
function auditFacetOptions(facets){
 if(!facets)return;var type=$("auditType"),actor=$("auditActor"),selectedType=type.value,selectedActor=actor.value;
 type.replaceChildren(new Option("All event types",""));(facets.event_types||[]).forEach(function(row){type.appendChild(new Option(row.value+" ("+number(row.count)+")",row.value))});type.value=selectedType;
 actor.replaceChildren(new Option("All actors",""));(facets.actors||[]).forEach(function(row){actor.appendChild(new Option(row.value+" ("+number(row.count)+")",row.value))});actor.value=selectedActor;auditFacetsLoaded=true
}
function renderHistogram(rows){var box=$("auditHistogram");box.replaceChildren();if(!rows||!rows.length){box.appendChild(element("div","empty","No events in this time range."));return}var max=Math.max.apply(null,rows.map(function(r){return Number(r.count||0)}));rows.forEach(function(row){var bar=element("button","histbar");bar.type="button";bar.style.height=Math.max(4,Math.round(Number(row.count||0)/max*78))+"px";bar.title=row.bucket+" · "+number(row.count)+" events";bar.setAttribute("aria-label",bar.title);bar.onclick=function(){var start=new Date(row.bucket+(row.bucket.length===13?":00:00Z":"T00:00:00Z")),end=new Date(start.getTime()+(row.bucket.length===13?3600000:86400000)-1);$("auditSince").value=isoInput(start);$("auditUntil").value=isoInput(end);auditSearch(true)};box.appendChild(bar)})}
function auditSummary(row){var p=row.payload||{};if(row.event_type==="memory.recall")return number(p.returned_ids&&p.returned_ids.length)+" returned / "+number(p.candidate_count)+" candidates";if(row.event_type==="memory.context_injected")return number(p.record_ids&&p.record_ids.length)+" memories injected";if(row.event_type==="agent.response_after_memory")return "response "+shortDigest(p.response_sha256);if(p.operation)return String(p.operation);return Object.keys(p).slice(0,3).join(", ")||"Open evidence"}
function inspectAuditEvent(row){
 document.body.style.overflow="hidden";$("auditorBackdrop").classList.add("show");$("auditorBackdrop").setAttribute("aria-hidden","false");$("auditorBackdrop").querySelector(".drawer").scrollTop=0;text("auditorEyebrow","Evidence event");text("auditorTitle",row.event_type);text("auditorId",row.event_id);
 var body=$("auditorBody");body.replaceChildren();var integrity=element("p","integrity","✓ Event is bound to the verified chain");body.appendChild(integrity);
 var overview=element("section","card"),grid=element("div","evidencegrid");overview.append(element("h2","","Event details"),element("p","sub","Pivot from any linked identifier to narrow the global investigation."));grid.append(evidence("Sequence",String(row.sequence),true),evidence("Time",displayTime(row.created_at),false),evidence("Actor",row.actor,false),evidence("Event ID",row.event_id,true),evidence("Previous hash",row.prev_hash,true),evidence("Event hash",row.event_hash,true));overview.appendChild(grid);body.appendChild(overview);
 var pivots=element("section","card"),links=element("div","downloads"),payloadValue=row.payload||{};pivots.append(element("h2","","Follow linked evidence"));[["record",row.record_id,"Record"],["session",row.session_id,"Session"],["actor",row.actor,"Actor"],["type",row.event_type,"Event type"]].forEach(function(v){if(!v[1])return;var b=element("button","secondary",v[2]+": "+v[1]);b.onclick=function(){closeAuditor();pivotAudit(v[0],v[1])};links.appendChild(b)});
 var linkedRecords=[];["record_id","record_ids","returned_ids","injected_record_ids","purged_record_ids","supersedes"].forEach(function(key){var value=payloadValue[key];(Array.isArray(value)?value:[value]).filter(Boolean).forEach(function(id){if(String(id).indexOf("rec_")===0&&linkedRecords.indexOf(String(id))<0)linkedRecords.push(String(id))})});linkedRecords.forEach(function(id){var b=element("button","secondary","Memory: "+id);b.onclick=function(){inspectRecord(id)};links.appendChild(b)});
 ["retrieval_id","run_id","outcome_id","transaction_id","operation_id","artifact_id","observation_id"].forEach(function(key){if(!payloadValue[key])return;var id=String(payloadValue[key]),b=element("button","secondary",key.replace("_id","")+": "+id);b.onclick=function(){closeAuditor();$("auditQuery").value=id;auditSearch(true)};links.appendChild(b)});if(row.record_id){var inspect=element("button","primary","Open record history");inspect.onclick=function(){inspectRecord(row.record_id)};links.appendChild(inspect)}pivots.appendChild(links);body.appendChild(pivots);
 var payload=element("section","card");payload.append(element("h2","","Canonical payload"),element("p","sub","The exact structured evidence covered by the event hash."),element("pre","eventpayload mono",JSON.stringify(row.payload||{},null,2)));body.appendChild(payload)
}
function renderAudit(report){
 auditLast=report;auditFacetOptions(report.facets);renderHistogram(report.histogram);var rows=$("auditRows");rows.replaceChildren();
 if(!(report.events||[]).length){var tr=element("tr"),td=element("td","empty","No audit events match these filters.");td.colSpan=7;tr.appendChild(td);rows.appendChild(tr)}
 (report.events||[]).forEach(function(row){var tr=element("tr"),time=element("td","",displayTime(row.created_at)),event=element("td"),eventBtn=element("button","eventbutton",row.event_type),summary=element("div","small",auditSummary(row));eventBtn.onclick=function(){inspectAuditEvent(row)};event.append(eventBtn,summary);
  var actor=element("td"),actorBtn=element("button","pivot",row.actor);actorBtn.onclick=function(){pivotAudit("actor",row.actor)};actor.appendChild(actorBtn);
  var record=element("td");if(row.record_id){var recordBtn=element("button","pivot mono",row.record_id);recordBtn.onclick=function(){inspectRecord(row.record_id)};record.appendChild(recordBtn)}else record.textContent="—";
  var session=element("td");if(row.session_id){var sessionBtn=element("button","pivot mono",row.session_id);sessionBtn.onclick=function(){pivotAudit("session",row.session_id)};session.appendChild(sessionBtn)}else session.textContent="—";if(row.turn_id)session.appendChild(element("div","small mono",row.turn_id));
  tr.append(time,event,actor,record,session,element("td","mono",row.event_id),element("td","integrity","verified"));rows.appendChild(tr)
 });
 $("auditIntegrity").className="integritychip"+(report.audit_chain_valid?"":" bad");text("auditIntegrity",report.audit_chain_valid?"✓ Chain verified":"✕ Verification failed");text("auditCount",number(report.matched_total)+" matching · "+number((report.events||[]).length)+" on this page");text("auditDigest",shortDigest(report.result_digest));text("auditPage","Page "+(auditPageIndex+1));$("auditBack").disabled=auditPageIndex===0;$("auditNext").disabled=!report.has_more;
 document.querySelectorAll(".auditexport").forEach(function(a){a.href="/api/mirror/audit-export?"+auditQueryString(auditFilters(),{format:a.dataset.format})})
}
async function loadAudit(includeFacets){
 clearError();$("auditRows").replaceChildren(tableLoading("Loading audit evidence…"));try{var extra={limit:$("auditLimit").value,include_facets:includeFacets?1:0},cursor=auditCursors[auditPageIndex];if(cursor!=null)extra.cursor=cursor;var report=await get("/api/mirror/audit?"+auditQueryString(auditFilters(),extra));renderAudit(report)}catch(error){showError(error)}
}
function auditSearch(reset){if(reset){auditCursors=[null];auditPageIndex=0}loadAudit(!auditFacetsLoaded||reset)}
function savedViews(){try{return JSON.parse(localStorage.getItem("atmem-audit-views")||"[]")}catch(_){return []}}
function renderSavedViews(){var select=$("auditSaved");select.replaceChildren(new Option("Saved views…",""));savedViews().forEach(function(view,index){select.appendChild(new Option(view.name,String(index)))})}
function applyAuditFilters(f){$("auditQuery").value=f.query||"";$("auditType").value=f.event_type||"";$("auditActor").value=f.actor||"";$("auditSession").value=f.session_id||"";$("auditRecord").value=f.record_id||"";$("auditSince").value=isoInput(f.since);$("auditUntil").value=isoInput(f.until);$("auditDirection").value=f.direction||"desc"}
function closeAuditor(){$("auditorBackdrop").classList.remove("show");$("auditorBackdrop").setAttribute("aria-hidden","true");document.body.style.overflow=""}
function recordSessionName(sessionId){var value=String(sessionId||"");if(value.indexOf(":investigator")>=0)return "AtMem dashboard search";if(value.indexOf("atmem-bridge-self-test")>=0)return "OpenClaw bridge self-test";if(value.indexOf("dashboard")>=0)return "Dashboard memory check";return value?"Agent session":"Session name was not recorded"}
function recordEvidenceChip(label,value){var button=element("button","evidencechip",label+": "+value);button.type="button";button.title="Find this value in the complete audit history";button.onclick=function(){closeAuditor();showTab("Technical");$("auditQuery").value=String(value);auditSearch(true);$("auditQuery").scrollIntoView({behavior:"smooth",block:"center"})};return button}
async function inspectRecord(recordId,backAction){
 clearError();document.body.style.overflow="hidden";$("auditorBackdrop").classList.add("show");$("auditorBackdrop").setAttribute("aria-hidden","false");
 $("auditorBackdrop").querySelector(".drawer").scrollTop=0;text("auditorEyebrow","Memory record history");text("auditorTitle","Memory record");text("auditorId",recordId);$("auditorBody").replaceChildren(loadingNode("Verifying the complete record history…","empty"));
 try{
  var report=await get("/api/mirror/record?record_id="+encodeURIComponent(recordId)),record=report.record||{},p=report.provenance||{},life=report.lifecycle||{},deliveries=report.deliveries||[],timeline=report.timeline||[],body=$("auditorBody");body.replaceChildren();
  if(backAction){var back=element("button","secondary backlink","← Back to flight");back.type="button";back.onclick=backAction;body.appendChild(back)}
  var integrity=element("p","integrity"+(report.audit_chain_valid?"":" bad"),report.audit_chain_valid?"✓ Audit chain verified":"✕ Audit chain verification failed");body.appendChild(integrity);
  var memoryCard=element("section","card");memoryCard.append(element("h2","","Stored memory"),element("p","recordcontent",record.content||"The memory content was purged; retained audit evidence is shown below."));body.appendChild(memoryCard);
  var considered=deliveries.length,returned=deliveries.filter(function(d){return d.returned}).length,injected=deliveries.filter(function(d){return d.context_injected_at}).length,bound=deliveries.filter(function(d){return d.response_sha256}).length;
  var investigatorReturns=deliveries.filter(function(d){return String(d.session_id||"").indexOf(":investigator")>=0&&d.returned}).length,nonInvestigatorReturns=returned-investigatorReturns,usageCard=element("section","card"),usageSummary=injected?"This memory was proven to reach the model in "+injected+" recorded "+(injected===1?"run":"runs")+".":nonInvestigatorReturns?"An agent memory search returned this memory, but the retained evidence does not prove it reached the model.":investigatorReturns?"This memory appeared in a read-only dashboard search. No agent or model was involved.":considered?"This memory was considered by search, but was not used.":"This memory has not appeared in a recorded memory search.";usageCard.append(element("h2","","How this memory was used"),element("p","sub",usageSummary));
  if(!deliveries.length)usageCard.appendChild(element("div","empty","No recorded agent run searched for this memory."));
  deliveries.forEach(function(d){var used=!!d.context_injected_at,wasReturned=!!d.returned,isInvestigator=String(d.session_id||"").indexOf(":investigator")>=0,title=isInvestigator?(wasReturned?"Shown in dashboard search — no model involved":"Considered by dashboard search — not shown"):used?"Used in a model request":wasReturned?"Returned by agent memory search; injection not proven":"Considered but not used",explanation=isInvestigator?(wasReturned?"The AtMem dashboard displayed this memory as a search result. This was a read-only investigation: it did not run an agent, call a model, or inject the memory into model context.":"The AtMem dashboard evaluated this memory as a possible search result but did not display it. No agent or model was involved."):used?"AtMem selected this memory and added it to the context sent to the model.":wasReturned?"AtMem returned this memory from an agent memory search, but there is no retained context event proving it was sent to the model.":"AtMem evaluated this memory as a possible match, but did not return it or add it to the model context.";if(used&&d.response_sha256)explanation+=" A model response was recorded afterward.";var item=element("details","delivery"+(used?" used":wasReturned?" returned":"")),summary=element("summary","",title+" — "+displayTime(d.recalled_at)),inside=element("div","deliverybody"),chips=element("div","evidencechips");inside.append(element("p","",explanation),element("p","small",recordSessionName(d.session_id)));[["retrieval",d.retrieval_id],["session",d.session_id],["context event",d.context_event_id],["response event",d.response_event_id],["response fingerprint",d.response_sha256]].forEach(function(pair){if(pair[1])chips.appendChild(recordEvidenceChip(pair[0],pair[1]))});inside.append(chips,element("p","small","Technical search position: rank "+(d.rank==null?"not recorded":d.rank)+"; similarity score "+(d.score==null?"not recorded":d.score)+". These values explain retrieval ordering; they do not mean the memory reached the model."));item.append(summary,inside);usageCard.appendChild(item)});body.appendChild(usageCard);
  var technical=element("details","technical");technical.appendChild(element("summary","","Show technical record evidence, IDs and hashes"));
  var chain=element("div","chain");var delivered=deliveries.some(function(d){return !!d.context_injected_at}),responded=deliveries.some(function(d){return !!d.response_sha256});
  chain.append(chainStep("Source",!!p.source_message_sha256,shortDigest(p.source_message_sha256)),chainStep("Interpret",!!p.interpreting_model,p.interpreting_model||"native import"),chainStep("Admit",!!life.created_at,displayTime(life.created_at)),chainStep("Recall",deliveries.length>0,deliveries.length+" attempt"+(deliveries.length===1?"":"s")),chainStep("Inject",delivered,delivered?"context receipt":"not recorded"),chainStep("Reply",responded,responded?"fingerprint recorded":"not recorded"));
  var chainCard=element("section","card");chainCard.append(element("h2","","Evidence chain"),element("p","sub","Source → interpretation → admission → recall → context injection → agent response"),chain);technical.appendChild(chainCard);
  var prov=element("section","card"),provGrid=element("div","evidencegrid");prov.append(element("h2","","Source and interpretation"),element("p","sub","Digests prove identity without exposing the original message."));
  provGrid.append(evidence("Source-message SHA-256",p.source_message_sha256,true),evidence("Interpreting model",p.interpreting_model||"Native OpenClaw import",false),evidence("Source binding",p.source_binding||p.interpretation_assurance,false),evidence("Native source",p.native_path||"Not a native-file import",true),evidence("Episode",p.episode_id,true),evidence("Memory plane",p.plane,false));prov.appendChild(provGrid);technical.appendChild(prov);
  var lifecycle=element("section","card"),lifeGrid=element("div","evidencegrid");lifecycle.append(element("h2","","Record lifecycle"),element("p","sub","Canonical state changes preserved in chronological audit evidence."));lifeGrid.append(evidence("Status",report.status,false),evidence("Created",displayTime(life.created_at),false),evidence("Superseded",life.superseded_at?displayTime(life.superseded_at):"Not superseded",false),evidence("Deleted",life.deleted_at?displayTime(life.deleted_at):"Not deleted",false));lifecycle.appendChild(lifeGrid);technical.appendChild(lifecycle);
  var deliveryCard=element("section","card"),deliveryStats=element("div","evidencegrid");deliveryCard.append(element("h2","","Retrieval totals"),element("p","sub","Technical counts across every recorded search involving this memory."));deliveryStats.append(evidence("Considered",String(considered),true),evidence("Returned",String(returned),true),evidence("Injected",String(injected),true),evidence("Response-bound",String(bound),true));deliveryCard.appendChild(deliveryStats);technical.appendChild(deliveryCard);
  var timeCard=element("section","card"),timeBox=element("div","timeline");timeCard.append(element("h2","","Complete chronological history"),element("p","sub",timeline.length+" linked evidence event"+(timeline.length===1?"":"s")+"."));
  timeline.forEach(function(e){var item=element("div","event");item.append(element("b","",e.title||e.type),element("p","",e.detail||""),element("div","small mono",displayTime(e.at)+" · "+(e.actor||"unknown actor")+" · "+(e.event_id||"no evidence ID")+(e.session_id?" · "+e.session_id:"")));timeBox.appendChild(item)});if(!timeline.length)timeBox.appendChild(element("div","empty","No linked events were retained."));timeCard.appendChild(timeBox);technical.appendChild(timeCard);
  var downloads=element("section","card"),links=element("div","downloads");downloads.append(element("h2","","Export evidence"),element("p","sub","Download a portable investigation report. A deletion receipt appears only after a verified purge."));
  [["JSON report","json"],["Text report","text"]].forEach(function(pair){var a=element("a","secondary",pair[0]);a.href="/api/mirror/record-report?record_id="+encodeURIComponent(recordId)+"&format="+pair[1];links.appendChild(a)});
  if(report.deletion_receipt){var receipt=element("a","secondary","Deletion receipt");receipt.href="/api/mirror/deletion-receipt?record_id="+encodeURIComponent(recordId);links.appendChild(receipt)}downloads.appendChild(links);technical.appendChild(downloads);body.appendChild(technical)
 }catch(error){$("auditorBody").replaceChildren(element("div","notice show",error.message||String(error)))}
}
function renderSources(mirror){
 var box=$("sources");box.replaceChildren();var rows=Array.isArray(mirror.sources)?mirror.sources:[];
 if(!rows.length){box.appendChild(element("div","empty","No mirrored source files were found."));return}
 rows.forEach(function(row){
  var item=element("div","source"),head=element("div","sourcehead"),name=element("b","",row.relative_path||"unknown");
  var bytes=element("span","small mono",number(row.bytes)+" bytes"),plane=element("span","plane",row.plane||"memory");
  head.append(name,bytes,plane);item.append(head);
  item.appendChild(element("div","digest mono","SHA-256  "+(row.sha256||"not recorded")));
  box.appendChild(item)
 });
 text("sourceSummary",rows.length+" verified source file"+(rows.length===1?"":"s")+" from "+(mirror.workspace||"the OpenClaw workspace")+".")
}
function renderReviews(){
 var box=$("reviews"),rows=Array.isArray(reviewQueue.records)?reviewQueue.records:[];box.replaceChildren();text("reviewCount",rows.length);
 if(typeof updateStatusBanner==="function")updateStatusBanner();
 if(!rows.length){box.appendChild(element("div","empty","Nothing is waiting for approval."));return}
 rows.forEach(function(row){
  var item=element("div","reviewitem"),content=element("p","reviewcontent",row.content||"Content unavailable"),meta=element("div","reviewmeta");
  meta.append(element("span","pill",row.media&&row.media.modality?row.media.modality:(row.scope||"observation")),element("span","small",displayTime(row.created_at)));
  var inspect=element("button","recordlink mono",row.record_id);inspect.type="button";inspect.onclick=function(){inspectRecord(row.record_id)};meta.appendChild(inspect);
  if(row.media&&row.media.extractor){var extractor=row.media.extractor;meta.append(element("span","small",[extractor.provider,extractor.model,extractor.version].filter(Boolean).join(" / ")||"extractor recorded"))}
  var isImage=Boolean(row.media&&row.media.modality==="image"),actions=element("div","reviewactions"),approve=element("button","primary approve",isImage?"Approve description as memory":"Approve as memory"),reject=element("button","reject","Reject and purge");
  approve.type="button";reject.type="button";approve.onclick=function(){reviewRecord(row,"approve")};reject.onclick=function(){reviewRecord(row,"reject")};
  item.appendChild(meta);
  if(isImage){
   var compare=element("div","reviewcompare"),source=element("section","reviewpane"),remembered=element("section","reviewpane"),image=element("img","reviewimage"),status=element("p","previewstatus","Verifying the exact source image…");
   source.append(element("h3","","Source image being reviewed"));image.alt="Source image bound to this observation";image.src=row.media.preview_url||"";approve.disabled=true;
   image.onload=function(){status.textContent="Source bytes verified against SHA-256 "+String(row.media.media_sha256||"").slice(0,16)+"…";status.className="previewstatus";approve.disabled=false};
   image.onerror=function(){image.remove();status.textContent="The exact source image is unavailable or no longer matches its recorded digest. Approval is disabled.";status.className="previewstatus bad";approve.disabled=true};
   source.append(image,status);remembered.append(element("h3","","What AtMem will remember"),content,element("p","reviewboundary","Future agents receive this text description, not the image pixels. The original image remains controlled by OpenClaw."));
   compare.append(source,remembered);item.appendChild(compare)
  }else item.appendChild(content);
  actions.append(approve,reject);item.appendChild(actions);box.appendChild(item)
 })
}
async function reviewRecord(row,decision){
 var approving=decision==="approve",verb=approving?"approve":"reject and permanently purge";
 var subject=row.media&&row.media.modality==="image"?"this exact text description as recallable memory":"this exact memory";
 if(!confirm("Do you want to "+verb+" "+subject+"?\n\n"+(row.content||"")))return;
 try{await working(approving?"Approving memory":"Rejecting memory",approving?"Activating the exact reviewed record and writing an audit event.":"Purging the exact reviewed record and verifying derived-index cleanup.",async function(){await post("/api/mirror/review",{record_id:row.record_id,confirm_record_id:row.record_id,decision:decision});await reload()})}
 catch(error){showError(error)}
}
async function refreshReviews(){
 try{reviewQueue=await get("/api/mirror/reviews");renderReviews()}catch(error){showError(error)}
}
function addCheck(label,ok,detail){
 var row=element("div","check"+(ok?"":" pending")),icon=element("i","",ok?"✓":"!"),body=element("div","",label);
 if(detail)body.appendChild(element("span","", " — "+detail));row.append(icon,body);$("checks").appendChild(row)
}
function render(){
 if(!state)return;var mirror=state.mirror||{},takeover=state.takeover||{},isActive=active(),needsRecovery=recovery(),readiness=state.readiness||{};
 $("stateChip").className="state"+(isActive?" active":"");
 text("stateChip",isActive?"AtMem active":needsRecovery?"Restore required":"OpenClaw active");
 text("eyebrow",isActive?"Current memory provider":needsRecovery?"Interrupted switch detected":"Safe side-by-side copy");
 text("title",isActive?"AtMem is managing OpenClaw memory":needsRecovery?"Restore OpenClaw before activating":"OpenClaw memory is still active");
 text("summary",isActive
  ?"AtMem now serves bounded, governed memory. Your original OpenClaw memory is preserved for restoration."
  :needsRecovery
  ?(takeover.recovery_message||"AtMem preserved the switch evidence and must verify restoration before another activation.")
  :"AtMem mirrors and verifies your existing memory without changing what OpenClaw uses.");
 text("sourceCount",mirror.source_count);text("recordCount",mirror.record_count);text("sourceBytes",number(mirror.source_bytes));
 text("verified",mirror.audit_verified?"PASSED":"CHECK");
 text("switchBtn",isActive||needsRecovery?"Restore OpenClaw":"Activate AtMem");
 $("switchBtn").classList.toggle("danger",isActive||needsRecovery);$("switchBtn").setAttribute("aria-label",isActive||needsRecovery?"Restore OpenClaw memory provider":"Activate AtMem memory provider");
 $("refreshBtn").style.display=isActive||needsRecovery?"none":"inline-block";
 $("switchBtn").disabled=isActive||needsRecovery?false:!readiness.ready_for_active;
 text("switchTitle",isActive||needsRecovery?"Restore OpenClaw":"Ready to activate?");
 text("switchCopy",isActive||needsRecovery
  ?"Restore the verified native files and make OpenClaw memory authoritative again."
  :"One switch freezes the current native state, verifies the AtMem integration, and restores the prior state automatically if anything fails.");
 text("identity",(state.host||"openclaw")+" · "+(state.subject_id||"local-user")+" · "+(state.migration_id||""));
 var drill=state.restore_drill||{};
 var verification=state.verification||{};
 text("verifyStatus",verification.report_sha256
  ?(verification.valid?"Last verification passed":"Last verification failed")+" · "+displayTime(verification.ended_at)+"\nEvidence "+shortDigest(verification.evidence_sha256)+" · report "+shortDigest(verification.report_sha256)
  :"No control verification recorded.");
 $("verifyStatus").style.whiteSpace="pre-line";
 text("drillStatus",drill.valid
  ?"File restoration tested "+displayTime(drill.ended_at)+"\nSaved configuration readable\nLive rollback not performed"
  :"No restore drill recorded. This test does not change live files or configuration.");
 $("drillStatus").style.whiteSpace="pre-line";
 $("drillBtn").style.display=(isActive||needsRecovery)?"inline-block":"none";
 renderSources(mirror);renderReviews();$("checks").replaceChildren();
 if(isActive){
  addCheck("Native memory snapshot",!!takeover.native_snapshot_verified,"verified");
  addCheck("OpenClaw gateway",!!takeover.gateway_verified,"running");
  addCheck("Memory tools",!!takeover.compatibility_tools_verified,"memory_search and memory_get");
  addCheck("Capture hooks",!!takeover.capture_hooks_verified,"verified");
 }else if(needsRecovery){
  addCheck("Interrupted switch",false,"status: "+(takeover.status||"unknown"));
  addCheck("Recovery action",false,"Restore OpenClaw verifies the preserved files");
 }else{
  addCheck("Mirror synchronized",!!mirror.synced,number(mirror.source_count)+" sources");
  addCheck("Mirror audit",!!mirror.audit_verified,mirror.audit_error||"verified");
  addCheck("Searchable records",number(mirror.record_count)>0,number(mirror.record_count)+" ready");
  addCheck("Safe activation",!!readiness.ready_for_active,(readiness.reasons||[])[0]||"ready");
 }
 updateStatusBanner();renderProductVersions()
}
async function reload(){var values=await Promise.all([get("/api/status"),get("/api/mirror/reviews")]);state=values[0];reviewQueue=values[1];render()}
async function search(){
 var query=$("query").value.trim();if(!query)return;clearError();$("results").replaceChildren(loadingNode("Searching memory…","empty"));
 try{
  var value=await get("/api/mirror/search?query="+encodeURIComponent(query)),rows=value.records||[],box=$("results");box.replaceChildren();
  if(!rows.length){box.appendChild(element("div","empty","No matching memory found."));return}
  rows.forEach(function(row){
   var p=row.openclaw_provenance||{},item=element("div","result"),body=element("p","",row.match_excerpt||row.content||"");
   var meta=element("div","meta");meta.append(element("span","pill",p.plane||row.scope||"memory"));
   if(row.id){var recordButton=element("button","recordlink mono",row.id);recordButton.type="button";recordButton.onclick=function(){inspectRecord(row.id)};meta.append(recordButton)}
   else meta.append(element("span","mono",p.relative_path||""));
   if(p.relative_path)meta.append(element("span","mono",p.relative_path));
   if(p.line_start)meta.append(element("span","mono","lines "+p.line_start+"–"+(p.line_end||p.line_start)));
   item.append(body,meta);box.appendChild(item)
  })
 }catch(error){showError(error)}
}
async function refresh(){
 try{await working("Refreshing the memory mirror","Reading native files, rebuilding the search index, and verifying its audit evidence.",async function(){await post("/api/mirror/sync",{});await reload()})}
 catch(error){showError(error)}
}
async function restoreDrill(){
 try{await working("Testing file restoration","Staging the frozen files and checking saved configuration without changing the live OpenClaw installation.",async function(){await post("/api/restore-drill",{});await reload()})}
 catch(error){showError(error)}
}
async function verifyNow(){
 try{await working("Verifying the memory switch","Measuring configuration, mirror integrity, restore readiness, versions, and gateway health without repairing or restarting anything.",async function(){await post("/api/verify",{});await reload()})}
 catch(error){showError(error)}
}
async function refreshBridgeAndTest(){
 if(!state)return;var expected=state.host||"openclaw";
 var entered=prompt("This briefly restarts OpenClaw and may incur a small model charge. Type '"+expected+"' to upgrade the bridge and run one self-test:");if(entered===null)return;
 try{await working("Refreshing the OpenClaw bridge","Installing the version pinned by AtMem, restarting the gateway, verifying the plugin, and recording one fresh test flight.",async function(){var result=await post("/api/bridge/refresh-test",{confirm_host:entered});await reload();await loadBlackbox();if(result.test_flight&&result.test_flight.run_id)await inspectBlackbox(result.test_flight.run_id)})}
 catch(error){showError(error)}
}
async function switchProvider(){
 if(!state)return;clearError();
 if(active()||recovery()){
  if(!confirm("Restore the verified OpenClaw memory and stop AtMem memory takeover?"))return;
  try{await working("Restoring OpenClaw memory","Restoring and verifying the frozen native files, then restarting OpenClaw. This can take a minute.",async function(){await post("/api/restore",{});await reload()})}
  catch(error){showError(error)}
  return
 }
 var expected=state.host||"openclaw";
 var entered=prompt("To activate AtMem, type '"+expected+"':");
 if(entered===null)return;
 try{await working("Activating AtMem","Freezing native memory, checking compatibility, restarting OpenClaw, and verifying memory tools. This can take a minute.",async function(){await post("/api/mode",{mode:"active",confirm_host:entered});await reload()})}
 catch(error){showError(error)}
}
function showTab(name){
 document.querySelectorAll(".tabpanel").forEach(function(panel){panel.classList.toggle("active",panel.id==="tab"+name)});
 document.querySelectorAll(".tabbtn").forEach(function(btn){var isActive=btn.id==="tabBtn"+name;btn.classList.toggle("active",isActive);btn.setAttribute("aria-selected",isActive?"true":"false")})
}
$("tabBtnOverview").onclick=function(){showTab("Overview")};$("tabBtnTechnical").onclick=function(){showTab("Technical")};
$("searchBtn").onclick=search;$("query").addEventListener("keydown",function(event){if(event.key==="Enter")search()});
$("refreshBtn").onclick=refresh;$("switchBtn").onclick=switchProvider;
$("drillBtn").onclick=restoreDrill;
$("verifyBtn").onclick=verifyNow;
$("bridgeRefresh").onclick=refreshBridgeAndTest;
$("reviewRefresh").onclick=refreshReviews;
$("blackboxRefresh").onclick=loadBlackbox;
$("flightSearch").onclick=filterBlackboxArchive;$("flightQuery").addEventListener("keydown",function(event){if(event.key==="Enter")filterBlackboxArchive()});$("flightStatus").onchange=filterBlackboxArchive;[$("flightSince"),$("flightUntil")].forEach(function(input){input.onchange=function(){flightRange="custom";document.querySelectorAll("[data-flight-range]").forEach(function(button){button.classList.remove("active")});filterBlackboxArchive()}});document.querySelectorAll("[data-flight-range]").forEach(function(button){button.onclick=function(){setFlightRange(button.dataset.flightRange,true)}});
$("auditRun").onclick=function(){auditSearch(true)};$("auditQuery").addEventListener("keydown",function(event){if(event.key==="Enter")auditSearch(true)});
$("auditDirection").onchange=function(){auditSearch(true)};$("auditLimit").onchange=function(){auditSearch(true)};
$("auditNext").onclick=function(){if(!auditLast||!auditLast.next_cursor)return;auditCursors=auditCursors.slice(0,auditPageIndex+1);auditCursors.push(auditLast.next_cursor);auditPageIndex++;loadAudit(false)};
$("auditBack").onclick=function(){if(auditPageIndex===0)return;auditPageIndex--;loadAudit(false)};
document.querySelectorAll("[data-range]").forEach(function(button){button.onclick=function(){var minutes=Number(button.dataset.range||0),now=new Date();$("auditUntil").value=minutes?isoInput(now):"";$("auditSince").value=minutes?isoInput(new Date(now.getTime()-minutes*60000)):"";auditSearch(true)}});
document.querySelectorAll("[data-event-pattern]").forEach(function(button){button.onclick=function(){var pattern=button.dataset.eventPattern||"",select=$("auditType");if(!Array.from(select.options).some(function(o){return o.value===pattern}))select.appendChild(new Option(pattern,pattern));select.value=pattern;auditSearch(true)}});
$("auditReset").onclick=function(){applyAuditFilters({});auditSearch(true)};
$("auditSave").onclick=function(){var name=prompt("Name this audit view:");if(!name||!name.trim())return;var views=savedViews();views.push({name:name.trim(),filters:auditFilters()});localStorage.setItem("atmem-audit-views",JSON.stringify(views));renderSavedViews();$("auditSaved").value=String(views.length-1)};
$("auditSaved").onchange=function(){var view=savedViews()[Number($("auditSaved").value)];if(!view)return;applyAuditFilters(view.filters||{});auditSearch(true)};
$("auditorClose").onclick=closeAuditor;$("auditorBackdrop").addEventListener("click",function(event){if(event.target===$("auditorBackdrop"))closeAuditor()});document.addEventListener("keydown",function(event){if(event.key==="Escape")closeAuditor()});
applyTheme(preferredTheme(),false);$("themeToggle").onclick=function(){applyTheme(document.documentElement.dataset.theme==="dark"?"light":"dark",true)};
async function init(){try{csrf=(await get("/api/session")).csrf_token;renderSavedViews();await Promise.all([get("/api/product").then(function(value){productInfo=value;renderProductVersions()}),reload(),loadAudit(true),loadBlackbox()]);setInterval(refreshReviews,5000)}catch(error){showError(error)}}
init()
})();
</script>
</body>
</html>
"""
