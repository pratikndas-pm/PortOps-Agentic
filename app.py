
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
st.set_page_config(page_title="PortOps Agentic — Streamlit", page_icon="🚢", layout="wide")
with open("assets/theme.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
@st.cache_data
def load_data():
    V = pd.read_csv("data/vessel_schedule.csv")
    B = pd.read_csv("data/berths.csv")
    Y = pd.read_csv("data/yard_blocks.csv")
    V["eta_dt"] = pd.to_datetime(V["eta"])
    return V, B, Y
def berth_plan(V, B):
    V = V.sort_values("eta_dt").copy()
    plan=[]; next_free={b: pd.Timestamp.min for b in B["berth_id"]}
    for _, v in V.iterrows():
        cands = B[B["max_loa_m"]>=float(v["loa_m"])].sort_values("max_loa_m")
        chosen, etb = None, v["eta_dt"]
        for _, b in cands.iterrows():
            if next_free[b["berth_id"]] <= etb: chosen=b; break
        if chosen is None and not cands.empty:
            waits = {k: next_free[k] for k in cands["berth_id"]}
            berth_id = min(waits, key=waits.get)
            chosen = B[B["berth_id"]==berth_id].iloc[0]
            etb = waits[berth_id]
        if chosen is None: continue
        cranes = int(chosen["cranes"])
        hrs = max(8.0, float(v["moves"])/(cranes*35))
        etd = etb + pd.Timedelta(hours=hrs)
        next_free[chosen["berth_id"]] = etd
        plan.append({"vessel":v["vessel"],"imo":v["imo"],"etb":etb.strftime("%Y-%m-%d %H:%M"),
                     "etd":etd.strftime("%Y-%m-%d %H:%M"),"berth":chosen["berth_id"],
                     "cranes":cranes,"moves":int(v["moves"]),"mph":round(v["moves"]/hrs,1)})
    return pd.DataFrame(plan)
def yard_alloc(Y, total_moves=2000):
    demand = total_moves*0.5
    out=[]; rem=demand
    for _, y in Y.iterrows():
        take=min(y["slots"], rem)
        if take>0:
            out.append({"block":y["block"], "allocate_slots":int(take), "type":y["type"]})
            rem-=take
    if rem>0: out.append({"block":"(overflow)","allocate_slots":int(rem),"type":"IMP"})
    return pd.DataFrame(out)
def kpis(df):
    if df is None or df.empty: return 0,0,0,0
    return len(df), int(df["moves"].sum()), round(df["mph"].mean(),1), round(df["cranes"].mean(),1)
st.markdown("<h2>🚢 PortOps Agentic — Streamlit</h2><p style='color:#9ad6cd'>Agentic planner: berth, cranes & yard — polished, no backend.</p>", unsafe_allow_html=True)
V,B,Y = load_data()
left, right = st.columns([7,5])
with left:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    query = st.text_input("Ask the Agent (try: 'berth plan', 'list schedule', 'yard plan 3000')", "berth plan")
    run = st.button("Run")
    st.markdown("</div>", unsafe_allow_html=True)
    if run or query:
        txt = query.lower().strip()
        if "list" in txt or "schedule" in txt:
            st.markdown("### Upcoming Schedule")
            st.dataframe(V.sort_values("eta_dt")[["vessel","imo","eta","loa_m","moves"]], use_container_width=True)
        elif "yard" in txt and "plan" in txt:
            import re
            nums = re.findall(r"(\d+)", txt); tot = int(nums[0]) if nums else 2000
            alloc = yard_alloc(Y, tot)
            st.markdown(f"### Yard Allocation for {tot} moves")
            st.dataframe(alloc, use_container_width=True)
        else:
            plan = berth_plan(V, B)
            v,m,mph,cr = kpis(plan)
            st.markdown(f"### Berth Plan — {v} vessels • {m} moves • avg {mph} MPH • {cr} cranes")
            st.dataframe(plan, use_container_width=True)
            fig = px.bar(plan, x="vessel", y="moves", text="cranes", title="Moves per Vessel (text = cranes)")
            fig.update_layout(margin=dict(l=10,r=10,t=40,b=10), paper_bgcolor="#0d1a26", plot_bgcolor="#0d1a26", font_color="#eaf1f7")
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True, theme=None)
with right:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("#### Examples")
    st.write("• **berth plan** — compute ETB/ETD, cranes")
    st.write("• **list schedule** — upcoming vessels")
    st.write("• **yard plan 3000** — allocate yard slots")
    st.markdown("---")
    st.markdown("#### Test Data")
    test = pd.DataFrame([
        {"Case":"Berth plan","Input":"berth plan","Expected":"ETB/ETD, berth, cranes, MPH"},
        {"Case":"List schedule","Input":"list schedule","Expected":"ETA-sorted list"},
        {"Case":"Yard plan","Input":"yard plan 3000","Expected":"Slots by block"}
    ])
    st.dataframe(test, use_container_width=True, hide_index=True)
    st.markdown("---")
    st.markdown("#### Data Schema")
    st.write("• `data/vessel_schedule.csv`: vessel, imo, eta, loa_m, moves")
    st.write("• `data/berths.csv`: berth_id, max_loa_m, cranes")
    st.write("• `data/yard_blocks.csv`: block, type, slots")
    st.markdown("</div>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;color:#8aa0af'>© 2025 · Pratik N Das · PortOps Agentic (Streamlit)</p>", unsafe_allow_html=True)
