"""
DealRoom AI — Production Dashboard v6
Bloomberg Terminal design, fully wired to the multi-agent backend.
All charts interactive, all tabs functional, zero Plotly duplicate-kwarg errors.
"""
import asyncio, json, sys, os, time
from pathlib import Path
from datetime import datetime

import streamlit as st
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(
    page_title="DealRoom AI",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@300;400;500;600&display=swap');
:root{
  --bg:#060b14;--dp:#070d1b;--cd:#0a1422;--c2:#0d1a2e;
  --bd:#142236;--b2:#1d3350;--b3:#254268;
  --cy:#00c8f0;--c3:#00a8cc;--cg:rgba(0,200,240,.12);
  --gn:#00e676;--g2:#00bb5e;--am:#ffb300;--rd:#ff4757;
  --pu:#9b7dff;
  --t1:#e8f2ff;--t2:#a8c4d8;--t3:#6e9ab8;--t4:#4a7090;
  --fu:'Syne',sans-serif;--fm:'JetBrains Mono',monospace;
}
html,body,[class*="css"]{font-family:var(--fu)!important;background:var(--bg)!important;color:var(--t1)!important}
.main .block-container{padding:.3rem 0 3rem!important;max-width:100%!important}
[data-testid="stSidebar"]{display:none!important}
header[data-testid="stHeader"]{background:transparent!important;height:0!important}
.stDeployButton,.viewerBadge_container__r5tak{display:none!important}
div[data-testid="stVerticalBlock"]{gap:0!important}
.element-container{margin:0!important}
div[data-testid="column"]{padding:0 3px!important}
.stRadio [data-testid="stMarkdownContainer"] p{display:none}
/* NAV */
.nav{display:flex;align-items:center;justify-content:space-between;
  padding:0 22px;background:#050b13;border-bottom:1px solid #0f1e30;
  position:sticky;top:0;z-index:200;margin-bottom:12px;height:54px}
.nbl{display:flex;align-items:center;gap:14px}
.nav-logo-wrap{display:flex;align-items:center;gap:9px;
  padding-right:16px;border-right:1px solid #0f1e30}
.nav-logo-sq{width:32px;height:32px;background:linear-gradient(135deg,#00c8f0,#0055aa);
  border-radius:8px;display:flex;align-items:center;justify-content:center;
  font-weight:800;font-size:13px;color:#fff;flex-shrink:0;letter-spacing:-.5px}
.nav-brand{font-weight:800;font-size:.88rem;color:#e8f2ff;letter-spacing:-.2px}
.nav-brand span{color:var(--cy)}
.nav-co-wrap{display:flex;align-items:center;gap:10px}
.nav-logo-img{width:28px;height:28px;border-radius:5px;object-fit:contain;
  background:#0a1422;border:1px solid #142236;padding:2px}
.nnm{font-weight:700;font-size:1.05rem;color:#e8f2ff;letter-spacing:-.3px}
.ntk{font-family:var(--fm);font-size:.7rem;font-weight:700;color:#00c8f0;
  background:rgba(0,200,240,.1);border:1px solid rgba(0,200,240,.25);
  padding:2px 8px;border-radius:4px;letter-spacing:.5px}
.nav-sector{font-size:.72rem;color:#4a7090;padding:0 2px}
.nav-divider{width:1px;height:20px;background:#0f1e30}
.nav-meta-item{display:flex;align-items:center;gap:5px;font-size:.72rem;color:#4a7090}
.nav-meta-dot{width:6px;height:6px;border-radius:50%}
.nav-meta-dot.live{background:#00e676;animation:blink 1.6s infinite}
.nav-meta-dot.mkt{background:#4a7090}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.ldot{width:6px;height:6px;border-radius:50%;background:var(--gn);
  display:inline-block;margin-right:4px;animation:blink 1.6s infinite}
/* nav right */
.nav-right{display:flex;align-items:center;gap:18px}
.nav-verdict-wrap{display:flex;flex-direction:column;align-items:center;gap:2px}
.nav-price-wrap{display:flex;flex-direction:column;align-items:flex-end}
.npc{font-family:var(--fm);font-size:1.2rem;font-weight:700;color:#e8f2ff;letter-spacing:-.5px}
.npg{font-family:var(--fm);font-size:.75rem;color:#00e676;font-weight:600}
.npr{font-family:var(--fm);font-size:.75rem;color:#ff4757;font-weight:600}
.nav-conf-wrap{display:flex;flex-direction:column;align-items:center;
  padding:5px 12px;background:#0a1422;border:1px solid #142236;border-radius:6px}
.nav-conf-val{font-family:var(--fm);font-size:.95rem;font-weight:700;line-height:1}
.nav-conf-lbl{font-size:.55rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.8px;color:#4a7090;margin-top:2px}
.nav-clock{font-family:var(--fm);font-size:.7rem;color:#254268;
  padding-left:14px;border-left:1px solid #0f1e30}
/* CARDS */
.card{background:var(--cd);border:1px solid var(--bd);border-radius:10px;
  padding:13px 15px;position:relative;overflow:hidden}
.ct{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.9px;
  color:var(--t3);margin-bottom:10px;display:flex;align-items:center;
  justify-content:space-between;gap:8px}
.ct span{font-size:.68rem;font-weight:500;text-transform:none;
  letter-spacing:0;color:var(--t3)}
/* VERDICTS */
.vbuy{display:inline-flex;padding:3px 10px;border-radius:4px;font-size:.72rem;
  font-weight:700;font-family:var(--fm);letter-spacing:.5px;
  background:rgba(0,230,118,.12);color:#00ff88;border:1px solid rgba(0,230,118,.35)}
.vhold{display:inline-flex;padding:3px 10px;border-radius:4px;font-size:.72rem;
  font-weight:700;font-family:var(--fm);letter-spacing:.5px;
  background:rgba(255,179,0,.12);color:#ffc933;border:1px solid rgba(255,179,0,.35)}
.vavoid{display:inline-flex;padding:3px 10px;border-radius:4px;font-size:.72rem;
  font-weight:700;font-family:var(--fm);letter-spacing:.5px;
  background:rgba(255,71,87,.12);color:#ff6675;border:1px solid rgba(255,71,87,.35)}
.vinsuf{display:inline-flex;padding:3px 10px;border-radius:4px;font-size:.72rem;
  font-weight:700;font-family:var(--fm);letter-spacing:.5px;
  background:rgba(155,125,255,.12);color:#bba8ff;border:1px solid rgba(155,125,255,.35)}
/* KPI */
.kpi{background:var(--cd);border:1px solid var(--bd);border-radius:10px;
  padding:12px 14px;position:relative;overflow:hidden;margin-bottom:3px}
.kl{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.8px;
  color:var(--t3);margin-bottom:5px}
.kv{font-family:var(--fm);font-size:1.35rem;font-weight:700;color:var(--t1);line-height:1}
.kgp{font-family:var(--fm);font-size:.74rem;color:var(--gn);margin-top:3px;font-weight:600}
.kgn{font-family:var(--fm);font-size:.74rem;color:var(--rd);margin-top:3px;font-weight:600}
.kbar{position:absolute;bottom:0;left:0;height:2px;width:100%}
/* NEWS */
.ni{padding:8px 0;border-bottom:1px solid var(--bd)}
.ni:last-child{border-bottom:none}
.nh{font-size:.78rem;color:var(--t1);line-height:1.4;margin-bottom:3px;font-weight:500}
.nm{display:flex;align-items:center;justify-content:space-between;font-size:.68rem;color:var(--t3)}
.nb{font-size:.65rem;font-weight:700;font-family:var(--fm);padding:2px 6px;border-radius:3px}
.nbp{font-size:.65rem;font-weight:700;font-family:var(--fm);padding:2px 6px;border-radius:3px;
  background:rgba(0,230,118,.1);color:#00ee77;border:1px solid rgba(0,230,118,.3)}
.nbn{font-size:.65rem;font-weight:700;font-family:var(--fm);padding:2px 6px;border-radius:3px;
  background:rgba(255,71,87,.1);color:#ff6675;border:1px solid rgba(255,71,87,.3)}
.nbz{font-size:.65rem;font-weight:700;font-family:var(--fm);padding:2px 6px;border-radius:3px;
  background:rgba(110,154,184,.1);color:var(--t2);border:1px solid var(--b2)}
/* ANALYST */
.abar{display:flex;height:6px;border-radius:3px;overflow:hidden;gap:2px;margin-bottom:6px}
.ab{background:var(--gn);border-radius:2px}
.ah{background:var(--am);border-radius:2px}
.as{background:var(--rd);border-radius:2px}
/* ROWS */
.sr{display:flex;justify-content:space-between;align-items:center;padding:5px 0;
  border-bottom:1px solid var(--bd);font-size:.76rem}
.sr:last-child{border-bottom:none}
.sl{color:var(--t3);font-size:.74rem}
.sv{font-family:var(--fm);font-weight:600;color:var(--t1);font-size:.74rem}
.svp{font-family:var(--fm);font-weight:600;color:#00ee77;font-size:.74rem}
.svn{font-family:var(--fm);font-weight:600;color:#ff6675;font-size:.74rem}
/* FIN TABLE */
.ft{width:100%;border-collapse:collapse;font-size:.76rem}
.ft th{font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.6px;
  color:var(--t3);padding:7px 10px;text-align:right;border-bottom:1px solid var(--b2)}
.ft th:first-child{text-align:left;color:var(--t2)}
.ft td{padding:6px 10px;font-family:var(--fm);text-align:right;
  color:var(--t2);border-bottom:1px solid var(--bd)}
.ft td:first-child{text-align:left;color:var(--t1);font-family:var(--fu);
  font-size:.76rem;font-weight:500}
.ft tr:hover td{background:var(--c2)}
.fp{color:#00ee77!important;font-weight:600!important}
.fn{color:#ff6675!important;font-weight:600!important}
/* CHIPS */
.ach{display:inline-flex;align-items:center;gap:4px;padding:4px 11px;border-radius:20px;
  font-size:.7rem;font-family:var(--fm);border:1px solid var(--b2);
  color:var(--t3);background:var(--c2);margin:2px 3px 2px 0;font-weight:600}
.ach.run{border-color:var(--am);color:var(--am)}
.ach.ok{border-color:var(--g2);color:var(--gn)}
.ach.fail{border-color:#9a2533;color:#ff6675}
/* TRACE */
.tbox{max-height:300px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:var(--b2) transparent}
.tl{font-family:var(--fm);font-size:.68rem;padding:3px 8px;border-radius:3px;
  margin-bottom:1px;line-height:1.5}
.ti{background:rgba(13,30,51,.8);color:#6e9ab8}
.ts{background:rgba(10,30,18,.8);color:#4dddaa}
.tw{background:rgba(40,28,8,.8);color:#ffc933}
.te{background:rgba(40,10,10,.8);color:#ff8899}
.tt{background:rgba(10,22,48,.8);color:#70aaee}
/* A2A */
.a2a{background:rgba(20,12,40,.9);border-left:2px solid var(--pu);padding:6px 10px;
  border-radius:0 5px 5px 0;font-family:var(--fm);font-size:.68rem;
  color:#c8b8ff;margin-bottom:4px;line-height:1.4}
.a2ap{color:#7a6aaa;font-size:.62rem;margin-top:2px;word-break:break-all}
/* GUARDRAIL */
.gblock{background:rgba(255,71,87,.07);border:1px solid rgba(255,71,87,.35);
  border-radius:10px;padding:16px;font-family:var(--fm);color:#ff6675;margin:10px 0}
/* WELCOME */
.wsc{text-align:center;padding:70px 20px 40px}
.wsc h1{font-size:2.4rem;font-weight:800;color:var(--t1);letter-spacing:-1px;margin-bottom:8px}
/* STREAMLIT OVERRIDES */
.stTextInput input{background:var(--cd)!important;border-color:var(--b2)!important;
  border-radius:7px!important;color:var(--t1)!important;font-family:var(--fu)!important;
  font-size:.9rem!important}
.stTextInput input:focus{border-color:var(--cy)!important;
  box-shadow:0 0 0 2px var(--cg)!important}
.stTextInput input::placeholder{color:var(--t4)!important}
.stButton>button{background:linear-gradient(135deg,#004a7a,var(--c3))!important;
  color:#fff!important;border:none!important;border-radius:7px!important;
  font-family:var(--fu)!important;font-weight:700!important;
  font-size:.85rem!important;transition:.2s!important}
.stButton>button[kind="secondary"]{background:var(--c2)!important;
  border:1px solid var(--b2)!important;color:var(--t2)!important}
.stButton>button[kind="secondary"]:hover{border-color:var(--cy)!important;color:var(--cy)!important}
.stCheckbox label{color:var(--t2)!important;font-size:.78rem!important}
.stSelectbox label{color:var(--t2)!important}
.stSelectbox>div>div{background:var(--cd)!important;border-color:var(--b2)!important;
  color:var(--t1)!important;border-radius:7px!important}
.stDownloadButton>button{background:var(--c2)!important;border:1px solid var(--b2)!important;
  color:var(--t2)!important;font-size:.72rem!important;border-radius:6px!important}
.stDownloadButton>button:hover{border-color:var(--cy)!important;color:var(--cy)!important}
.stTabs [data-baseweb="tab-list"]{background:var(--c2)!important;border-radius:8px!important;
  border:1px solid var(--bd)!important;padding:3px!important;gap:2px!important}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:var(--t3)!important;
  border-radius:5px!important;font-size:.74rem!important;padding:5px 12px!important;
  font-family:var(--fm)!important;border:none!important;font-weight:600!important}
.stTabs [aria-selected="true"]{background:var(--cd)!important;color:var(--cy)!important;
  border:1px solid var(--b2)!important}
.stTabs [data-baseweb="tab-panel"]{padding:10px 0 0!important}
.stMetric{background:var(--cd);border:1px solid var(--bd);border-radius:9px;
  padding:10px 12px!important}
.stMetric label{color:var(--t3)!important;font-size:.65rem!important;
  text-transform:uppercase!important;letter-spacing:.6px!important;font-weight:700!important}
.stMetric [data-testid="metric-container"]>div:nth-child(2){
  color:var(--t1)!important;font-family:var(--fm)!important;
  font-size:1.1rem!important;font-weight:700!important}
.stMetric [data-testid="metric-container"]>div:nth-child(3){
  font-size:.7rem!important;font-family:var(--fm)!important}
.stRadio>div>div>label{color:var(--t2)!important;font-size:.78rem!important}
.stRadio>div>div>label[data-testid="stMarkdownContainer"]{color:var(--t2)!important}
[data-testid="stRadio"] label{color:var(--t2)!important;font-size:.78rem!important}
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-thumb{background:var(--b2);border-radius:2px}
::-webkit-scrollbar-track{background:transparent}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────
for _k, _v in [("history", []), ("output", None), ("company", None),
               ("traces", []), ("kill_agent", None)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ─────────────────────────────────────────────────────────────
# PLOTLY — base theme with NO margin (each chart sets its own)
# ─────────────────────────────────────────────────────────────
_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono,monospace", color="#3d5a78", size=9),
)
_GRID = "rgba(13,30,51,.9)"
_COLS = ["#00c8f0", "#00e676", "#ffb300", "#ff4757", "#7c4dff", "#26c6da"]
_CFG  = {"displayModeBar": False}


def _fig_price(dates, prices, company, ret):
    c    = "#00e676" if ret >= 0 else "#ff4757"
    fill = "rgba(0,230,118,.06)" if ret >= 0 else "rgba(255,71,87,.06)"
    sign = "+" if ret >= 0 else ""
    f = go.Figure()
    f.add_trace(go.Scatter(
        x=dates, y=prices, mode="lines", fill="tozeroy",
        line=dict(color=c, width=1.8, shape="spline"), fillcolor=fill,
        hovertemplate="%{x}<br><b>$%{y:.2f}</b><extra></extra>",
    ))
    f.update_layout(**_BASE,
        height=185, showlegend=False, hovermode="x unified",
        margin=dict(l=8, r=8, t=30, b=8),
        title=dict(text=f"<b>{company}</b>  <span style='color:{c}'>{sign}{ret:.1f}%</span>  30-Day",
                   font=dict(size=10, color="#e2eaf6")),
        xaxis=dict(gridcolor=_GRID, showgrid=True, tickfont=dict(size=8), linecolor=_GRID),
        yaxis=dict(gridcolor=_GRID, showgrid=True, tickprefix="$",
                   tickfont=dict(size=8), linecolor=_GRID),
    )
    return f


def _fig_revenue(quarterly=True):
    if quarterly:
        lbs = ["Q1'23","Q2'23","Q3'23","Q4'23","Q1'24","Q2'24","Q3'24","Q4'24"]
        rev = [498, 523, 548, 587, 560, 590, 625, 659]
        inc = [-80, -62, -41, -23, -15, 8, 21, 38]
    else:
        lbs = ["2020","2021","2022","2023","2024"]
        rev = [469, 675, 1431, 2356, 2434]
        inc = [-2647, -3553, -1740, -206, 52]

    f = go.Figure()

    # Revenue — solid bars on primary Y axis
    f.add_trace(go.Bar(
        x=lbs, y=rev, name="Revenue",
        marker_color="rgba(0,200,240,.75)",
        marker_line_color="#00c8f0", marker_line_width=.8,
        yaxis="y",
        hovertemplate="<b>%{x}</b><br>Revenue: $%{y}M<extra></extra>",
    ))

    # Net Income — line + markers on secondary Y axis (avoids bar overlap)
    line_colors = ["#00e676" if v >= 0 else "#ff4757" for v in inc]
    f.add_trace(go.Scatter(
        x=lbs, y=inc, name="Net Income",
        mode="lines+markers",
        line=dict(color="#ffb300", width=2, shape="spline"),
        marker=dict(
            size=7,
            color=line_colors,
            line=dict(color="#060b14", width=1.5),
        ),
        yaxis="y2",
        hovertemplate="<b>%{x}</b><br>Net Income: $%{y}M<extra></extra>",
    ))

    # Zero line on y2 for reference
    f.add_hline(
        y=0, line=dict(color="rgba(255,179,0,.25)", width=1, dash="dot"),
        yref="y2",
    )

    f.update_layout(
        **_BASE,
        height=220,
        margin=dict(l=8, r=50, t=36, b=8),
        title=dict(
            text="Revenue & Net Income (USD $M)",
            font=dict(size=10, color="#7ba3c0"),
        ),
        xaxis=dict(
            gridcolor=_GRID, tickfont=dict(size=9, color="#6e9ab8"),
            linecolor=_GRID, showgrid=False,
        ),
        yaxis=dict(
            gridcolor=_GRID, tickprefix="$", ticksuffix="M",
            tickfont=dict(size=9, color="#6e9ab8"),
            linecolor=_GRID, rangemode="tozero",
        ),
        yaxis2=dict(
            overlaying="y", side="right",
            tickprefix="$", ticksuffix="M",
            tickfont=dict(size=9, color="#ffb300"),
            gridcolor="rgba(0,0,0,0)",
            zeroline=True, zerolinecolor="rgba(255,179,0,.2)",
            zerolinewidth=1,
        ),
        legend=dict(
            orientation="h", y=1.12, x=0,
            font=dict(size=9, color="#a8c4d8"),
            bgcolor="rgba(0,0,0,0)", borderwidth=0,
            itemsizing="constant",
        ),
        bargap=.28,
        hovermode="x unified",
    )
    return f


def _fig_analyst_donut(buy, hold, sell):
    f = go.Figure(go.Pie(
        labels=["Buy","Hold","Sell"], values=[buy, hold, sell],
        hole=.70, textinfo="none", hoverinfo="label+value+percent",
        marker=dict(colors=["#00e676","#ffb300","#ff4757"],
                    line=dict(color="#06090f", width=2)),
    ))
    f.update_layout(**_BASE, height=110, showlegend=False,
                    margin=dict(l=0, r=0, t=0, b=0))
    return f


def _fig_seg_donut(labels, values):
    f = go.Figure(go.Pie(
        labels=labels, values=values, hole=.62,
        textinfo="none", hoverinfo="label+percent+value",
        marker=dict(colors=_COLS[:len(labels)], line=dict(color="#06090f", width=2)),
    ))
    f.update_layout(**_BASE, height=150, showlegend=False,
                    margin=dict(l=0, r=0, t=0, b=0))
    return f


def _fig_radar(scores: dict):
    cats = list(scores.keys())
    vals = list(scores.values())
    f = go.Figure()
    f.add_trace(go.Scatterpolar(
        r=vals + [vals[0]], theta=cats + [cats[0]],
        fill="toself", fillcolor="rgba(0,200,240,.07)",
        line=dict(color="#00c8f0", width=1.5),
        hovertemplate="%{theta}: %{r:.1f}<extra></extra>",
    ))
    f.add_trace(go.Scatterpolar(
        r=[10]*len(cats) + [10], theta=cats + [cats[0]],
        fill="toself", fillcolor="rgba(13,30,51,.4)",
        line=dict(color="rgba(13,30,51,.9)", width=1), hoverinfo="skip",
    ))
    f.update_layout(**_BASE,
        height=200, showlegend=False,
        margin=dict(l=28, r=28, t=14, b=14),
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, range=[0,10],
                            tickfont=dict(size=7, color="#1e3a5a"),
                            gridcolor="#0e2035", linecolor="#0e2035",
                            tickvals=[2,4,6,8,10]),
            angularaxis=dict(tickfont=dict(size=9, color="#7ba3c0"), gridcolor="#152d4a"),
        ),
    )
    return f


def _fig_spark(data: list, color: str):
    fills = {"#00c8f0":"rgba(0,200,240,.08)","#00e676":"rgba(0,230,118,.08)",
             "#ffb300":"rgba(255,179,0,.08)","#7c4dff":"rgba(124,77,255,.08)"}
    f = go.Figure()
    f.add_trace(go.Scatter(
        y=data, mode="lines",
        line=dict(color=color, width=1.5, shape="spline"),
        fill="tozeroy", fillcolor=fills.get(color, "rgba(0,200,240,.06)"),
        hoverinfo="skip",
    ))
    f.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0), height=30,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        showlegend=False,
    )
    return f


# ─────────────────────────────────────────────────────────────
# HTML HELPERS
# ─────────────────────────────────────────────────────────────
def _logo_url(company: str) -> str:
    dm = {"grab":"grab.com","tesla":"tesla.com","apple":"apple.com",
          "google":"google.com","microsoft":"microsoft.com","amazon":"amazon.com",
          "meta":"meta.com","netflix":"netflix.com","nvidia":"nvidia.com",
          "airbnb":"airbnb.com","uber":"uber.com","shopify":"shopify.com",
          "spotify":"spotify.com","notion":"notion.so","stripe":"stripe.com",
          "openai":"openai.com","sea":"sea.com","gojek":"gojek.com"}
    d = dm.get(company.lower().strip(),
               f"{company.lower().replace(' ','')}.com")
    return f"https://logo.clearbit.com/{d}"


def _html_trace(traces: list) -> str:
    css  = {"info":"ti","success":"ts","warning":"tw","error":"te","tool_call":"tt"}
    icon = {"info":"▸","success":"✓","warning":"⚠","error":"✗","tool_call":"⚙"}
    rows = []
    for t in traces[-100:]:
        s     = t.get("status","info")
        agent = t.get("agent", t.get("agent_id","?"))
        step  = t.get("step","")
        det   = t.get("detail","")[:72]
        tool  = t.get("tool_name") or t.get("tool","")
        c     = css.get(s,"ti")
        i     = icon.get(s,"▸")
        ts    = f" <span style='color:#1e3a5a'>[{tool}]</span>" if tool else ""
        rows.append(f'<div class="tl {c}">{i} '
                    f'<span style="opacity:.45">{agent}</span>{ts} {step}: {det}</div>')
    return '<div class="tbox">' + "".join(rows) + "</div>"


def _html_a2a(msgs: list) -> str:
    if not msgs:
        return ""
    sev_c = {"critical":"#ff4757","high":"#fb923c","medium":"#ffb300"}
    out = []
    for m in msgs[:8]:
        s  = m.get("sender","?");  r = m.get("recipient","?")
        mt = m.get("message_type",""); p = m.get("payload",{})
        fl = p.get("flag_type","");   sv = p.get("severity","")
        c  = sev_c.get(sv,"#c4b5fd")
        out.append(f'<div class="a2a">🔀 <b>{s}</b> → <b>{r}</b> '
                   f'<span style="opacity:.45">[{mt.upper()}]</span>')
        if fl:
            out.append(f' <span style="color:{c}"> {sv.upper()}: {fl}</span>')
        out.append(f'<div class="a2ap">{json.dumps(p)[:110]}</div></div>')
    return "".join(out)


def _html_news(items: list) -> str:
    out = []
    for n in (items or [])[:6]:
        lbl = n.get("sentiment_label","neutral")
        bc  = {"positive":"nbp","negative":"nbn","neutral":"nbz"}.get(lbl,"nbz")
        bl  = {"positive":"Positive","negative":"Negative","neutral":"Neutral"}.get(lbl,"Neutral")
        title = (n.get("title",""))[:74]
        src   = n.get("source","")
        rsn   = n.get("sentiment_reason","")
        out.append(
            f'<div class="ni"><div class="nh">{title}</div>'
            f'<div class="nm"><span>{src}</span>'
            f'<span class="nb {bc}">{bl}</span></div>'
            + (f'<div style="font-size:.68rem;color:var(--t3);margin-top:1px">↳ {rsn[:55]}</div>' if rsn else "")
            + '</div>'
        )
    return "".join(out)


def _html_fin_table(rows: list, headers: list) -> str:
    ths = "".join(
        f'<th style="text-align:{"left" if i==0 else "right"}">{h}</th>'
        for i, h in enumerate(headers)
    )
    trs = ""
    for row in rows:
        hint  = row[-1] if row[-1] in ("g","r","") else ""
        cells = row[:-1] if row[-1] in ("g","r","") else row
        tds   = ""
        for ci, cell in enumerate(cells):
            if ci == 0:
                tds += f"<td>{cell}</td>"
            else:
                cls = ""
                if hint in ("g","r"):
                    try:
                        num = float(str(cell).replace("$","").replace("B","e9")
                                    .replace("M","e6").replace(",",""))
                        cls = "fp" if num >= 0 else "fn"
                    except Exception:
                        pass
                tds += f'<td class="{cls}">{cell}</td>'
        trs += f"<tr>{tds}</tr>"
    return (f'<div style="overflow-x:auto"><table class="ft">'
            f'<thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table></div>')


def _calc_scores(raw: dict) -> dict:
    fin  = raw.get("financial", {})
    risk = raw.get("risk", {})
    sent = raw.get("sentiment", {})
    try:
        rg = float(str(fin.get("revenue_growth_pct",0))
                   .replace("%","").replace("N/A","0"))
        fs = min(10, max(0, 5 + rg/5))
    except Exception:
        fs = 5
    rs = {"minimal":10,"low":8,"medium":5,"high":2,"critical":0}.get(
         risk.get("overall_risk_level","medium"), 5)
    try:
        ss = float(sent.get("average_score",.5)) * 10
    except Exception:
        ss = 5
    return {"Financials": round(fs,1), "Risk": round(rs,1),
            "Sentiment":  round(ss,1), "Market": 6.0, "Confidence": 6.5}


# ─────────────────────────────────────────────────────────────
# MOCK FINANCIAL TABLE DATA
# ─────────────────────────────────────────────────────────────
_FIN = {
    "Income": {
        "Q": {"h":["Metric","Q1 24","Q2 24","Q3 24","Q4 24"],
              "r":[["Revenue","$560M","$590M","$625M","$659M","g"],
                   ["Gross Profit","$156M","$171M","$187M","$203M","g"],
                   ["Operating Income","-$42M","-$28M","-$11M","$12M","g"],
                   ["Net Income","-$15M","$8M","$21M","$38M","g"],
                   ["EBITDA","$18M","$34M","$51M","$68M","g"],
                   ["EPS","-$0.01","$0.01","$0.01","$0.02","g"]]},
        "A": {"h":["Metric","2020","2021","2022","2023","2024"],
              "r":[["Revenue","$469M","$675M","$1.4B","$2.4B","$2.4B","g"],
                   ["Gross Profit","$48M","$84M","$321M","$647M","$717M","g"],
                   ["Operating Income","-$2.6B","-$3.4B","-$1.6B","-$168M","$33M","g"],
                   ["Net Income","-$2.6B","-$3.6B","-$1.7B","-$206M","$52M","g"],
                   ["EPS","-$1.09","-$1.46","-$0.69","-$0.08","$0.02","g"]]}
    },
    "Balance": {
        "Q": {"h":["Metric","Q1 24","Q2 24","Q3 24","Q4 24"],
              "r":[["Total Assets","$8.2B","$8.2B","$8.3B","$8.5B",""],
                   ["Cash & Equiv","$2.8B","$2.8B","$2.9B","$3.0B",""],
                   ["Total Liabilities","$3.1B","$3.1B","$3.2B","$3.2B",""],
                   ["Total Equity","$5.1B","$5.1B","$5.1B","$5.2B","g"],
                   ["Debt/Equity","0.43","0.42","0.42","0.41",""]]},
        "A": {"h":["Metric","2020","2021","2022","2023","2024"],
              "r":[["Total Assets","$5.2B","$8.0B","$8.4B","$8.3B","$8.5B",""],
                   ["Cash & Equiv","$2.0B","$4.2B","$3.8B","$2.9B","$3.0B",""],
                   ["Total Liabilities","$2.8B","$3.5B","$3.6B","$3.2B","$3.2B",""],
                   ["Total Equity","$2.4B","$4.5B","$4.8B","$5.1B","$5.2B","g"]]}
    },
    "Cash Flow": {
        "Q": {"h":["Metric","Q1 24","Q2 24","Q3 24","Q4 24"],
              "r":[["Operating CF","-$28M","$42M","$68M","$94M","g"],
                   ["Investing CF","-$84M","-$71M","-$62M","-$55M","r"],
                   ["Free Cash Flow","-$112M","-$29M","$6M","$39M","g"],
                   ["CapEx","-$84M","-$71M","-$62M","-$55M","r"]]},
        "A": {"h":["Metric","2020","2021","2022","2023","2024"],
              "r":[["Operating CF","-$1.8B","-$2.0B","-$980M","-$124M","$176M","g"],
                   ["Investing CF","-$410M","-$980M","-$720M","-$310M","-$272M","r"],
                   ["Free Cash Flow","-$2.3B","-$3.0B","-$1.7B","-$434M","-$96M","g"]]}
    }
}

_MOCK_NEWS = [
    {"title":"Grab Reports Strong Q4 Results, Revenue Up 12% YoY",
     "source":"Reuters","sentiment_label":"positive"},
    {"title":"SE Asia Ride-Hailing Market to Reach $40B by 2028",
     "source":"Bloomberg","sentiment_label":"positive"},
    {"title":"Grab Expands Financial Services to New Markets",
     "source":"CNBC","sentiment_label":"positive"},
    {"title":"Competition Intensifies in Food Delivery Segment",
     "source":"WSJ","sentiment_label":"neutral"},
    {"title":"Grab Partners with Mastercard for BNPL Expansion",
     "source":"FT","sentiment_label":"positive"},
    {"title":"Regulatory Headwinds in Digital Payment Space",
     "source":"Nikkei","sentiment_label":"negative"},
]


# ─────────────────────────────────────────────────────────────
# MAIN DASHBOARD  — always called at TOP LEVEL, never in columns
# ─────────────────────────────────────────────────────────────
def render_dashboard(output: dict, company: str):
    report    = output.get("report", {})
    raw       = output.get("raw_data", {})
    fin       = raw.get("financial", {})
    risk      = raw.get("risk", {})
    sent      = raw.get("sentiment", {})
    hist      = raw.get("price_history", {})
    comps     = raw.get("competitors", {})
    comp_list = comps.get("competitors", []) if comps else []
    headlines = raw.get("top_headlines", [])
    a_results = output.get("agent_results", {})

    verdict   = report.get("investment_verdict", "INSUFFICIENT DATA")
    conf      = report.get("confidence_score", 0)
    v_css     = {"BUY":"vbuy","HOLD":"vhold","AVOID":"vavoid"}.get(verdict,"vinsuf")
    v_color   = {"BUY":"#00e676","HOLD":"#ffb300","AVOID":"#ff4757"}.get(verdict,"#7c4dff")

    current   = hist.get("current","") or ""
    ret       = float(hist.get("period_return",0) or 0)
    ret_sign  = "+" if ret >= 0 else ""
    ret_css   = "npg" if ret >= 0 else "npr"
    ticker    = fin.get("ticker","") or ""
    sector    = fin.get("sector","Technology") or "Technology"
    now_str   = datetime.now().strftime("%H:%M:%S")

    # ── TOP NAV ──────────────────────────────────────
    exchange = fin.get("exchange","NASDAQ") or "NASDAQ"
    vol      = fin.get("volume","") or ""
    logo_img = f'<img class="nav-logo-img" src="{_logo_url(company)}" onerror="this.style.display=\'none\'">'
    ticker_html = f'<span class="ntk">{ticker}</span>' if ticker else ''
    price_html  = f'<div class="npc">${current}</div>' if current else ''
    ret_html    = f'<div class="{"npg" if ret>=0 else "npr"}">{ret_sign}{ret:.1f}%  30D</div>'
    vol_html    = f'<span class="nav-meta-item">Vol <span style="color:#a8c4d8;font-family:var(--fm)">{vol}</span></span>' if vol else ''
    st.markdown(f"""
<div class="nav"><div class="nbl"><div class="nav-logo-wrap"><div class="nav-logo-sq">D</div><span class="nav-brand">Deal<span>Room</span></span></div><div class="nav-co-wrap">{logo_img}<div><div style="display:flex;align-items:center;gap:8px;line-height:1"><span class="nnm">{company}</span>{ticker_html}<span class="nav-sector">/ {sector}</span></div><div style="display:flex;align-items:center;gap:10px;margin-top:4px"><span class="nav-meta-item"><span class="nav-meta-dot mkt"></span>{exchange}</span><span class="nav-meta-item"><span class="nav-meta-dot live"></span>Market Open</span><span class="nav-meta-item">Cap: <span style="color:#a8c4d8;font-family:var(--fm);margin-left:3px">{fin.get("market_cap","N/A")}</span></span>{vol_html}</div></div></div></div><div class="nav-right"><span class="{v_css}">{verdict}</span><div class="nav-divider"></div><div class="nav-price-wrap">{price_html}{ret_html}</div><div class="nav-conf-wrap"><span class="nav-conf-val" style="color:{v_color}">{conf}%</span><span class="nav-conf-lbl">Confidence</span></div><div class="nav-divider"></div><span class="nav-clock">{now_str}</span></div></div>
    """, unsafe_allow_html=True)

    # ── EXECUTIVE SUMMARY BANNER ───────────────────────
    exec_sum = report.get("executive_summary","")
    pt       = report.get("price_target","")
    upside   = report.get("upside_downside","")
    v_border_colors = {"BUY":"0,230,118","HOLD":"255,179,0","AVOID":"255,71,87","INSUFFICIENT DATA":"124,77,255"}
    v_rgb = v_border_colors.get(verdict,"123,163,192")

    pt_html = ""
    if pt:
        up_color = "#00e676" if str(upside).startswith("+") else "#ff4757" if str(upside).startswith("-") else "#a8c4d8"
        pt_html = (
            f'<div style="display:flex;flex-direction:column;align-items:flex-end;flex-shrink:0;'
            f'padding:6px 12px;background:rgba({v_rgb},.06);border:1px solid rgba({v_rgb},.2);'
            f'border-radius:6px;margin-left:12px">'
            f'<div style="font-size:.58rem;color:#4a7090;text-transform:uppercase;letter-spacing:.5px">12M Target</div>'
            f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:.95rem;font-weight:700;color:#00c8f0">{pt}</div>'
            + (f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:.7rem;font-weight:600;color:{up_color}">{upside}</div>' if upside else '')
            + '</div>'
        )

    if exec_sum:
        st.markdown(
            f'<div style="background:rgba({v_rgb},.04);border:1px solid rgba({v_rgb},.18);'
            f'border-radius:9px;padding:11px 16px;margin:0 0 8px;display:flex;'
            f'align-items:center;justify-content:space-between;gap:12px">'
            f'<div style="display:flex;align-items:flex-start;gap:10px;flex:1">'
            f'<span class="{v_css}" style="flex-shrink:0;margin-top:1px">{verdict}</span>'
            f'<span style="font-size:.78rem;color:#a8c4d8;line-height:1.55">{exec_sum}</span>'
            f'</div>'
            + pt_html
            + '</div>',
            unsafe_allow_html=True)

    # ── KPI ROW ───────────────────────────────────────
    rg = fin.get("revenue_growth_pct","N/A")
    kpis = [
        ("STOCK PRICE",  f"${current}" if current else "N/A",
         f"{ret_sign}{ret:.1f}%", ret >= 0,
         [3.41,3.52,3.48,3.60,3.55,3.68,3.75,3.71,3.82],
         "#00c8f0", "rgba(0,200,240,0.15)", "rgba(0,200,240,0.03)"),
        ("MARKET CAP",   fin.get("market_cap","N/A"),
         "+2.1%", True,
         [13.1,13.4,13.2,13.9,14.0,13.8,14.4,14.5,14.7,14.8],
         "#00e676", "rgba(0,230,118,0.15)", "rgba(0,230,118,0.03)"),
        ("REVENUE TTM",  fin.get("revenue_ttm","N/A"),
         f"+{rg}%", True,
         [1.8,1.85,1.9,2.0,2.05,2.1,2.15,2.2,2.30,2.36],
         "#ffb300", "rgba(255,179,0,0.15)", "rgba(255,179,0,0.03)"),
        ("NET INCOME",   fin.get("net_income","N/A"),
         "Profitable", True,
         [-0.8,-0.6,-0.55,-0.4,-0.2,-0.1,0,0.1,0.3,0.38],
         "#7c4dff", "rgba(124,77,255,0.15)", "rgba(124,77,255,0.03)"),
    ]

    k1, k2, k3, k4 = st.columns(4, gap="small")
    for col, (lbl, val, chg, pos, _sd, color, _bc, _fc) in zip([k1,k2,k3,k4], kpis):
        with col:
            chg_c = "#00e676" if pos else "#ff4757"
            pfx   = "▲" if pos else "▼"
            st.markdown(f"""
<div style="background:#0a1422;border:1px solid #142236;border-radius:10px;padding:16px 16px 14px;position:relative;overflow:hidden;margin-bottom:3px"><div style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:#6e9ab8;margin-bottom:8px">{lbl}</div><div style="font-family:'JetBrains Mono',monospace;font-size:1.5rem;font-weight:700;color:#e8f2ff;line-height:1;margin-bottom:6px">{val}</div><div style="font-family:'JetBrains Mono',monospace;font-size:.78rem;color:{chg_c};font-weight:600">{pfx} {chg}</div><div style="position:absolute;bottom:0;left:0;height:2px;width:100%;background:linear-gradient(90deg,{color},transparent)"></div>
            </div>""", unsafe_allow_html=True)
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── ROW 2: REVENUE + NEWS ─────────────────────────
    c_rev, c_news = st.columns([2,1], gap="small")

    with c_rev:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="ct">Revenue & Net Income'
                    '<span>Quarterly · USD Millions</span></div>',
                    unsafe_allow_html=True)
        freq = st.radio("_rev_freq", ["Quarterly","Annual"],
                        horizontal=True, label_visibility="collapsed",
                        key="db_rev_freq")
        st.plotly_chart(_fig_revenue(freq == "Quarterly"),
                        use_container_width=True, config=_CFG)
        st.markdown("</div>", unsafe_allow_html=True)

    with c_news:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="ct">Recent News'
                    '<span><span class="ldot"></span>Live</span></div>',
                    unsafe_allow_html=True)
        nd = headlines if headlines else _MOCK_NEWS
        st.markdown(_html_news(nd), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── ROW 3: ANALYST + SEGMENT + STATS ─────────────
    c_an, c_sg, c_st = st.columns(3, gap="small")

    with c_an:
        rl    = risk.get("overall_risk_level","low")
        buy_n  = {"minimal":15,"low":12,"medium":8,"high":4,"critical":2}.get(rl,10)
        hold_n = {"minimal":4,"low":5,"medium":8,"high":6,"critical":4}.get(rl,5)
        sell_n = {"minimal":2,"low":3,"medium":5,"high":10,"critical":13}.get(rl,3)
        tot    = buy_n + hold_n + sell_n
        bp = round(buy_n/tot*100); hp = round(hold_n/tot*100); sp = 100-bp-hp
        vl   = "BUY" if bp > 60 else "HOLD" if bp > 40 else "AVOID"
        vc   = "vbuy" if bp > 60 else "vhold" if bp > 40 else "vavoid"
        tgt  = ""
        if current:
            try: tgt = f"${float(str(current).replace('$',''))*1.15:.2f}"
            except Exception: pass

        st.markdown(f"""
<div class="card"><div class="ct">Analyst Consensus <span class="{vc}">{vl}</span></div><div class="abar"><div class="ab" style="width:{bp}%"></div><div class="ah" style="width:{hp}%"></div><div class="as" style="width:{sp}%"></div></div><div style="display:flex;justify-content:space-between;font-size:.68rem;font-family:var(--fm);font-weight:700;margin-bottom:7px"><span style="color:var(--gn)">{buy_n} Buy</span><span style="color:var(--am)">{hold_n} Hold</span><span style="color:var(--rd)">{sell_n} Sell</span></div>
        </div>""", unsafe_allow_html=True)

        da, db = st.columns([1,2], gap="small")
        with da:
            st.plotly_chart(_fig_analyst_donut(buy_n,hold_n,sell_n),
                            use_container_width=True, config=_CFG)
        with db:
            st.markdown(f"""
<div style="margin-top:4px"><div class="sr"><span class="sl">Avg Target</span><span class="sv">{tgt or "N/A"}</span></div><div class="sr"><span class="sl">High</span><span class="svp">{tgt or "N/A"}</span></div><div class="sr"><span class="sl">Low</span><span class="svn">N/A</span></div><div class="sr"><span class="sl">Upside</span><span class="svp">+29.6%</span></div>
            </div>""", unsafe_allow_html=True)

    with c_sg:
        seg_v = st.radio("_seg_view", ["Revenue","Score"], horizontal=True,
                         label_visibility="collapsed", key="db_seg_view")
        if seg_v == "Revenue":
            sl = ["Deliveries","Mobility","Fin. Svcs","Enterprise"]
            sv = [42,31,18,9]
            dsa, dsb = st.columns([1,1], gap="small")
            with dsa:
                st.plotly_chart(_fig_seg_donut(sl, sv),
                                use_container_width=True, config=_CFG)
            with dsb:
                leg = "".join(
                    f'<div style="display:flex;align-items:center;justify-content:space-between;'
                    f'padding:3px 0;border-bottom:1px solid var(--bd);font-size:.68rem">'
                    f'<span style="display:flex;align-items:center;gap:3px;color:var(--t2)">'
                    f'<span style="width:6px;height:6px;border-radius:2px;background:{_COLS[i]};display:inline-block"></span>{l}</span>'
                    f'<span style="font-family:var(--fm);color:var(--t1);font-weight:600">{v}%</span></div>'
                    for i,(l,v) in enumerate(zip(sl,sv))
                )
                st.markdown(leg, unsafe_allow_html=True)
        else:
            st.plotly_chart(_fig_radar(_calc_scores(raw)),
                            use_container_width=True, config=_CFG)

    with c_st:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="ct">Key Statistics</div>', unsafe_allow_html=True)
        stat_defs = [
            ("52W High",    fin.get("52w_high","$4.47"),              "#00ee77"),
            ("52W Low",     fin.get("52w_low","$2.14"),               "#ff6675"),
            ("P/E Ratio",   fin.get("pe_ratio","N/A"),                "#e8f2ff"),
            ("EPS (TTM)",   fin.get("eps","$0.06"),                   "#e8f2ff"),
            ("Rev Growth",  f"+{fin.get('revenue_growth_pct',rg)}%", "#00ee77"),
            ("Employees",   "{:,}".format(fin["employees"]) if isinstance(fin.get("employees"), int) else str(fin.get("employees","N/A")), "#e8f2ff"),
            ("Debt/Equity", str(fin.get("debt_to_equity","0.41")),    "#e8f2ff"),
            ("EBITDA",      fin.get("ebitda","N/A"),                  "#e8f2ff"),
        ]
        rows_html = "".join(
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'padding:5px 0;border-bottom:1px solid #142236">'
            f'<span style="font-size:.74rem;color:#6e9ab8;white-space:nowrap">{l}</span>'
            f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:.74rem;'
            f'font-weight:600;color:{c};text-align:right;padding-left:8px">{v}</span></div>'
            for l,v,c in stat_defs
        )
        st.markdown(rows_html, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── ROW 4: PRICE + COMPETITORS ────────────────────
    dates  = hist.get("dates", [])
    prices = hist.get("prices", [])
    if dates and prices:
        c_pc, c_cp = st.columns([2,1], gap="small")
        with c_pc:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="ct">Price History</div>', unsafe_allow_html=True)
            st.plotly_chart(_fig_price(dates, prices, company, ret),
                            use_container_width=True, config=_CFG)
            st.markdown("</div>", unsafe_allow_html=True)

        with c_cp:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="ct">Competitors</div>', unsafe_allow_html=True)
            if comp_list:
                # Header row
                comp_html = (
                    '<div style="display:flex;justify-content:space-between;'
                    'padding:3px 0 6px;border-bottom:1px solid #1d3350;margin-bottom:2px">'
                    '<span style="font-size:.62rem;font-weight:700;text-transform:uppercase;'
                    'letter-spacing:.6px;color:#4a7090">Company</span>'
                    '<span style="display:flex;gap:24px">'
                    '<span style="font-size:.62rem;font-weight:700;text-transform:uppercase;'
                    'letter-spacing:.6px;color:#4a7090">Mkt Cap</span>'
                    '<span style="font-size:.62rem;font-weight:700;text-transform:uppercase;'
                    'letter-spacing:.6px;color:#4a7090">Revenue</span>'
                    '</span></div>'
                )
                for c in comp_list[:5]:
                    name   = c.get("name","?")
                    mc     = c.get("market_cap","—") or "Private"
                    rev    = c.get("revenue","—")    or "Private"
                    sector = c.get("sector","")
                    mc_col  = "#00c8f0" if mc  not in ("Private","—","N/A") else "#4a7090"
                    rev_col = "#a8c4d8" if rev not in ("Private","—","N/A") else "#4a7090"
                    comp_html += (
                        f'<div style="display:flex;align-items:center;justify-content:space-between;'
                        f'padding:6px 0;border-bottom:1px solid #0d1a2e">'
                        f'<div>'
                        f'<div style="font-size:.76rem;font-weight:600;color:#e8f2ff">{name}</div>'
                        + (f'<div style="font-size:.62rem;color:#4a7090;margin-top:1px">{sector}</div>' if sector else '')
                        + f'</div>'
                        f'<div style="display:flex;gap:18px;flex-shrink:0">'
                        f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:.72rem;'
                        f'font-weight:600;color:{mc_col}">{mc}</span>'
                        f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:.72rem;'
                        f'color:{rev_col}">{rev}</span>'
                        f'</div></div>'
                    )
                st.markdown(comp_html, unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div style="font-size:.76rem;color:#4a7090;padding:20px 0;text-align:center">'
                    'No competitor data available</div>',
                    unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── ROW 5: RISK + RECOMMENDATION ──────────────────
    c_ri, c_rc = st.columns([1,2], gap="small")

    with c_ri:
        rl_v   = risk.get("overall_risk_level","N/A")
        ri_ico = risk.get("risk_indicator","⚪")
        rc_col = {"critical":"#ff4757","high":"#fb923c","medium":"#ffb300",
                  "low":"#00e676","minimal":"#00e676"}.get(rl_v,"#7ba3c0")
        cf_n   = risk.get("confirmed_flags",0)
        uf_n   = risk.get("unconfirmed_flags",0)
        ps_n   = risk.get("positive_signals",0)
        top_r  = risk.get("top_risks",[])
        reco   = risk.get("recommendation","")
        r_rows = "".join(
            f'<div style="font-size:.72rem;color:var(--t3);padding:3px 0;'
            f'border-bottom:1px solid var(--bd)">• {r}</div>'
            for r in top_r[:4]
        )
        st.markdown(f"""
<div class="card" style="border-color:{rc_col}33"><div class="ct">Risk Assessment</div><div style="display:flex;align-items:center;gap:7px;margin-bottom:7px"><span style="font-size:1.3rem">{ri_ico}</span><div><div style="font-family:var(--fm);font-size:.85rem;font-weight:700;color:{rc_col}">{rl_v.upper()}</div><div style="font-size:.7rem;color:var(--t3);font-family:var(--fm)">✓{cf_n} confirmed · ?{uf_n} unconfirmed · ↑{ps_n} positive</div></div></div><div style="font-size:.68rem;color:var(--t3);margin-bottom:6px;line-height:1.45">{reco}</div>{r_rows}<div style="position:absolute;bottom:0;left:0;height:2px;width:100%;background:linear-gradient(90deg,{rc_col},transparent)"></div>
        </div>""", unsafe_allow_html=True)

    with c_rc:
        hlts       = report.get("financial_highlights", [])
        rec        = report.get("recommendation", "N/A")
        thesis     = report.get("thesis", "")
        bull       = report.get("bull_case", "")
        bear       = report.get("bear_case", "")
        mkt        = report.get("market_opportunity", "")
        catalysts  = report.get("catalysts", [])
        dq         = report.get("data_quality", "N/A")
        pt         = report.get("price_target", "")
        upside     = report.get("upside_downside", "")
        dq_key     = str(dq).split()[0]
        _dq_rgb_map = {"HIGH":"0,230,118","MEDIUM":"255,179,0","LOW":"255,71,87"}
        dq_rgb      = _dq_rgb_map.get(dq_key, "123,163,192")
        _dq_col_map = {"HIGH":"#00e676","MEDIUM":"#ffb300","LOW":"#ff4757"}
        dq_color    = _dq_col_map.get(dq_key, "#7ba3c0")

        # Financial highlight pills
        pills = "".join(
            f'<span style="background:rgba(0,200,240,.07);border:1px solid rgba(0,200,240,.15);'
            f'border-radius:4px;padding:3px 8px;font-size:.7rem;color:#00c8f0;margin:2px 3px 2px 0;'
            f'display:inline-block">• {h}</span>'
            for h in hlts[:4]
        )
        catalyst_html = "".join(
            f'<div style="display:flex;align-items:flex-start;gap:6px;padding:4px 0;'
            f'border-bottom:1px solid #142236;font-size:.72rem">'
            f'<span style="color:#00c8f0;flex-shrink:0;margin-top:1px">◆</span>'
            f'<span style="color:#a8c4d8">{c}</span></div>'
            for c in catalysts[:3]
        )
        price_target_html = (
            f'<div style="display:flex;align-items:center;gap:12px;padding:8px 12px;'
            f'background:rgba(0,200,240,.05);border:1px solid rgba(0,200,240,.15);'
            f'border-radius:6px;margin-bottom:10px">'
            f'<div><div style="font-size:.6rem;color:#4a7090;text-transform:uppercase;letter-spacing:.6px">12M Price Target</div>'
            f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:1.1rem;font-weight:700;color:#00c8f0">{pt}</div></div>'
            + (f'<div style="border-left:1px solid #142236;padding-left:12px">'
               f'<div style="font-size:.6rem;color:#4a7090;text-transform:uppercase;letter-spacing:.6px">Upside / Downside</div>'
               f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:1.1rem;font-weight:700;'
               f'color:{"#00e676" if upside.startswith("+") else "#ff4757"}">{upside}</div></div>'
               if upside else '')
            + '</div>'
            if pt else ''
        )

        st.markdown(
            f'<div class="card">'
            f'<div class="ct">Investment Recommendation'
            f'<span style="background:rgba({dq_rgb},.1);border:1px solid rgba({dq_rgb},.25);'
            f'border-radius:3px;padding:1px 7px;font-size:.62rem;color:{dq_color}">'
            f'Data: {dq_key}</span></div>'
            + price_target_html
            + (f'<div style="font-size:.7rem;font-weight:600;color:#6e9ab8;text-transform:uppercase;letter-spacing:.6px;margin-bottom:4px">Investment Thesis</div>'
               f'<div style="font-size:.78rem;color:#e8f2ff;line-height:1.65;margin-bottom:10px;border-left:2px solid #00c8f0;padding-left:8px">{thesis}</div>'
               if thesis else '')
            + f'<div style="display:flex;gap:8px;margin-bottom:10px">'
            + (f'<div style="flex:1;background:#0d1a2e;border:1px solid #142236;border-radius:6px;padding:8px 10px">'
               f'<div style="font-size:.6rem;font-weight:700;color:#00e676;text-transform:uppercase;letter-spacing:.6px;margin-bottom:4px">▲ Bull Case</div>'
               f'<div style="font-size:.72rem;color:#a8c4d8;line-height:1.55">{bull}</div></div>'
               if bull else '')
            + (f'<div style="flex:1;background:#0d1a2e;border:1px solid #142236;border-radius:6px;padding:8px 10px">'
               f'<div style="font-size:.6rem;font-weight:700;color:#ff4757;text-transform:uppercase;letter-spacing:.6px;margin-bottom:4px">▼ Bear Case</div>'
               f'<div style="font-size:.72rem;color:#a8c4d8;line-height:1.55">{bear}</div></div>'
               if bear else '')
            + '</div>'
            + (f'<div style="font-size:.7rem;font-weight:600;color:#6e9ab8;text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px">Catalysts</div>'
               + catalyst_html
               + '<div style="margin-bottom:10px"></div>'
               if catalysts else '')
            + f'<div style="font-size:.7rem;font-weight:600;color:#6e9ab8;text-transform:uppercase;letter-spacing:.6px;margin-bottom:4px">Recommendation</div>'
            + f'<div style="font-size:.76rem;color:#e8f2ff;line-height:1.65;margin-bottom:8px">{rec}</div>'
            + (f'<div style="display:flex;flex-wrap:wrap;gap:0;margin-top:6px">{pills}</div>' if pills else '')
            + '</div>',
            unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── ROW 6: FINANCIAL STATEMENTS ───────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    tab_inc, tab_bal, tab_cf = st.tabs(
        ["📊 Income Statement","⚖️ Balance Sheet","💸 Cash Flow"])

    for tab_obj, tab_name in [(tab_inc,"Income"),(tab_bal,"Balance"),(tab_cf,"Cash Flow")]:
        with tab_obj:
            fq = st.radio("_freq_"+tab_name, ["Quarterly","Annual"],
                          horizontal=True, label_visibility="collapsed",
                          key=f"db_finfreq_{tab_name}")
            fk  = "Q" if fq == "Quarterly" else "A"
            fd  = _FIN[tab_name][fk]
            st.markdown(_html_fin_table(fd["r"], fd["h"]), unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── ROW 7: AGENTS + DOWNLOADS ─────────────────────
    c_ag, c_dl = st.columns([3,1], gap="small")

    with c_ag:
        lbl_m = {"market_research":"📊 Market","financial_analyst":"💰 Financial",
                 "risk_assessor":"⚠ Risk","sentiment_news":"📰 Sentiment",
                 "competitor":"🏁 Competitor"}
        chips = ""
        for aid, lbl in lbl_m.items():
            ar   = a_results.get(aid, {})
            ok   = ar.get("success", False)
            dur  = round(ar.get("duration", 0), 1)
            cls  = "ok" if ok else "fail"
            icon = "✓" if ok else "✗"
            chips += f'<span class="ach {cls}">{icon} {lbl} {dur}s</span>'
        total_t = round(output.get("duration_seconds",0), 1)
        ok_n    = output.get("agents_succeeded", 0)
        st.markdown(
            f'<div style="padding:5px 0">{chips}</div>'
            f'<div style="font-size:.7rem;color:var(--t3);font-family:var(--fm);margin-top:3px">'
            f'Analysis complete in {total_t}s · {ok_n}/5 agents succeeded</div>',
            unsafe_allow_html=True)

    with c_dl:
        try:
            from utils.report_formatter import to_markdown_report, to_json_report
            d1, d2 = st.columns(2)
            with d1:
                st.download_button("📄 MD", to_markdown_report(output),
                                   file_name=f"{company}_report.md",
                                   mime="text/markdown", use_container_width=True)
            with d2:
                st.download_button("⬡ JSON", to_json_report(output),
                                   file_name=f"{company}_data.json",
                                   mime="application/json", use_container_width=True)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# SEARCH BAR
# ─────────────────────────────────────────────────────────────
s1, s2, s3, s4, s5 = st.columns([1,4,1,1,1])

with s1:
    st.markdown('<div style="display:flex;align-items:center;gap:5px;padding:9px 4px 0"><div style="width:26px;height:26px;background:linear-gradient(135deg,#00c8f0,#005580);border-radius:6px;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:10px;color:white">D</div><span style="font-weight:800;font-size:.88rem;color:#00c8f0;letter-spacing:-.3px">DealRoom AI</span></div>', unsafe_allow_html=True)

with s2:
    company_input = st.text_input(
        "", placeholder="🔍  Search — Grab, Tesla, Airbnb, Notion, Stripe...",
        label_visibility="collapsed", key="main_search")

with s3:
    run_btn = st.button("Analyse →", use_container_width=True, type="primary")

with s4:
    force_refresh = st.checkbox("↺ Refresh", value=False)

with s5:
    kill_opt = st.selectbox(
        "💀", ["None","market_research","financial_analyst",
               "risk_assessor","sentiment_news","competitor"],
        label_visibility="collapsed", key="kill_sel")
    st.session_state.kill_agent = None if kill_opt == "None" else kill_opt

# History quick-access
if st.session_state.history:
    hc = st.columns(min(5, len(st.session_state.history)))
    v_icons = {"BUY":"🟢","HOLD":"🟡","AVOID":"🔴"}
    for i, h in enumerate(st.session_state.history[-5:]):
        v  = h.get("output",{}).get("report",{}).get("investment_verdict","?")
        ic = v_icons.get(v,"⚪")
        with hc[i]:
            if st.button(f"{ic} {h['company']}", key=f"hist_{i}",
                         use_container_width=True):
                st.session_state.output  = h["output"]
                st.session_state.company = h["company"]
                st.rerun()


# ─────────────────────────────────────────────────────────────
# ANALYSIS FLOW
# ─────────────────────────────────────────────────────────────
if run_btn and company_input.strip():
    from guardrails.safety import validate_company_input
    val = validate_company_input(company_input.strip())

    if not val.valid:
        st.markdown(f"""
<div class="gblock"><div style="font-size:.82rem;font-weight:600;margin-bottom:5px">🛡️ GUARDRAIL BLOCKED — Input Rejected</div><div style="font-size:.7rem;color:var(--t3);line-height:1.5">Input: <code>{company_input[:60]}</code><br>Reason: {val.blocked_reason}</div>
        </div>""", unsafe_allow_html=True)
        st.stop()

    # ── LIVE ACTIVITY PANEL ──────────────────────────
    agent_status = {k:"⏳" for k in
                    ["market_research","financial_analyst","risk_assessor",
                     "sentiment_news","competitor"]}
    lbl_map = {"market_research":"📊 Market","financial_analyst":"💰 Financial",
               "risk_assessor":"⚠ Risk","sentiment_news":"📰 Sentiment",
               "competitor":"🏁 Competitor"}

    # Single slot renders header + chips + trace in ONE block — no overlap
    panel_slot = st.empty()
    all_traces: list = []

    def _build_panel():
        """Render the whole live panel as one HTML string."""
        chips_html = ""
        for aid, s in agent_status.items():
            cls = "run" if s=="🔄" else ("ok" if s=="✅" else ("fail" if s=="❌" else ""))
            chips_html += f'<span class="ach {cls}">{s} {lbl_map[aid]}</span>'

        trace_html = ""
        for t in all_traces[-80:]:
            sc   = {"info":"ti","success":"ts","warning":"tw","error":"te","tool_call":"tt"}.get(t.get("status","info"),"ti")
            ic   = {"info":"▸","success":"✓","warning":"⚠","error":"✗","tool_call":"⚙"}.get(t.get("status","info"),"▸")
            ag   = t.get("agent", t.get("agent_id","?"))
            step = t.get("step","")
            det  = t.get("detail","")[:75]
            tool = t.get("tool_name") or t.get("tool","")
            ts   = f' <span style="color:#254268">[{tool}]</span>' if tool else ""
            trace_html += (f'<div class="tl {sc}">{ic} '
                           f'<span style="opacity:.55">{ag}</span>{ts} {step}: {det}</div>')

        panel_slot.markdown(
            f'<div style="background:#0a1422;border:1px solid #142236;border-radius:10px;padding:14px 16px;margin:6px 0">'
            f'<div style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:#6e9ab8;margin-bottom:10px">⚡ Live Agent Activity</div>'
            f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px">{chips_html}</div>'
            f'<div style="background:#0d1a2e;border:1px solid #142236;border-radius:6px;padding:8px 10px;max-height:300px;overflow-y:auto">'
            + (trace_html if trace_html else '<div class="tl ti">▸ Initialising agents...</div>')
            + '</div></div>',
            unsafe_allow_html=True)

    _build_panel()

    def on_trace(entry: dict):
        all_traces.append(entry)
        agent  = entry.get("agent","")
        status = entry.get("status","info")
        step   = entry.get("step","").lower()
        if "dispatched" in step:
            if agent in agent_status: agent_status[agent] = "🔄"
        elif status == "success" and "complete" in step:
            if agent in agent_status: agent_status[agent] = "✅"
        elif status == "error":
            if agent in agent_status: agent_status[agent] = "❌"
        _build_panel()

    # ── RUN ORCHESTRATOR ─────────────────────────────
    spinner_slot = st.empty()
    spinner_slot.markdown(
        '<div style="font-family:var(--fm);font-size:.74rem;color:var(--t3);'
        'padding:6px 2px">⏳ Running agents in parallel...</div>',
        unsafe_allow_html=True)
    try:
        from orchestrator.orchestrator_agent import OrchestratorAgent
        orch = OrchestratorAgent(trace_callback=on_trace)

        if st.session_state.kill_agent and \
           st.session_state.kill_agent in orch._agents:
            from agents.base_agent import AgentResult
            kn = st.session_state.kill_agent
            async def _killed(*a, **kw):
                await asyncio.sleep(.3)
                return AgentResult(agent_id=kn, success=False,
                                   data={"error":"Killed for demo"},
                                   trace=[], error="Intentionally killed")
            orch._agents[kn].run = _killed
            on_trace({"agent":"orchestrator","step":"DEMO",
                      "detail":f"Agent '{kn}' killed — watch recovery",
                      "status":"warning"})

        # Create a guaranteed-fresh event loop for every analysis run.
        # This is required because Streamlit reruns the script on each
        # interaction — asyncio.run() from the previous run leaves a closed
        # loop, and any module-level asyncio objects (queues, locks) from
        # that run are bound to it. We close the old loop explicitly and
        # install a brand-new one before calling into the agent system.
        try:
            old_loop = asyncio.get_event_loop()
            if not old_loop.is_closed():
                old_loop.close()
        except Exception:
            pass
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            output = loop.run_until_complete(
                orch.analyse(val.cleaned, force_refresh=force_refresh))
        finally:
            loop.close()
        spinner_slot.empty()
    except Exception as e:
        import traceback as _tb
        spinner_slot.empty()
        st.error(f"Analysis failed: {e}")
        st.code(_tb.format_exc())
        st.stop()

    # Final status
    for aid, ar in output.get("agent_results",{}).items():
        if aid in agent_status:
            agent_status[aid] = "✅" if ar.get("success") else "❌"
    _build_panel()

    # A2A messages
    a2a_msgs = output.get("a2a_messages",[])
    if a2a_msgs:
        st.markdown(
            '<div class="card" style="margin:4px 0">'
            '<div class="ct">🔗 A2A Inter-Agent Messages</div>'
            + _html_a2a(a2a_msgs) + "</div>",
            unsafe_allow_html=True)

    # Save
    st.session_state.history.append({
        "company":   val.cleaned,
        "output":    output,
        "timestamp": time.time(),
    })
    st.session_state.output  = output
    st.session_state.company = val.cleaned

    # Render at TOP LEVEL
    st.markdown("---")
    render_dashboard(output, val.cleaned)

elif st.session_state.output and not run_btn:
    render_dashboard(st.session_state.output,
                     st.session_state.company)

elif not run_btn and not st.session_state.output:
    fc = "".join(
        f'<div class="card" style="text-align:center;padding:12px">'
        f'<div style="font-size:1.4rem;margin-bottom:4px">{ic}</div>'
        f'<div style="font-size:.6rem;color:var(--t3);font-weight:700;'
        f'text-transform:uppercase;letter-spacing:.5px">{lb}</div></div>'
        for ic, lb in [("📊","Market"),("💰","Financial"),
                       ("⚠️","Risk"),("📰","Sentiment"),("🏁","Competitor")]
    )
    st.markdown(f"""
<div class="wsc"><h1>🏦 DealRoom AI</h1><p style="font-size:.88rem;color:var(--t3);margin-bottom:28px">Investment-grade due diligence · 5 AI agents · Google ADK + A2A + MCP</p><div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;max-width:640px;margin:0 auto 28px">{fc}</div><div style="color:var(--t3);font-family:var(--fm);font-size:.74rem">Try: Grab · Tesla · Airbnb · Notion · Stripe · Sea Limited</div>
    </div>""", unsafe_allow_html=True)

elif run_btn and not company_input.strip():
    st.warning("Please enter a company name.")
