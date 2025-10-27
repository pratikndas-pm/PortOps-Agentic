
import gradio as gr, pandas as pd, plotly.express as px
from pandas import Timedelta

APP_NAME = "PortOps Agentic"
TAGLINE = "Autonomous Terminal Intelligence — berth, crane & yard planning"

VESSELS = pd.read_csv("data/vessel_schedule.csv")
BERTHS = pd.read_csv("data/berths.csv")
YARDS = pd.read_csv("data/yard_blocks.csv")

def tool_list_vessels(date_str=None):
    df = VESSELS.copy()
    if date_str:
        try:
            date = pd.to_datetime(date_str)
            end = date + Timedelta(days=1)
            df = df[(pd.to_datetime(df['eta'])>=date) & (pd.to_datetime(df['eta'])<end)]
        except Exception:
            pass
    return df

def tool_berth_plan():
    df = VESSELS.copy()
    df['eta_dt'] = pd.to_datetime(df['eta'])
    df = df.sort_values('eta_dt')
    plan = []
    berth_next_free = {b: pd.Timestamp.min for b in BERTHS['berth_id']}
    for _, row in df.iterrows():
        candidates = BERTHS[BERTHS['max_loa_m'] >= float(row['loa_m'])].sort_values('max_loa_m')
        chosen, etb = None, row['eta_dt']
        for _, b in candidates.iterrows():
            if berth_next_free[b['berth_id']] <= etb:
                chosen = b; break
        if chosen is None:
            allowed = {k:v for k,v in berth_next_free.items() if k in list(candidates['berth_id'])}
            berth_id = min(allowed, key=allowed.get)
            etb = allowed[berth_id]
            chosen = BERTHS[BERTHS['berth_id']==berth_id].iloc[0]
        cranes = int(chosen['cranes'])
        hrs = max(8.0, float(row['moves'])/(cranes*35))
        etd = etb + pd.Timedelta(hours=hrs)
        berth_next_free[chosen['berth_id']] = etd
        plan.append({
            "vessel": row['vessel'],
            "imo": row['imo'],
            "etb": etb.strftime("%Y-%m-%d %H:%M"),
            "etd": etd.strftime("%Y-%m-%d %H:%M"),
            "berth": chosen['berth_id'],
            "cranes": cranes,
            "moves": int(row['moves']),
            "gross_prod_mph": round(row['moves']/hrs,1)
        })
    return pd.DataFrame(plan)

def tool_crane_allocation(vessel_name):
    plan = tool_berth_plan()
    row = plan[plan['vessel'].str.lower()==str(vessel_name).lower()]
    if row.empty:
        return f"No vessel named '{vessel_name}' in plan.", None
    r = row.iloc[0]
    hrs = (pd.to_datetime(r['etd']) - pd.to_datetime(r['etb'])).total_seconds()/3600
    msg = f"Assign {r['cranes']} quay cranes to {r['vessel']} @ berth {r['berth']} for {r['moves']} moves in ~{hrs:.1f}h (≈{r['gross_prod_mph']} MPH)."
    return msg, row

def tool_yard_plan(total_moves:int):
    demand = total_moves * 0.5
    alloc, remaining = [], demand
    for _, blk in YARDS.iterrows():
        take = min(blk['slots'], remaining)
        if take>0:
            alloc.append({"block": blk['block'], "allocate_slots": int(take)})
            remaining -= take
    if remaining>0:
        alloc.append({"block":"(overflow)", "allocate_slots": int(remaining)})
    return pd.DataFrame(alloc)

def compute_kpis(plan: pd.DataFrame):
    if plan is None or plan.empty:
        return 0, 0, 0.0, 0.0
    total_vessels = len(plan)
    total_moves = int(plan['moves'].sum())
    avg_mph = round(plan['gross_prod_mph'].mean(), 1)
    avg_cranes = round(plan['cranes'].mean(), 1)
    return total_vessels, total_moves, avg_mph, avg_cranes

def crane_chart(plan: pd.DataFrame):
    if plan is None or plan.empty:
        return px.bar(title="No data")
    fig = px.bar(plan, x="vessel", y="moves", text="cranes", title="Moves per Vessel (text = cranes)")
    fig.update_layout(margin=dict(l=10,r=10,t=40,b=10), paper_bgcolor="#0d1a26", plot_bgcolor="#0d1a26", font_color="#eaf1f7")
    fig.update_traces(textposition="outside")
    return fig

def agent(query, date=None, vessel=None, moves=None):
    q = (query or "").lower().strip()
    if "list" in q or "schedule" in q or "eta" in q:
        df = tool_list_vessels(date); msg = "Vessel schedule:"
    elif "berth" in q or "plan" in q:
        df = tool_berth_plan(); msg = "Berth plan generated."
    elif "crane" in q and vessel:
        msg, df = tool_crane_allocation(vessel)
    elif "yard" in q or "storage" in q:
        m = int(moves) if moves else 2000
        df = tool_yard_plan(m); msg = f"Yard allocation for ~{m} import moves:"
    else:
        return "Try: 'list schedule', 'berth plan', 'crane plan' (with vessel), or 'yard plan' (with moves).", None, None, None, None, None
    plan = df if isinstance(df, pd.DataFrame) and 'moves' in df.columns else None
    tv, tm, mph, cranes = compute_kpis(plan)
    chart = crane_chart(plan) if plan is not None else None
    return msg, df, tv, tm, mph, cranes, chart

EXAMPLE_TABLE = '''
<div class="card table-md">
<h3>🧪 Test Data</h3>
<table>
  <thead><tr><th>Use case</th><th>Inputs</th><th>Expected</th></tr></thead>
  <tbody>
    <tr><td>Berth plan</td><td><span class="badge">Query</span> berth plan</td><td>ETB/ETD, berth, cranes, MPH</td></tr>
    <tr><td>List schedule</td><td><span class="badge">Query</span> list schedule</td><td>Upcoming vessels by ETA</td></tr>
    <tr><td>Crane plan</td><td><span class="badge">Query</span> crane plan<br/><span class="badge">Vessel</span> MSC AURORA</td><td>Crane count + service time</td></tr>
    <tr><td>Yard plan</td><td><span class="badge">Query</span> yard plan<br/><span class="badge">Moves</span> 3000</td><td>Block allocation</td></tr>
  </tbody>
</table>
</div>
'''

EXAMPLES = [
    ["berth plan", "", "", 2000],
    ["list schedule", "", "", 2000],
    ["crane plan", "", "MSC AURORA", 2000],
    ["yard plan", "", "", 3000]
]

with gr.Blocks(css="assets/style.css", title=f"{APP_NAME}") as demo:
    gr.HTML(f"<div class='header'><h1>🚢 {APP_NAME}</h1><p class='typing'>{TAGLINE}</p></div>")

    with gr.Row(elem_classes=["grid"]):
        with gr.Column(scale=1):
            with gr.Box(elem_classes=["card"]):
                gr.Markdown("### ✨ Ask the Agent")
                q = gr.Textbox(label="Query", value="berth plan", placeholder="berth plan / list schedule / crane plan / yard plan")
                date = gr.Textbox(label="Date (YYYY-MM-DD)", placeholder="optional")
                vessel = gr.Textbox(label="Vessel (for crane plan)", placeholder="e.g., MSC AURORA")
                moves = gr.Number(label="Moves (for yard plan)", value=2000)
                go = gr.Button("Run Agent")

            with gr.Box(elem_classes=["card"]):
                out_title = gr.Markdown(elem_id="output_title")
                out_df = gr.Dataframe(wrap=True, interactive=False)

                with gr.Row(elem_classes=["kpis"]):
                    kpi1 = gr.Markdown()
                    kpi2 = gr.Markdown()
                    kpi3 = gr.Markdown()
                    kpi4 = gr.Markdown()

                chart = gr.Plot(label="Workload Chart")

            def render_kpi(label, value, cls="ok"):
                return f"<div class='kpi {cls}'><div class='label'>{label}</div><div class='value'>{value}</div></div>"

            def update(*args):
                msg, df, tv, tm, mph, cranes, fig = agent(*args)
                k1 = render_kpi("Vessels planned", tv, "ok" if tv>0 else "warn")
                k2 = render_kpi("Total moves", tm, "ok" if tm>0 else "warn")
                k3 = render_kpi("Avg MPH", mph, "ok" if mph>=30 else "warn")
                k4 = render_kpi("Avg cranes", cranes, "ok" if cranes>=3 else "warn")
                return msg, df, k1, k2, k3, k4, fig

            go.click(update, inputs=[q, date, vessel, moves], outputs=[out_title, out_df, kpi1, kpi2, kpi3, kpi4, chart])

        with gr.Column(scale=0, min_width=380):
            with gr.Box(elem_classes=["card","sidebar"]):
                with gr.Tabs(elem_classes=["tabs"]):
                    with gr.Tab("Examples"):
                        gr.Markdown("### 📋 Quick Examples")
                        gr.Examples(EXAMPLES, inputs=[q, date, vessel, moves], label="Click to fill")
                    with gr.Tab("Test Data"):
                        gr.HTML(EXAMPLE_TABLE)
                    with gr.Tab("Data Schema"):
                        gr.Markdown("**vessel_schedule.csv**: `imo, vessel, loa_m, beam_m, draft_m, eta, etb_window_h, moves`\n\n**berths.csv**: `berth_id, max_loa_m, cranes`\n\n**yard_blocks.csv**: `block, slots`")
                gr.Markdown("<p class='small'>Swap CSVs in <code>/data</code> to run your own scenarios.</p>")

    gr.HTML("<div class='footer'>© 2025 · Pratik N Das · PortOps Agentic</div>")

demo.launch()
