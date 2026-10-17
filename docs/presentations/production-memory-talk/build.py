#!/usr/bin/env python3
"""Build the standalone viewer and transcript for the production-memory talk.

The slide sources in ``slides/`` use the Claude Slides format: one
``<section>`` per file on a 1920x1080 canvas, speaker notes in ``<aside>``.
This script needs only the standard library and writes:

* ``index.html``     a self-contained browser viewer (arrow keys, N for notes)
* ``TRANSCRIPT.md``  the spoken script, one heading per slide

Run from any directory:  python docs/presentations/production-memory-talk/build.py
"""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent


class _SlideText(HTMLParser):
    """Collect the first h1/h2 heading and the aside text of one slide."""

    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.notes = ""
        self._stack: list[str] = []
        self._title_done = False

    def handle_starttag(self, tag: str, attrs) -> None:
        self._stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("h1", "h2") and self.title:
            self._title_done = True
        while self._stack:
            if self._stack.pop() == tag:
                break

    def handle_data(self, data: str) -> None:
        if "aside" in self._stack:
            self.notes += data
        elif not self._title_done and any(t in self._stack for t in ("h1", "h2")):
            self.title += data


def _load() -> tuple[dict, list[tuple[str, str]]]:
    deck = json.loads((HERE / "deck.json").read_text(encoding="utf-8"))
    slides = []
    for slide_id in deck["order"]:
        source = (HERE / "slides" / f"{slide_id}.html").read_text(encoding="utf-8")
        slides.append((slide_id, source.strip()))
    return deck, slides


def _paragraphs(text: str) -> str:
    text = text.strip()
    if "\n\n" in text:
        return "\n\n".join(" ".join(p.split()) for p in text.split("\n\n"))
    return " ".join(text.split())


def build_transcript(deck: dict, slides: list[tuple[str, str]]) -> str:
    starts = {s["start"]: s["description"] for s in deck.get("sections", {}).values()}
    lines = [f"# {deck['title']} — talk transcript", ""]
    lines.append(
        "Speaker script for the slides in `slides/`. Open `index.html` to present; "
        "press **N** to show these notes beside each slide."
    )
    lines.append("")
    for number, (slide_id, source) in enumerate(slides, start=1):
        if slide_id in starts:
            lines += [f"## {starts[slide_id]}", ""]
        parser = _SlideText()
        parser.feed(source)
        title = " ".join(parser.title.split()) or slide_id
        lines += [f"### {number}. {title}", "", _paragraphs(parser.notes), ""]
    return "\n".join(lines).rstrip() + "\n"


VIEWER_CSS = """
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:#0b121b;color:#eef1f4;font-family:'IBM Plex Sans',Arial,sans-serif;overflow:hidden}
#stage{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
#canvas{width:1920px;height:1080px;position:relative;transform-origin:center center;flex:none}
#canvas>section{width:1920px;height:1080px;position:absolute;inset:0;overflow:hidden}
#canvas>section:not(.on){display:none!important}
section h1,section h2,section h3,section p,section ul,section ol{margin:0}
section h1{font-size:96px;font-weight:600;line-height:1.1}
section h2{font-size:64px;font-weight:600;line-height:1.15}
section h3{font-size:44px;font-weight:600;line-height:1.2}
section p{font-size:32px;line-height:1.4}
section ul,section ol{padding-left:1.2em}
section table{width:100%;border-collapse:collapse}
section th,section td{padding:.35em .6em;border-bottom:1px solid #d9d5cc;text-align:left;vertical-align:top}
section th{font-weight:600}
section aside{display:none}
x-shape,x-icon{display:block;flex:none}
x-shape svg,x-icon svg{display:block;width:100%;height:100%}
#notes{position:absolute;right:0;top:0;bottom:0;width:min(520px,40vw);background:#13202f;border-left:1px solid #3a4d63;padding:24px 28px;overflow:auto;font-size:17px;line-height:1.55;white-space:pre-wrap;display:none}
body.notes #notes{display:block}
body.notes #stage{right:min(520px,40vw)}
#bar{position:absolute;left:16px;bottom:12px;font-size:14px;color:#8fa3b8;user-select:none}
"""

VIEWER_JS = r"""
(function(){
const NS='http://www.w3.org/2000/svg';
const ICONS={
 Code:'<path d="M8 6 2 12l6 6M16 6l6 6-6 6M14 4l-4 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
 Users:'<circle cx="9" cy="8" r="3.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5M16 4.8a3.4 3.4 0 0 1 0 6.4M18 14.8c2 .7 3.2 2.5 3.6 5.2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
 Globe:'<circle cx="12" cy="12" r="9.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M2.5 12h19M12 2.5c3 3 3 16 0 19M12 2.5c-3 3-3 16 0 19" fill="none" stroke="currentColor" stroke-width="2"/>',
 Lock:'<rect x="4" y="10.5" width="16" height="11" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5" fill="none" stroke="currentColor" stroke-width="2"/>',
 Trust:'<path d="M12 2.5 4 5.5v6c0 5 3.4 8.6 8 10 4.6-1.4 8-5 8-10v-6z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="m8.5 12 2.5 2.5 4.5-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
};
function icon(el){
  const name=el.getAttribute('name');
  el.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true">'+(ICONS[name]||'<circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="2"/>')+'</svg>';
}
function shape(el){
  const kind=el.getAttribute('kind');
  const fill=el.style.background||el.style.backgroundColor||'#888';
  el.style.background='transparent';
  const arrow='M0 30 H60 V10 L100 50 L60 90 V70 H0 Z';
  const shapes={
   'arrow-right':'<path d="'+arrow+'"/>',
   'arrow-left':'<path d="'+arrow+'" transform="rotate(180 50 50)"/>',
   'arrow-down':'<path d="'+arrow+'" transform="rotate(90 50 50)"/>',
   'arrow-up':'<path d="'+arrow+'" transform="rotate(-90 50 50)"/>',
   'ellipse':'<ellipse cx="50" cy="50" rx="50" ry="50"/>',
   'diamond':'<path d="M50 0 100 50 50 100 0 50Z"/>'
  };
  el.innerHTML='<svg viewBox="0 0 100 100" preserveAspectRatio="none" fill="'+fill+'" aria-hidden="true">'+(shapes[kind]||'<rect width="100" height="100"/>')+'</svg>';
}
let markerId=0;
function connector(el){
  const host=el.parentElement;
  const w=host.offsetWidth,h=host.offsetHeight;
  const n=a=>parseFloat(el.getAttribute(a));
  const x1=n('x1'),y1=n('y1'),x2=n('x2'),y2=n('y2');
  const route=el.getAttribute('route')||'straight';
  let pts=[[x1,y1],[x2,y2]];
  if(route==='hv')pts=[[x1,y1],[x2,y1],[x2,y2]];
  if(route==='vh')pts=[[x1,y1],[x1,y2],[x2,y2]];
  if(route==='elbow'){const mx=(x1+x2)/2;pts=[[x1,y1],[mx,y1],[mx,y2],[x2,y2]];}
  const color=el.style.color||'#4a5566';
  const sw=parseFloat(el.style.borderWidth)||2;
  const dashed=(el.style.borderStyle||'').includes('dash');
  const head=el.getAttribute('head')||'end';
  const id='m'+(markerId++);
  const svg=document.createElementNS(NS,'svg');
  svg.setAttribute('width',w);svg.setAttribute('height',h);
  svg.style.cssText='position:absolute;left:0;top:0;overflow:visible;pointer-events:none';
  svg.innerHTML='<defs><marker id="'+id+'" markerWidth="4" markerHeight="4" refX="4" refY="2" orient="auto-start-reverse" markerUnits="strokeWidth"><path d="M0 0 4 2 0 4Z" fill="'+color+'"/></marker></defs>'+
    '<polyline points="'+pts.map(p=>p.join(',')).join(' ')+'" fill="none" stroke="'+color+'" stroke-width="'+sw+'" stroke-linecap="round" stroke-linejoin="round"'+
    (dashed?' stroke-dasharray="'+(sw*3)+' '+(sw*2.5)+'"':'')+
    (head==='end'||head==='both'?' marker-end="url(#'+id+')"':'')+
    (head==='both'?' marker-start="url(#'+id+')"':'')+'/>';
  el.replaceWith(svg);
}
const slides=[...document.querySelectorAll('#canvas>section')];
const notes=document.getElementById('notes'),bar=document.getElementById('bar');
let cur=0;
function show(i){
  cur=Math.max(0,Math.min(slides.length-1,i));
  slides.forEach((s,k)=>s.classList.toggle('on',k===cur));
  const s=slides[cur];
  s.querySelectorAll('x-icon').forEach(icon);
  s.querySelectorAll('x-shape').forEach(shape);
  s.querySelectorAll('x-connector').forEach(connector);
  s.querySelectorAll('table').forEach(t=>{
    const c=[...t.querySelectorAll('th,td')].find(x=>x.style.padding);
    if(c)t.querySelectorAll('th,td').forEach(x=>{x.style.padding=c.style.padding;});
  });
  const a=s.querySelector('aside');
  notes.textContent=a?a.textContent.trim():'';
  bar.textContent=(cur+1)+' / '+slides.length+'  ·  ← → to move · N notes · F full screen';
  history.replaceState(null,'','#'+(cur+1));
}
function fit(){
  const stage=document.getElementById('stage');
  const k=Math.min(stage.clientWidth/1920,stage.clientHeight/1080);
  document.getElementById('canvas').style.transform='scale('+k+')';
}
addEventListener('resize',fit);
addEventListener('keydown',e=>{
  if(['ArrowRight','PageDown',' '].includes(e.key)){show(cur+1);e.preventDefault();}
  else if(['ArrowLeft','PageUp'].includes(e.key)){show(cur-1);e.preventDefault();}
  else if(e.key==='Home')show(0);
  else if(e.key==='End')show(slides.length-1);
  else if(e.key==='n'||e.key==='N'){document.body.classList.toggle('notes');fit();}
  else if(e.key==='f'||e.key==='F'){document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();}
});
document.getElementById('stage').addEventListener('click',e=>show(cur+(e.clientX<innerWidth/3?-1:1)));
fit();
show((parseInt(location.hash.slice(1),10)||1)-1);
})();
"""


def build_viewer(deck: dict, slides: list[tuple[str, str]]) -> str:
    families = "&".join(
        face["href"].split("?", 1)[1].replace("&display=swap", "")
        for face in deck.get("faces", {}).values()
        if "href" in face
    )
    font_link = (
        f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{families}&display=swap">'
        if families
        else ""
    )
    body = "\n".join(source for _, source in slides)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(deck['title'])}</title>
<!-- Generated by build.py from slides/*.html; edit the sources, then rebuild. -->
{font_link}
<style>{VIEWER_CSS}</style>
</head>
<body>
<div id="stage"><div id="canvas">
{body}
</div></div>
<div id="notes"></div>
<div id="bar"></div>
<script>{VIEWER_JS}</script>
</body>
</html>
"""


def main() -> None:
    deck, slides = _load()
    (HERE / "index.html").write_text(build_viewer(deck, slides), encoding="utf-8")
    (HERE / "TRANSCRIPT.md").write_text(build_transcript(deck, slides), encoding="utf-8")
    print(f"built {len(slides)} slides -> index.html, TRANSCRIPT.md")


if __name__ == "__main__":
    main()
