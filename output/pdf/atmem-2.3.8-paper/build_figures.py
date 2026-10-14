"""Rebuild original vector figures and descriptive statistics from frozen counts."""
from pathlib import Path
import json
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

ROOT = Path(__file__).resolve().parent
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "pdf.fonttype": 42, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.facecolor": "white"})
NAVY, TEAL, ORANGE, GRAY = "#17324d", "#087f8c", "#c46b24", "#667481"

def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

def box(ax, x, y, w, h, text, color=TEAL, fs=10):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.015",
                              linewidth=1.3, edgecolor=color, facecolor="#f3f7fa"))
    ax.text(x+w/2, y+h/2, text, ha="center", va="center", fontsize=fs, color=NAVY)

def arrow(ax, a, b, color=GRAY):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=12,
                                lw=1.4, color=color))

fig, ax = plt.subplots(figsize=(11.5, 6.6))
ax.set(xlim=(0, 12), ylim=(0, 7.0)); ax.axis("off")
ax.text(.1, 6.65, "2.3.7: governed records and execution continuity", color=NAVY, weight="bold", fontsize=13)
old = [(0.1,"Canonical records\n+ retained episodes"), (3.1,"FTS / graph /\nsemantic paths"),
       (6.1,"Eligible record set\n+ bounded context"), (9.1,"Scope + generation\nchecks; audit receipt")]
for x,t in old: box(ax,x,5.3,2.65,.95,t,GRAY)
for x,_ in old[:-1]: arrow(ax,(x+2.7,5.775),(x+2.95,5.775))
ax.text(.1, 4.72, "2.3.8: source evidence, explicit obligations, and verified delivery", color=NAVY, weight="bold", fontsize=13)
new=[(.1,"Immutable source\n+ exact ranges"),(3.1,"Typed evidence views\n+ formation loss ledger"),
     (6.1,"Obligation planning\n+ independent pools"),(9.1,"Bounded neighbours\n+ complete episodes")]
for x,t in new: box(ax,x,3.35,2.65,1.02,t)
for x,_ in new[:-1]: arrow(ax,(x+2.7,3.86),(x+2.95,3.86))
box(ax,9.1,1.8,2.65,1.02,"Coverage-aware packing\n+ sufficiency decision")
arrow(ax,(10.425,3.3),(10.425,2.85))
box(ax,5.2,1.8,3.25,1.02,"Governance: authorize, reload,\nvalidate scope / lifecycle / bytes")
arrow(ax,(9.05,2.31),(8.5,2.31))
box(ax,.1,1.8,4.25,1.02,"Context package, source IDs, audit receipt\nHost decides whether to invoke\nmodel / tools",fs=9.5)
arrow(ax,(5.15,2.31),(4.4,2.31))
ax.text(.1,.91,"Inherited: scoped authority, encrypted storage support, audit chain, continuity and checkpoint API",fontsize=10,color=GRAY)
ax.text(.1,.42,"Added: evidence obligations and loss accounting; record-to-audit commitments for AGMI verification",fontsize=10,color=TEAL)
save(fig,"architecture")

fig, axs=plt.subplots(1,2,figsize=(11,4.1),gridspec_kw={"width_ratios":[1.25,1]})
names=["No retrieval","AtMem context","Verified evidence"]
counts=[1,5,19]
colors=[GRAY,TEAL,ORANGE]
y=np.arange(len(names))
axs[0].barh(y,np.array(counts)/23*100,color=colors,height=.58)
axs[0].set_yticks(y,names); axs[0].invert_yaxis(); axs[0].set_xlim(0,100)
axs[0].set_xlabel("Questions correct (%)"); axs[0].grid(axis="x",alpha=.18); axs[0].set_axisbelow(True)
for yi,k in zip(y,counts): axs[0].text(k/23*100+1.2,yi,f"{k}/23",va="center",fontsize=9)
axs[0].annotate("14-question evidence-delivery gap",xy=(19/23*100,2),xytext=(42,1.45),
                arrowprops={"arrowstyle":"->","color":ORANGE},fontsize=9,color=ORANGE)
axs[0].set_title("LongMemEval-V2 evidence-delivery diagnostic",loc="left",fontsize=11,weight="bold")

outcomes=[9,21]
axs[1].bar(["Passed","Not passed"],np.array(outcomes)/30*100,color=[TEAL,"#d9e0e5"],width=.62)
axs[1].set_ylim(0,100); axs[1].set_ylabel("Tasks (%)"); axs[1].grid(axis="y",alpha=.18); axs[1].set_axisbelow(True)
for xi,k in enumerate(outcomes): axs[1].text(xi,k/30*100+2,f"{k}/30",ha="center",fontsize=9)
axs[1].set_title("DolphinBench task-outcome diagnostic",loc="left",fontsize=11,weight="bold")
fig.text(.02,.01,"Inspected partitions. These counts diagnose the system and do not estimate held-out generalization.",fontsize=9,color=GRAY)
fig.tight_layout(rect=(0,.07,1,1)); save(fig,"results")

fig, ax=plt.subplots(figsize=(10.5,3.6))
vals=np.array([[0]*9,[0]*8+[1],[1]*8+[0],[1]*9])
from matplotlib.colors import ListedColormap
ax.imshow(vals,cmap=ListedColormap(["#eef1f4",TEAL]),vmin=0,vmax=1,aspect="auto")
ax.set_yticks(range(4),["2.3.7 | chain","2.3.7 | external checkpoint","2.3.8 | chain","2.3.8 | external checkpoint"])
ax.set_xticks(range(9),["T1\nEdit","T2\nTruncate","T3\nDelete","T4\nReorder","T5\nForge","T6\nCross replay","T7\nOld replay","T8\nMetadata","T9\nSnapshot"])
ax.tick_params(length=0)
for i in range(4):
    for j in range(9): ax.text(j,i,"R" if vals[i,j] else "A",ha="center",va="center",color="white" if vals[i,j] else GRAY,weight="bold")
ax.set_title("AGMI 0.6.3 | R = reported by audit; A = accepted",loc="left",weight="bold",pad=14)
fig.text(.03,.01,"2.3.8: third-party replication by the AGMI maintainer from the PyPI wheel. T9 requires a trusted external checkpoint.",fontsize=9,color=GRAY)
fig.tight_layout(rect=(0,.08,1,1)); save(fig,"integrity")

fig, ax=plt.subplots(figsize=(10.5,3.2))
ax.set(xlim=(0,12),ylim=(0,3.5));ax.axis("off")
labels=["Task request\nrecipient, date,\noutcome","Obligations\nwhat must be\nsupported","Source spans\ntrigger, action,\nresult","Packed episode\ncomplete, contiguous"]
for i,t in enumerate(labels): box(ax,.12+i*3,1.5,2.6,1.15,t,fs=10)
for i in range(3): arrow(ax,(2.8+i*3,2.07),(3.05+i*3,2.07))
ax.text(.15,.88,"Missing one required span",weight="bold",color=ORANGE)
arrow(ax,(3.9,1.45),(3.9,.55),ORANGE)
ax.text(4.15,.52,"partial / named missing obligation -> host gate blocks model and tools",va="center",fontsize=10,color=NAVY)
ax.text(.15,3.05,"Illustrative mechanism: preserve the evidence needed for an action",color=NAVY,weight="bold",fontsize=12)
save(fig,"evidence_flow")

def mcnemar_possible(a,b,n):
    rows=[]
    for overlap in range(max(0,a+b-n),min(a,b)+1):
        wins,losses=a-overlap,b-overlap
        d=wins+losses
        p=min(1.,2*sum(math.comb(d,i) for i in range(min(wins,losses)+1))/2**d) if d else 1.
        rows.append({"overlap":overlap,"atmem_only":wins,"other_only":losses,"two_sided_p":p})
    return rows
stats={"longmem_atmem_mem0":mcnemar_possible(5,1,23),
       "longmem_atmem_agentrunbook":mcnemar_possible(5,4,23),
       "dolphin_atmem_mem0":mcnemar_possible(9,7,30)}
(ROOT/"derived-statistics.json").write_text(json.dumps(stats,indent=2)+"\n")
print(json.dumps({k:{"min_p":min(x["two_sided_p"] for x in v),"max_p":max(x["two_sided_p"] for x in v)} for k,v in stats.items()},indent=2))
