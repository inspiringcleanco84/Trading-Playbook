"""
Public Trading Playbook Viewer (Read-Only)
==========================================
Reads live playbook data from a GitHub Gist and displays it.
No account names, balances, DD, or deployment details.
Matches the display and logic of dashboard_v2.py.
"""

import streamlit as st
import json
from urllib.request import urlopen
from urllib.error import URLError
from datetime import datetime

st.set_page_config(page_title="Trading Playbook", page_icon="📊", layout="wide")

# ============================================================
# CONFIG
# ============================================================
GIST_RAW_URL = st.secrets.get("GIST_RAW_URL", "")

# ============================================================
# CSS — matches local dashboard
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


def zone_stars(z):
    """Convert zone weight to 1-5 star rating."""
    w = z.get("weight", 0)
    if w >= 8: return 5
    if w >= 6: return 4
    if w >= 4: return 3
    if w >= 2: return 2
    return 1


# ============================================================
# Risk allocation logic — uses user's account DD
# ============================================================
RISK_PCT = 0.10  # 10% of remaining DD per trade idea (conservative baseline)

def score_mult(score):
    if score >= 8: return 1.0
    if score >= 6: return 0.7
    if score >= 4: return 0.5
    return 0.3

def conv_mult(conviction):
    return {"high": 1.0, "med": 0.7, "low": 0.4}.get(conviction, 0.4)

def calc_account_risk(accounts, score, conviction):
    """Calculate per-account risk from DD. Returns list of (acct, risk_$)."""
    sm = score_mult(score)
    cm = conv_mult(conviction)
    results = []
    for a in accounts:
        dd = a.get("dd_remaining", 0)
        if dd <= 0:
            continue
        # DD safety gating
        if dd < 200:
            results.append((a, 0, "FROZEN"))
            continue
        if dd < 500 and score < 9:
            results.append((a, 0, "DANGER (need 9+)"))
            continue
        base = dd * RISK_PCT
        risk = int(base * sm * cm)
        results.append((a, risk, "OK"))
    return results

def render_risk_deploy_accounts(acct_risks):
    """Render per-account risk deployment HTML."""
    if not acct_risks:
        return ('<div style="margin-top:8px;padding:10px;background:#1e293b;border-radius:6px;'
                'font-size:0.9em;color:#9ca3af;text-align:center;">'
                'Please input account data in the <b>My Accounts</b> tab for deployment recommendations</div>')
    active = [(a, r, s) for a, r, s in acct_risks if r > 0]
    frozen = [(a, r, s) for a, r, s in acct_risks if r == 0]
    total_risk = sum(r for _, r, _ in active)
    if not active and frozen:
        reasons = ", ".join([f"{a['name']}: {s}" for a, _, s in frozen])
        return (f'<div style="margin-top:8px;padding:8px;background:#7f1d1d;border-radius:6px;font-size:0.9em;">'
                f'<b>RISK DEPLOYMENT:</b> $0 -- all accounts gated<br>'
                f'<span style="color:#fca5a5;">{reasons}</span></div>')
    lines = []
    for a, r, s in active:
        icon = {"Tradeify": "🟠", "TopStepX": "🔵"}.get(a.get("provider", ""), "⚪")
        lines.append(f"&nbsp;&nbsp;{icon} <b>{a['name']}:</b> ${r} risk (DD: ${a['dd_remaining']:,.0f})")
    for a, r, s in frozen:
        lines.append(f"&nbsp;&nbsp;⛔ <b>{a['name']}:</b> {s}")
    body = "<br>".join(lines)
    return (f'<div style="margin-top:8px;padding:8px;background:#1e293b;border-radius:6px;font-size:0.9em;">'
            f'<b>RISK DEPLOYMENT:</b> ${total_risk} total across {len(active)} account(s)<br>'
            f'{body}</div>')


# ============================================================
# ACCOUNTS — session state, persists across reruns
# ============================================================
if "user_accounts" not in st.session_state:
    st.session_state.user_accounts = []

# ============================================================
# TABS
# ============================================================
tab_playbook, tab_accounts, tab_how = st.tabs(["📊 Live Playbook", "💼 My Accounts", "📖 How It Works"])


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
    st.caption(f"{data.get('day', '')}, {data.get('date', '')} | {data.get('phase', '')}")
    st.markdown(f'<div style="text-align:right;color:#9ca3af;font-size:0.85em;margin-top:-10px;">Last Updated: <b>{data.get("updated", "?")}</b></div>', unsafe_allow_html=True)

    # Metrics row — matches local dashboard
    total = data.get("total_score", 0)
    ss = data.get("set_score", 0)
    js = data.get("jay_score", 0)
    ts = data.get("tech_score", 0)
    sb = data.get("set_bias", "silent")
    jb = data.get("jay_bias", "none")
    bb_regime = data.get("bb_regime", "?")
    bb_orb_signal = data.get("bb_orb_signal", "?")
    ema_structure = data.get("ema_structure", "?")
    set_conviction = data.get("set_conviction", "med")
    jay_conviction = data.get("jay_conviction", "med")
    jay_dom = data.get("jay_dom", "none")
    jay_dom_conviction = data.get("jay_dom_conviction", "med")
    cp = data.get("current_price", 0)
    prior_close = data.get("prior_close", 0) or data.get("ovn_low", 0)
    zones = data.get("zones", [])

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        label = "ELITE" if total >= 9 else ("Good" if total >= 7 else ("Min" if total >= 4 else "Skip"))
        st.metric("Total Score", f"{total}/12", delta=label)
    with c2:
        if sb == "bear":
            st.metric("Set", f"{ss}/4", delta="bear", delta_color="inverse")
        elif sb == "bull":
            st.metric("Set", f"{ss}/4", delta="bull")
        else:
            st.metric("Set", f"{ss}/4")
    with c3:
        if jb == "bear":
            st.metric("Jay", f"{js}/4", delta="bear", delta_color="inverse")
        elif jb == "bull":
            st.metric("Jay", f"{js}/4", delta="bull")
        else:
            st.metric("Jay", f"{js}/4")
    with c4:
        st.metric("BB Regime", bb_regime, delta=bb_orb_signal)
    with c5:
        st.metric("EMAs", ema_structure, delta="+1" if ema_structure in ["BULL STACK", "BEAR STACK"] else "+0")
    with c6:
        if cp and prior_close:
            st.metric("Gap", f"{cp - prior_close:+.1f}")
        else:
            st.metric("Gap", "--")

    # BB Regime banner
    rc = "score-high" if bb_orb_signal == "GO" else ("score-skip" if bb_orb_signal == "SKIP" else "score-med")
    st.markdown(f'<div class="{rc}" style="text-align:center;font-size:1.1em;"><b>BB REGIME: {bb_regime}</b> -- {data.get("bb_desc","")}</div>', unsafe_allow_html=True)

    # Deployment summary (public: count only, no account names)
    n_active = data.get("n_accounts_active", 0)
    deploy_css = "score-high" if n_active >= 5 else ("score-med" if n_active >= 3 else "score-low")
    st.markdown(f'<div class="{deploy_css}" style="text-align:center;"><b>DEPLOYMENT: {n_active} accounts active</b> | Score: {total}</div>', unsafe_allow_html=True)

    # Pre-compute account risks for each trade idea
    user_accts = st.session_state.user_accounts
    has_accounts = len(user_accts) > 0

    st.text("")
    left, right = st.columns([3, 2])

    with left:
        st.subheader("🎯 Trade Ideas + Account Deployment")

        # ---- ORB ----
        orb_eligible = data.get("orb_eligible", False)
        orb_day = data.get("orb_day", False)
        orb_min_score = data.get("orb_min_score", 4)
        orb_dir = (data.get("orb_direction") or "both").upper()

        if orb_eligible:
            day = data.get("day", "")
            mw_label = " (elevated threshold)" if day in ["Monday", "Wednesday"] else ""

            orb_risks = calc_account_risk(user_accts, total, "high") if has_accounts else []
            orb_deploy = render_risk_deploy_accounts(orb_risks)

            sizing_label = f"BB: {bb_regime} + EMA: {ema_structure}"
            st.markdown(f"""<div class="score-high">
                <b>🟢 MNQ ORB BREAKOUT</b> -- {day}{mw_label} | Score {total} | Direction: {orb_dir} favored<br>
                <span style="font-size:0.9em;color:#fbbf24;"><b>SIZING: {sizing_label}</b></span>
                <table style="width:100%;font-size:0.9em;margin-top:6px;">
                <tr><td style="color:#9ca3af;width:80px;">Entry</td><td>15-min range break (7:45 MT)</td>
                    <td style="color:#9ca3af;width:80px;">Window</td><td>7:30-9:00 MT</td></tr>
                <tr><td style="color:#9ca3af;">Stop</td><td>Opposite side + 4 ticks</td>
                    <td style="color:#9ca3af;">Target</td><td>Majority@2R + Runner@BE to 4R/EOD</td></tr>
                </table>
                {orb_deploy}</div>""", unsafe_allow_html=True)
        elif orb_day and bb_orb_signal != "GO":
            st.markdown(f'<div class="score-skip">🔴 ORB: BB regime is {bb_regime} ({bb_orb_signal}). <b>SKIP.</b></div>', unsafe_allow_html=True)
        elif orb_day and total < orb_min_score:
            day = data.get("day", "")
            mw_note = " -- Mon/Wed needs 5+" if day in ["Monday", "Wednesday"] else ""
            st.markdown(f'<div class="score-skip">🔴 ORB: Score {total} below minimum ({orb_min_score}{mw_note}). <b>SKIP.</b></div>', unsafe_allow_html=True)
        elif not orb_day:
            day = data.get("day", "")
            st.markdown(f'<div class="score-skip">🔴 ORB: Weekend ({day}). <b>SKIP.</b></div>', unsafe_allow_html=True)

        # ---- SET TRADE ----
        set_eligible = data.get("set_eligible", False)
        set_dir_str = data.get("set_direction", "?")
        set_keywords = data.get("set_keywords", "")

        if set_eligible:
            set_risks = calc_account_risk(user_accts, total, set_conviction) if has_accounts else []
            set_deploy = render_risk_deploy_accounts(set_risks)

            set_css = "score-high" if set_conviction == "high" else "score-med"
            st.markdown(f"""<div class="{set_css}">
                <b>🟢 SET TRADE -- {set_dir_str}</b> -- Score {total} | Conv: {set_conviction.upper()}
                {set_deploy}</div>""", unsafe_allow_html=True)
        elif sb in ["bull", "bear"]:
            reasons = []
            if set_conviction == "low": reasons.append("conviction low (skip)")
            st.markdown(f'<div class="score-skip">🔴 SET TRADE: <b>SKIP</b> -- {", ".join(reasons) if reasons else "not eligible"}</div>', unsafe_allow_html=True)

        # ---- JAY TRADE ----
        jay_eligible = data.get("jay_eligible", False)
        jay_dir_str = data.get("jay_direction", "?")
        jay_notes = data.get("jay_notes", "")

        if jay_eligible:
            jay_conv_label = "high" if jay_conviction == "high" or jay_dom_conviction == "high" else ("med" if js >= 2 else "low")
            jay_risks = calc_account_risk(user_accts, total, jay_conv_label) if has_accounts else []
            jay_deploy = render_risk_deploy_accounts(jay_risks)
            jay_detail = f"Bias: {data.get('jay_bias','?')}/{jay_conviction} | DOM: {jay_dom}/{jay_dom_conviction}"

            jay_css = "score-high" if js >= 3 else "score-med"
            st.markdown(f"""<div class="{jay_css}">
                <b>🔵 JAY TRADE -- {jay_dir_str}</b> -- Jay {js}/4 | {jay_detail}
                {jay_deploy}</div>""", unsafe_allow_html=True)
        elif jb in ["bull", "bear"]:
            st.markdown(f'<div class="score-skip">🔴 JAY TRADE: <b>SKIP</b> -- no conviction (Jay {js}/4)</div>', unsafe_allow_html=True)

        # ---- BOUNCE ZONES ----
        if zones and cp:
            st.text("")
            st.markdown("**📍 Level Bounce Zones** (watch for PA confirmation)")
            for z in sorted(zones, key=lambda x: -x.get("weight", 0))[:6]:
                dist = z["price"] - cp
                if abs(dist) < 3 or abs(dist) > 80:
                    continue
                role = "Support" if dist < 0 else "Resistance"
                action = "Buy bounce" if dist < 0 else "Sell rejection"
                n_stars = zone_stars(z)
                css = "zone-hot" if n_stars >= 4 else ("zone-warm" if n_stars >= 3 else "zone-cold")
                roles_str = " | ".join([f"{s}:{r}" for s, r in z.get("roles", [])])
                star_display = "\u2B50" * n_stars

                st.markdown(f"""<div class="{css}">
                    <b>{z['price']:.0f}</b> -- {role} {star_display}
                    <span style="float:right;">Wt:{z.get('weight',0)}</span><br>
                    <span style="font-size:0.8em;color:#9ca3af;">{action} | {roles_str}</span>
                </div>""", unsafe_allow_html=True)

    with right:
        # ---- LEVEL MAP ----
        st.subheader("📍 Level Map")
        if zones and cp:
            _cp_shown = False
            for z in sorted(zones, key=lambda x: -x["price"]):
                dist = z["price"] - cp
                if abs(dist) > 100:
                    continue

                if not _cp_shown and z["price"] < cp:
                    st.markdown(f'<div style="background:#fbbf24;color:#000;text-align:center;padding:6px;border-radius:4px;font-weight:bold;">&#9654; CURRENT: {cp:.0f}</div>', unsafe_allow_html=True)
                    _cp_shown = True

                n_stars = zone_stars(z)
                css = "zone-hot" if n_stars >= 4 else ("zone-warm" if n_stars >= 3 else "zone-cold")
                roles = " | ".join([f"{s}:{r}" for s, r in z.get("roles", [])])
                star_display = "\u2B50" * n_stars
                st.markdown(f'<div class="{css}"><b>{z["price"]:.0f}</b> {star_display} Wt:{z.get("weight",0)}<br><span style="font-size:0.8em;color:#9ca3af;">{roles}</span></div>', unsafe_allow_html=True)

            if not _cp_shown:
                st.markdown(f'<div style="background:#fbbf24;color:#000;text-align:center;padding:6px;border-radius:4px;font-weight:bold;">&#9654; CURRENT: {cp:.0f}</div>', unsafe_allow_html=True)
        else:
            st.info("Levels will appear once the session is active.")

        # ---- RULES ----
        st.text("")
        st.subheader("📏 Rules")
        st.markdown(f"""
        - **Min score ORB**: {orb_min_score} | **Set**: 7 | **Jay**: always eligible
        - **BB regime**: {bb_regime} -- ORB {bb_orb_signal}
        - **Accounts active**: {n_active} (score {total})
        - ORB: Mon-Fri 7:30-9:00 MT (Mon/Wed need score 5+, TuThFr need 4+)
        - Set trade: HIGH conviction + score 7+ only
        - Jay trade: Scored deployment only
        - Max 2 trades before 9:00, 3 total/day
        - Daily loss: 2 stops = done for the day
        - EOD flatten by 13:55 MT
        """)

    # Auto-refresh
    st.caption("Auto-refreshes every 30 seconds. Data updates whenever inputs change on the main dashboard.")


# ============================================================
# TAB 2: MY ACCOUNTS
# ============================================================
with tab_accounts:
    st.title("💼 My Accounts")
    st.caption("Add your prop/eval accounts to get personalized deployment recommendations on each trade idea.")

    # Add account form
    with st.expander("➕ Add Account", expanded=len(st.session_state.user_accounts) == 0):
        with st.form("add_account", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                acct_name = st.text_input("Account Name", placeholder="e.g. Tradeify 150K #1")
            with c2:
                provider = st.selectbox("Provider", ["Tradeify", "TopStepX", "Apex", "Other"])
            with c3:
                dd_remaining = st.number_input("Drawdown Remaining ($)", min_value=0, max_value=50000, step=100, value=2000)
            add_clicked = st.form_submit_button("Add Account", type="primary")
            if add_clicked and acct_name:
                st.session_state.user_accounts.append({
                    "name": acct_name,
                    "provider": provider,
                    "dd_remaining": dd_remaining,
                })
                st.rerun()

    if not st.session_state.user_accounts:
        st.info("Add your accounts above to see deployment recommendations in each trade idea.")
    else:
        st.markdown("### Your Accounts")
        for i, acct in enumerate(st.session_state.user_accounts):
            dd = acct["dd_remaining"]
            icon = {"Tradeify": "🟠", "TopStepX": "🔵", "Apex": "🟣"}.get(acct.get("provider", ""), "⚪")
            # DD health
            if dd < 200: health = "⛔ FROZEN"
            elif dd < 500: health = "🔴 DANGER"
            elif dd < 1000: health = "⚠️ CAUTION"
            else: health = "✅ HEALTHY"

            c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 1])
            with c1:
                st.markdown(f"**{icon} {acct['name']}**")
            with c2:
                st.markdown(f"{acct.get('provider', '?')}")
            with c3:
                st.markdown(f"${dd:,.0f} DD remaining")
            with c4:
                st.markdown(health)
            with c5:
                if st.button("❌", key=f"rm_{i}"):
                    st.session_state.user_accounts.pop(i)
                    st.rerun()

        st.divider()
        # Summary
        total_dd = sum(a["dd_remaining"] for a in st.session_state.user_accounts)
        healthy = sum(1 for a in st.session_state.user_accounts if a["dd_remaining"] >= 500)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total Accounts", len(st.session_state.user_accounts))
        with c2:
            st.metric("Healthy Accounts", f"{healthy}/{len(st.session_state.user_accounts)}")
        with c3:
            st.metric("Total DD Remaining", f"${total_dd:,.0f}")

        st.markdown("""
        <div style="background:#111827;border:1px solid #1f2937;border-radius:8px;padding:12px;margin-top:8px;font-size:0.85em;color:#9ca3af;">
        <b>How risk is calculated:</b> Each trade idea gets 10% of your remaining DD as the base risk budget,
        then scaled by Score multiplier (8+=100%, 6-7=70%, 4-5=50%, 0-3=30%) and Conviction multiplier
        (High=100%, Med=70%, Low=40%). Accounts below $200 DD are frozen. Below $500 = elite (score 9+) setups only.
        Risk is calculated per account individually, so accounts with less DD get proportionally smaller risk.
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# TAB 3: HOW IT WORKS
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
<div class="how-header">Scoring System: 0-12 Points</div>

The total score determines whether we trade, how many accounts we deploy, and how aggressively we size.

| Component | Max Points | What It Measures |
|-----------|-----------|-----------------|
| **Set's Bias** | 4 | Discretionary trader's directional call + conviction level |
| **Jay's Bias** | 4 | VP bias (0-2) + DOM sentiment (0-2) |
| **Technicals** | 4 | Bollinger Band regime (0-3) + EMA structure (0-1) |
| **Total** | **12** | Combined confluence score |

**Score Tiers:**
- **9+** = ELITE -- max deployment, highest conviction
- **7-8** = GOOD -- strong setup, deploy confidently
- **4-6** = MINIMUM -- reduced size, fewer accounts
- **0-3** = SKIP -- no trade, sit on hands
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">Risk Allocation: 72/28 Split (Option A)</div>

Every trade idea gets a risk budget based on **Score x Conviction**, then split across providers:

| Bucket | Base Budget | Scaled By |
|--------|-------------|-----------|
| **ORB** | $500 | Score mult x Conviction mult |
| **Set** | $500 | Score mult x Conviction mult |
| **Jay** | $500 | Score mult x Conviction mult |

**Score multiplier:** 8+ = 100% | 6-7 = 70% | 4-5 = 50% | 0-3 = 30%<br>
**Conviction multiplier:** High = 100% | Med = 70% | Low = 40%

**Provider split:** 72% Tradeify / 28% TopStepX (backtested Option A -- 0/8 accounts blown)

Example: Score 8 + High Conviction = $500 total -> $360 Tradeify + $140 TopStepX
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">Set's Bias (0-4 points)</div>

Set (@Adaamset) is an ES futures trader who posts weekly bias updates on Substack with key levels,
plus real-time Discord journal entries during the session.

**How he scores:**
- Base: conviction level (High=2, Med=1, Low=0)
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

**Set trade eligibility:** Take unless conviction is "low" -- very permissive gate.
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">Jay's Bias (0-4 points)</div>

Jay is a second discretionary futures trader who reads Volume Profiles pre-market and watches
the DOM (Depth of Market) intraday for sentiment shifts. He provides exact entry levels.

**Two independent inputs, each scored 0-2:**

| Input | What It Is | Scoring |
|-------|-----------|---------|
| **VP Bias** | Pre-market Volume Profile read (Bull/Bear/Balance/Neutral) | High=2, Med=1, Low=0 |
| **DOM Sentiment** | Intraday DOM read, can confirm or shift his bias | High=2, Med=1, Low=0 |

**Why Jay is always eligible:** Unlike Set trades, Jay's scalp trades are
always shown when he has a directional call with any conviction. His style is fast in/out scalps
at specific levels, which work independently of the broader confluence picture.
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">Technicals: Bollinger Band Regime (0-3 points)</div>

We classify the 1-hour ES Bollinger Bands into a **5-state regime** based on width and trend direction.
Calibrated against real data: TRENDING >= 0.75% width, NORMAL >= 0.40%, SQUEEZE < 0.40%.

| Regime | Signal | Score | What It Means |
|--------|--------|-------|--------------|
| **SQUEEZE** | GO | 3 | Coiling for a breakout |
| **BREAKOUT** | GO | 3 | Move is starting |
| **TRENDING** | GO | 3 | Strong momentum |
| **WIDE PULLBACK** | GO | 2 | Prior trend still active |
| **EXHAUSTION** | SKIP | 0 | Chop zone, fade the edges |

**Backtested:** GO regimes produce PF 1.81 (+$107K over 2 years).
EXHAUSTION regime produces PF 0.60 -- a net loser.
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">Technicals: EMA Structure (0-1 point)</div>

| Structure | Condition | Score |
|-----------|-----------|-------|
| **BULL STACK** | EMA 20 > 50 > 200 | +1 |
| **BEAR STACK** | EMA 20 < 50 < 200 | +1 |
| **MIXED** | Any other order | +0 |

**Backtested edge:** Bull Stack trades had PF 2.16 (vs 1.82 baseline). Bull Stack + tight EMA spread
(<43pt between EMA 20 and 200) = PF 2.82, 62.9% WR.
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">Level Map & Star System</div>

All levels from every source get clustered into zones (+/- 8pt). Weight determines stars:

**Weight Hierarchy:**
| Source | Weight |
|--------|--------|
| VP-Y POC | 5 |
| VP-Y VAH/VAL, VP-M POC | 4 |
| VP-M VAH/VAL, VP-W POC, Set Pivot, Plan Bull/Bear Pivot | 3 |
| VP-W VAH/VAL, VP-D POC, Set S/R, Jay Keys, Plan TU/R/S/TD, Prior Day H/L | 2 |
| VP-D VAH/VAL, ON H/L, Set Minor/Targets | 1 |

**Star Rating:** Wt 8+ = 5 stars | Wt 6-7 = 4 stars | Wt 4-5 = 3 stars | Wt 2-3 = 2 stars | Wt 1 = 1 star
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">ORB Strategy (Opening Range Breakout)</div>

The primary automated trade. MNQ 15-min opening range breakout.

**Rules:**
- **Entry**: Break of the 15-min high (long) or low (short) after 7:45 MT
- **Stop**: Opposite side of the range + 4 ticks
- **Targets**: 50% off at 2R, runner at breakeven to 4R or EOD
- **Window**: Must trigger by 9:00 MT or cancel
- **Risk**: $200 max per account (MNQ $2/pt)

**Day eligibility:** TuThFr need score 4+, Mon/Wed need score 5+ (backtested PF 2.17 with elevated threshold).
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="how-section">
<div class="how-header">Risk Management</div>

- **Max 2 trades before 9:00 MT**, 3 total per day
- **2 stops = done for the day** (Daily Loss Limit discipline)
- **EOD flatten by 13:55 MT** -- no overnight risk on intraday trades
- **Round-robin deployment**: each trade rotates to the next account within each provider
- **DD safety**: Accounts below critical DD thresholds get pulled from rotation
</div>
""", unsafe_allow_html=True)

    st.markdown("""
---
*This system combines mechanical execution (ORB) with discretionary trader reads (Set, Jay)
and technical regime filtering (BB, EMA) to find high-probability, well-sized trades.
Every component has been individually backtested against 2+ years of data.*
""")
