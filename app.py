"""
Public Trading Playbook Viewer (Read-Only)
==========================================
Reads live playbook data from a GitHub Gist and displays it.
No account info, no sizing, no deployment details.

Deploy to Streamlit Cloud from a GitHub repo.
"""

import streamlit as st
import json
from urllib.request import urlopen
from urllib.error import URLError
from datetime import datetime

st.set_page_config(page_title="Trading Playbook", page_icon="📊", layout="wide")

# ============================================================
# CONFIG — set this after running gist_sync.py setup
# ============================================================
GIST_RAW_URL = st.secrets.get("GIST_RAW_URL", "")

# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .score-high { background: linear-gradient(90deg, #064e3b, #065f46); border-left: 4px solid #10b981;
                  padding: 12px 16px; border-radius: 6px; margin: 6px 0; }
    .score-med  { background: linear-gradient(90deg, #1e3a5f, #1e40af); border-left: 4px solid #3b82f6;
                  padding: 12px 16px; border-radius: 6px; margin: 6px 0; }
    .score-low  { background: linear-gradient(90deg, #78350f, #92400e); border-left: 4px solid #f59e0b;
                  padding: 12px 16px; border-radius: 6px; margin: 6px 0; }
    .score-skip { background: linear-gradient(90deg, #450a0a, #7f1d1d); border-left: 4px solid #ef4444;
                  padding: 12px 16px; border-radius: 6px; margin: 6px 0; }
    .zone-hot  { background: #064e3b; border: 1px solid #10b981; border-radius: 4px;
                 padding: 8px 12px; margin: 4px 0; }
    .zone-warm { background: #1e3a5f; border: 1px solid #3b82f6; border-radius: 4px;
                 padding: 8px 12px; margin: 4px 0; }
    .zone-cold { background: #1c1917; border: 1px solid #57534e; border-radius: 4px;
                 padding: 8px 12px; margin: 4px 0; }
    .how-section { background: #111827; border: 1px solid #1f2937; border-radius: 8px;
                   padding: 16px 20px; margin: 8px 0; }
    .how-header { color: #10b981; font-size: 1.2em; font-weight: bold; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=30)
def fetch_playbook():
    """Fetch playbook from Gist (cached 30s)."""
    if not GIST_RAW_URL:
        return None
    try:
        with urlopen(GIST_RAW_URL + "?t=" + str(int(datetime.now().timestamp()))) as resp:
            return json.loads(resp.read().decode())
    except (URLError, Exception):
        return None


# ============================================================
# TABS
# ============================================================
tab_playbook, tab_how = st.tabs(["📊 Live Playbook", "📖 How It Works"])


# ============================================================
# TAB 1: LIVE PLAYBOOK
# ============================================================
with tab_playbook:
    data = fetch_playbook()

    if not data:
        st.warning("Playbook not loaded. Check back when the market is open.")
        st.info("The playbook updates live throughout the trading session as new data comes in.")
        st.stop()

    st.title("📊 Daily Trading Playbook")
    st.caption(f"{data.get('day', '')}, {data.get('date', '')} | {data.get('phase', '')} | Last update: {data.get('updated', '?')}")

    # Metrics row
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    total = data.get("total_score", 0)
    with c1:
        label = "ELITE" if total >= 9 else ("Good" if total >= 7 else ("Min" if total >= 4 else "Skip"))
        st.metric("Total Score", f"{total}/{data.get('max_score', 11)}", delta=label)
    with c2:
        sb = data.get("set_bias", "silent")
        st.metric("Set", f"{data.get('set_score', 0)}/{data.get('set_max', 5)}", delta=sb if sb not in ["silent", "neutral"] else None)
    with c3:
        jb = data.get("jay_bias", "none")
        st.metric("Jay", f"{data.get('jay_score', 0)}/{data.get('jay_max', 2)}", delta=jb if jb not in ["none", "neutral"] else None)
    with c4:
        st.metric("BB Regime", data.get("bb_regime", "?"), delta=data.get("bb_orb_signal", "?"))
    with c5:
        ema = data.get("ema_structure", "?")
        st.metric("EMAs", ema, delta="+1" if ema in ["BULL STACK", "BEAR STACK"] else "+0")
    with c6:
        gap = data.get("gap", 0)
        st.metric("Gap", f"{gap:+.1f}" if gap else "--")

    # BB Regime banner
    bb_signal = data.get("bb_orb_signal", "")
    rc = "score-high" if bb_signal == "GO" else ("score-skip" if bb_signal == "SKIP" else "score-med")
    st.markdown(f'<div class="{rc}" style="text-align:center;font-size:1.1em;"><b>BB REGIME: {data.get("bb_regime","?")}</b> -- {data.get("bb_desc","")}</div>', unsafe_allow_html=True)

    # Deployment summary (count only, no names)
    n_active = data.get("n_accounts_active", 0)
    deploy_css = "score-high" if n_active >= 5 else ("score-med" if n_active >= 3 else "score-low")
    st.markdown(f'<div class="{deploy_css}" style="text-align:center;"><b>DEPLOYMENT: {n_active} accounts active</b> | Score: {total}</div>', unsafe_allow_html=True)

    st.text("")
    left, right = st.columns([3, 2])

    with left:
        st.subheader("Trade Ideas")

        # ORB
        if data.get("orb_eligible"):
            orb_dir = (data.get("orb_direction") or "both").upper()
            css = "score-high"
            day = data.get("day", "")
            mw = " (elevated threshold)" if day in ["Monday", "Wednesday"] else ""
            st.markdown(f"""<div class="{css}">
                <b>ORB BREAKOUT -- {orb_dir}</b>{mw}<br>
                <span style="font-size:0.9em;">15-min range break at 7:45 MT | Stop: opposite side + 4 ticks | T1: 2R, Runner to 4R/EOD</span>
            </div>""", unsafe_allow_html=True)
        elif data.get("orb_day"):
            reason = f"BB {data.get('bb_regime','?')} ({data.get('bb_orb_signal','SKIP')})" if data.get("bb_orb_signal") != "GO" else f"Score {total} < {data.get('orb_min_score', 4)}"
            st.markdown(f'<div class="score-skip">ORB: <b>SKIP</b> -- {reason}</div>', unsafe_allow_html=True)

        # SET
        if data.get("set_eligible"):
            st.markdown(f"""<div class="score-high">
                <b>SET TRADE -- {data.get('set_direction','?')} (2-Bullet)</b> | Conv: HIGH<br>
                <span style="font-size:0.9em;">B1: Entry at Set's level | B2: Re-entry if B1 stops | {data.get('set_keywords','')}</span>
            </div>""", unsafe_allow_html=True)
        elif sb in ["bull", "bear"]:
            conv = data.get("set_conviction", "?")
            st.markdown(f'<div class="score-skip">SET TRADE: <b>SKIP</b> -- score {total} or conviction {conv}</div>', unsafe_allow_html=True)

        # JAY
        if data.get("jay_eligible"):
            st.markdown(f"""<div class="score-med">
                <b>JAY TRADE -- {data.get('jay_direction','?')} (Scalp)</b> | Conv: {data.get('jay_conviction','?').upper()}<br>
                <span style="font-size:0.9em;">Limit at Jay's level | Fast in/out | {data.get('jay_notes','')}</span>
            </div>""", unsafe_allow_html=True)
        elif jb in ["bull", "bear"]:
            st.markdown(f'<div class="score-skip">JAY TRADE: <b>SKIP</b> -- low conviction</div>', unsafe_allow_html=True)

        # Bounce zones
        zones = data.get("zones", [])
        cp = data.get("current_price", 0)
        if zones and cp:
            st.text("")
            st.markdown("**Level Bounce Zones** (watch for PA confirmation)")
            for z in sorted(zones, key=lambda x: -x["weight"])[:6]:
                dist = z["price"] - cp
                if abs(dist) < 3 or abs(dist) > 80:
                    continue
                role = "Support" if dist < 0 else "Resistance"
                action = "Buy bounce" if dist < 0 else "Sell rejection"
                css = "zone-hot" if z["weight"] >= 5 else ("zone-warm" if z["weight"] >= 3 else "zone-cold")
                roles_str = " | ".join([f"{s}:{r}" for s, r in z["roles"]])
                stars = "+" * min(z["src_count"], 5)
                st.markdown(f"""<div class="{css}">
                    <b>{z['price']:.0f}</b> ({dist:+.0f}pt) -- {role} [{stars}]
                    <span style="float:right;">Wt:{z['weight']} | {z['src_count']} sources</span><br>
                    <span style="font-size:0.8em;color:#9ca3af;">{action} | {roles_str}</span>
                </div>""", unsafe_allow_html=True)

    with right:
        st.subheader("Level Map")
        if zones and cp:
            current_printed = False
            for z in sorted(zones, key=lambda x: x["price"]):
                dist = z["price"] - cp
                if abs(dist) > 100:
                    continue
                css = "zone-hot" if z["weight"] >= 5 else ("zone-warm" if z["weight"] >= 3 else "zone-cold")
                roles = " | ".join([f"{s}:{r}" for s, r in z["roles"]])
                stars = "+" * min(z["src_count"], 5)

                if not current_printed and z["price"] > cp:
                    st.markdown(f'<div style="background:#fbbf24;color:#000;text-align:center;padding:6px;border-radius:4px;font-weight:bold;">CURRENT: {cp:.0f}</div>', unsafe_allow_html=True)
                    current_printed = True

                st.markdown(f'<div class="{css}"><b>{z["price"]:.0f}</b> ({dist:+.0f}) [{stars}] Wt:{z["weight"]}<br><span style="font-size:0.8em;color:#9ca3af;">{roles}</span></div>', unsafe_allow_html=True)

            if not current_printed:
                st.markdown(f'<div style="background:#fbbf24;color:#000;text-align:center;padding:6px;border-radius:4px;font-weight:bold;">CURRENT: {cp:.0f}</div>', unsafe_allow_html=True)
        else:
            st.info("Levels will appear once the session is active.")

    # Auto-refresh
    st.caption("Auto-refreshes every 30 seconds. Data updates whenever inputs change on the main dashboard.")


# ============================================================
# TAB 2: HOW IT WORKS
# ============================================================
with tab_how:
    st.title("How This System Works")
    st.caption("A data-driven confluence trading system for ES/MES futures")

    st.markdown("""
---
## The Big Picture

This is a **confluence-based trading system** that combines multiple independent data sources to score
how confident we are in a given trade setup. Instead of relying on any single indicator or opinion,
we stack signals from discretionary traders, technical analysis, and market structure to find
high-probability setups.

**The core idea**: The more independent sources that agree on a direction, the higher the conviction,
the more capital we deploy. When signals conflict, we size down or sit out entirely.

---
""")

    st.markdown("""
<div class="how-section">
<div class="how-header">Scoring System: 0-11 Points</div>

The total score determines whether we trade, how many accounts we deploy, and how aggressively we size.

| Component | Max Points | What It Measures |
|-----------|-----------|-----------------|
| **Set's Bias** | 5 | Discretionary trader's directional call + conviction level |
| **Jay's Bias** | 2 | Second discretionary trader's call for confirmation |
| **Technicals** | 4 | Bollinger Band regime (0-3) + EMA structure (0-1) |
| **Total** | **11** | Combined confluence score |

**Score Tiers:**
- **9+** = ELITE -- max deployment, highest conviction
- **7-8** = GOOD -- strong setup, deploy confidently
- **4-6** = MINIMUM -- reduced size, fewer accounts
- **0-3** = SKIP -- no trade, sit on hands
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">Set's Bias (0-5 points)</div>

Set (@Adaamset) is an ES futures trader who posts weekly bias updates on Substack with key levels,
plus real-time Discord journal entries during the session.

**How he scores:**
- Base: conviction level (High=3, Med=2, Low=1)
- +1 if his Discord journal is active (real-time confirmation)
- +1 for high-conviction keywords: "Large Orders", "Full Clip", "Gone Shopping", "Pyramiding"

**His vocabulary:**
- **Makeba** = bearish / markets going down
- **KiKi** = bullish / markets going up
- **Coin Coma** = made a huge amount of money
- **DLL** = Daily Loss Limit (he stops trading when hit)
- **Full Clip** = maximum position size, highest conviction
- **Gone Shopping** = aggressively adding to position

**His levels as S/R zones:** Backtested at 66.7% bounce rate overall, 83.8% at resistance levels.
Over 2 years: 65.6% win rate, 1.98 win/loss ratio on 1,704 journal entries across 321 trading days.

**Silence rules:**
- No post during an active Substack swing = he's still in, carry forward last conviction
- No post AND no active bias = neutral/sidelined (score 0)
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">Jay's Bias (0-2 points)</div>

Jay is a second discretionary futures trader. His calls provide independent confirmation of direction.

**How he scores:**
- High conviction = 2 points
- Med/Low conviction = 1 point

**Why Jay is always eligible:** Unlike Set trades (which need score 7+), Jay's scalp trades are
always shown when he has a directional call with med+ conviction. His style is fast in/out scalps
at specific levels, which can work independently of the broader confluence picture.

Jay's key levels feed into the Level Map with weight 2, contributing to zone clustering.
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">Technicals: Bollinger Band Regime (0-3 points)</div>

We classify the 1-hour ES Bollinger Bands into a **5-state regime** based on width and trend direction.
This was backtested against 2 years of ORB (Opening Range Breakout) data.

| Regime | Condition | Signal | Score | What It Means |
|--------|-----------|--------|-------|--------------|
| **SQUEEZE** | Narrow (<50pt) + contracting | GO | 3 | Coiling for a breakout |
| **BREAKOUT** | Narrow (<50pt) + expanding | GO | 3 | Move is starting |
| **TRENDING** | Wide (50pt+) + expanding | GO | 3 | Strong momentum |
| **WIDE PULLBACK** | 60pt+ but contracting | GO | 2 | Prior trend still active |
| **EXHAUSTION** | 50-60pt + contracting | SKIP | 0 | Chop zone, fade the edges |

**Why this matters:** Backtested results showed GO regimes produce PF 1.81 (+$107K over 2 years).
EXHAUSTION regime produces PF 0.60 -- a net loser. The old method (simple expanding/contracting toggle)
had PF 1.72, so this 5-state system adds +$32,600 in edge.

**The 60pt override:** When BBs are very wide (60pt+) even while contracting, the prior trend is still
active enough to trade. Backtested at 72.7% WR, PF 3.72.
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">Technicals: EMA Structure (0-1 point)</div>

We read the 20, 50, and 200 period EMAs from the 1-hour ES chart.

| Structure | Condition | Score |
|-----------|-----------|-------|
| **BULL STACK** | EMA 20 > 50 > 200 | +1 |
| **BEAR STACK** | EMA 20 < 50 < 200 | +1 |
| **MIXED** | Any other order | +0 |

**Backtested edge:** Bull Stack trades had PF 2.16 (vs 1.82 baseline). Bull Stack + tight EMA spread
(<43pt between EMA 20 and 200) = PF 2.82, 62.9% WR.

**Why +1 not +2:** EMA stacking is a strong confirmation signal but used as a gate it would filter
out 206 viable trades. As a +1 point confirmation, it lifts the best setups without blocking good ones.
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">ORB Strategy (Opening Range Breakout)</div>

The primary automated trade. We use the first 15 minutes of Regular Trading Hours (7:30-7:45 MT)
to define a range, then trade the breakout of that range.

**Rules:**
- **Entry**: Break of the 15-min high (long) or low (short) after 7:45 MT
- **Stop**: Opposite side of the range + 4 ticks
- **Targets**: 50% off at 2R, runner at breakeven to 4R or EOD
- **Window**: Must trigger by 9:00 MT or cancel

**Why ORB:**
- Mechanical, repeatable, no discretion needed
- Backtested PF 1.87 with Model B sizing over 2 years
- Works best on Tuesday, Thursday, Friday (PF 1.84)
- Monday/Wednesday added with elevated score threshold (5+ vs 4+), backtested PF 2.17

**Model B Sizing (BB + EMA -> contracts per account):**

| Tier | Condition | Contracts |
|------|-----------|-----------|
| MAX | TRENDING/BREAKOUT + stacked EMAs + tight spread (<43pt) | 5 |
| FULL | Any GO regime + stacked EMAs | 4 |
| MID | Any GO regime + mixed EMAs, OR Wide PB + stacked | 3 |
| MIN | Wide Pullback + mixed EMAs | 2 |
| SKIP | EXHAUSTION regime | 0 |

Backtested: MAX tier had 65% WR and PF 2.86 over 157 trades. Model B adds +$25K over flat sizing.
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">Set Trades (Discretionary)</div>

When Set has a high-conviction directional call AND the total score is 7+, we deploy a 2-bullet
entry strategy following his thesis.

**Why score 7+:** Set's trades are discretionary swing/intraday plays. The score threshold ensures
we only follow his calls when other signals (Jay, technicals) confirm. His calls without confirmation
have a lower win rate.

**2-Bullet System:**
- **Bullet 1** (60% of risk): Enter at Set's level when he posts
- **Bullet 2** (40% of risk): Only if B1 stops out -- re-enter at the next support/resistance level
- This gives a second chance at a better price while capping total risk
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">Level Map & Bounce Zones</div>

All levels from every source get clustered into zones. When multiple independent sources point to
the same price area (+/- 8 points), that zone gets higher weight and more stars.

**Sources and their weights:**
| Source | Examples | Base Weight |
|--------|----------|-------------|
| Set's Pivot | Central level from Substack | 3 |
| Set's S/R | Support & resistance levels | 2 |
| Jay's Levels | Key levels from his calls | 2 |
| Daily Plan | Bull/Bear pivots | 3 |
| Daily Plan | Trend Up/Down, S/R | 2 |
| VP Daily | POC | 2 |
| VP Daily | VAH, VAL | 1 |
| VP Weekly | W-POC | 3 |
| VP Weekly | W-VAH, W-VAL | 2 |
| VP Monthly | M-POC | 3 |
| VP Monthly | M-VAH, M-VAL | 2 |
| Prior Day | High, Low | 1 |
| Overnight | High, Low | 1 |

**How zones work:** Levels within 8 points of each other cluster together. The zone's total weight
is the sum of all individual weights. More sources = more stars = higher confidence that price
will react at that level.

**Bounce trade logic:** When price approaches a high-weight zone, watch for price action confirmation
(rejection candle, delta shift, absorption on footprint) before entering a bounce trade.
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">Account Deployment (Phase System)</div>

Capital is deployed across multiple accounts using a phase system that scales up as the track record builds.

| Phase | Who Trades | Requirement |
|-------|-----------|-------------|
| **Phase 1** | Eval accounts only | Starting out -- free reps, build data |
| **Phase 2** | Evals + funded on elite scores | 20+ trades, net positive |
| **Phase 3** | All accounts active | 50+ trades, PF > 1.3 |
| **Phase 4** | All accounts, max size | 100+ trades, PF > 1.5, weekly green |

Higher scores unlock more accounts at each phase. Score 9+ deploys the most accounts;
score 4-6 deploys fewer. This ensures maximum capital is only deployed on the highest-conviction setups.
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">Risk Management</div>

- **Max 2 trades before 9:00 MT**, 3 total per day
- **2 stops = done for the day** (Daily Loss Limit discipline)
- **EOD flatten by 13:55 MT** -- no overnight risk on intraday trades
- **DD safety**: Accounts below 25% remaining drawdown are frozen. Below 40% = elite scores only.
- **Per-trade risk cap**: Max 20% of remaining drawdown per entry per account
</div>
""", unsafe_allow_html=True)

    st.markdown("""
---
*This system combines mechanical execution (ORB) with discretionary trader reads (Set, Jay)
and technical regime filtering (BB, EMA) to find high-probability, well-sized trades.
Every component has been individually backtested against 2 years of data.*
""")
