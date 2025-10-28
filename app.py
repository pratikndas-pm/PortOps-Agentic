
import gradio as gr, pandas as pd, plotly.express as px

APP = "PortOps Agentic v2"
TAG = "AI Planner + Chat — berth, crane & yard intelligence"

VESSELS = pd.read_csv("data/vessel_schedule.csv")
BERTHS = pd.read_csv("data/berths.csv")
YARD = pd.read_csv("data/yard_blocks.csv")

def list_schedule(date=None):
    df = VESSELS.copy()
    df["eta_dt"] = pd.to_datetime(df["eta"])
    if date:
        d = pd.to_datetime(date); e = d + pd.Timedelta(days=1)
        df = df[(df["eta_dt"]>=d) & (df["eta_dt"]<e)]
    return df.sort_values("eta_dt")[["vessel","imo","service","eta","loa_m","moves"]]

def berth_plan():
    df = VESSELS.copy(); df["eta_dt"] = pd.to_datetime(df["eta"]); df = df.sort_values("eta_dt")
    plan = []; next_free = {b: pd.Timestamp.min for b in BERTHS["berth_id"]}
    for _, v in df.iterrows():
        cands = BERTHS[BERTHS["max_loa_m"]>=float(v["loa_m"])].sort_values("max_loa_m")
        chosen, etb = None, v["eta_dt"]
        for _, b in cands.iterrows():
            if next_free[b["berth_id"]] <= etb: chosen=b; break
        if chosen is None:
            allowed = {k:next_free[k] for k in cands["berth_id"]}
            berth_id = min(allowed, key=allowed.get); etb = allowed[berth_id]
            chosen = BERTHS[BERTHS["berth_id"]==berth_id].iloc[0]
        cranes = int(chosen["cranes"])
        hrs = max(8.0, float(v["moves"])/(cranes*35))
        etd = etb + pd.Timedelta(hours=hrs)
        next_free[chosen["berth_id"]] = etd
        plan.append({"vessel":v["vessel"], "imo":v["imo"], "etb":etb.strftime("%Y-%m-%d %H:%M"),
                     "etd":etd.strftime("%Y-%m-%d %H:%M"), "berth":chosen["berth_id"],
                     "cranes":cranes, "moves":int(v["moves"]), "mph":round(v["moves"]/hrs,1)})
    return pd.DataFrame(plan)

def yard_alloc(total_moves:int=2000):
    demand = total_moves*0.5
    out=[]; rem=demand
    for _, y in YARD.iterrows():
        take = min(y["slots"], rem)
        if take>0: out.append({"block":y["block"], "allocate_slots":int(take), "type":y["type"]}); rem-=take
    if rem>0: out.append({"block":"(overflow)","allocate_slots":int(rem),"type":"IMP"})
    return pd.DataFrame(out)

def crane_for(vessel_name:str):
    plan = berth_plan()
    row = plan[plan["vessel"].str.lower()==str(vessel_name).lower()]
    if row.empty: return f"Couldn't find vessel '{vessel_name}'. Run 'plan' first or check name.", None
    r=row.iloc[0]; hrs = (pd.to_datetime(r["etd"])-pd.to_datetime(r["etb"])).total_seconds()/3600
    msg = f"Assign **{r['cranes']} cranes** to **{r['vessel']}** @ berth **{r['berth']}** for **{r['moves']}** moves (~{hrs:.1f}h, {r['mph']} MPH)."
    return msg, row

def kpis(df):
    if df is None or df.empty: return 0,0,0,0
    return len(df), int(df["moves"].sum()), round(df["mph"].mean(),1), round(df["cranes"].mean(),1)

def bar(plan):
    if plan is None or plan.empty: return px.bar(title="No data")
    fig = px.bar(plan, x="vessel", y="moves", text="cranes", title="Moves per Vessel (text = cranes)")
    fig.update_layout(margin=dict(l=10,r=10,t=40,b=10), paper_bgcolor="#0d1a26", plot_bgcolor="#0d1a26", font_color="#eaf1f7")
    fig.update_traces(textposition="outside")
    return fig

HELP = (
    "You can ask:\n"
    "- `list schedule` (optionally add a date)\n"
    "- `berth plan`\n"
    "- `crane plan MSC AURORA`\n"
    "- `yard plan 3000`\n"
)

def router(message, history):
    msg = message.lower().strip()
    if msg.startswith("help") or msg in {"?", "menu"}: 
        return HELP
    if "list" in msg or "schedule" in msg:
        return list_schedule().to_markdown(index=False)
    if "berth" in msg or "plan" in msg:
        plan = berth_plan()
        v,m, mph, cr = kpis(plan)
        return f"**Berth plan created** — {v} vessels, {m} moves, avg {mph} MPH, {cr} cranes.\n\n" + plan.to_markdown(index=False)
    if "crane" in msg:
        name = msg.replace("crane","").replace("plan","").strip().upper()
        text, _ = crane_for(name)
        return text
    if "yard" in msg:
        import re
        m = re.findall(r"(\d+)", msg)
        tot = int(m[0]) if m else 2000
        return yard_alloc(tot).to_markdown(index=False)
    return "I didn't recognize that. " + HELP

with gr.Blocks(css="assets/style.css", title=APP) as demo:
    gr.HTML(f"<div class='header'><h1>🚢 {APP}</h1><div class='sub'>{TAG}</div></div>")
    with gr.Row():
        with gr.Column(scale=1):
            chat = gr.ChatInterface(fn=router, type='messages', autofocus=True, fill_height=True, description="Try: 'berth plan', 'list schedule', 'crane plan MSC AURORA', 'yard plan 3000'")
        with gr.Column(scale=1):
            with gr.Tab("KPIs & Chart"):
                plan = gr.Dataframe(label="Current plan preview")
                chart = gr.Plot()
                def recalc(_):
                    p = berth_plan()
                    return p, bar(p)
                chat.submit(recalc, [chat.chatbot], [plan, chart])
            with gr.Tab("Vessel Schedule"):
                sched = gr.Dataframe(value=list_schedule(), interactive=False)
            with gr.Tab("Data Schema"):
                gr.Markdown("**vessel_schedule.csv**: imo, vessel, service, loa_m, beam_m, draft_m, eta, moves\n\n**berths.csv**: berth_id, max_loa_m, cranes\n\n**yard_blocks.csv**: block, type, slots")
    gr.HTML("<div class='footer'>© 2025 · Pratik N Das · PortOps Agentic v2</div>")
demo.launch()
