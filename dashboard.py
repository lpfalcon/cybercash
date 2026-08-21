import os
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dash_table, dcc, html
from dotenv import load_dotenv
from pymongo import MongoClient

# --- CONFIGURATION ---
load_dotenv()
app = Dash(__name__)
app.title = "CyberCash AI Sentinel"

# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI")
client: MongoClient = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client.cybercash_db

# --- PALETTE & STYLES (Matching HTML Landing Page) ---
COLOR_BG = "#0B0F19"         # Dark background
COLOR_CARD = "#111827"       # Card background
COLOR_BORDER = "#1F2937"     # Subtle border color
COLOR_TEXT = "#E5E7EB"       # Main body text
COLOR_MUTED = "#9CA3AF"      # Secondary text
COLOR_NEON_GREEN = "#00FF9D" # Success / Fast Path / Low Risk
COLOR_NEON_RED = "#FF3366"   # Threat / Bot / High Risk
COLOR_BLUE = "#3B82F6"       # Inbound / Neutral
COLOR_ORANGE = "#F59E0B"     # Moderate Risk

CARD_STYLE = {
    "backgroundColor": COLOR_CARD,
    "borderRadius": "8px",
    "padding": "20px",
    "boxShadow": "0 10px 15px -3px rgba(0, 0, 0, 0.5)",
    "flex": "1",
    "minWidth": "200px",
    "textAlign": "center",
    "border": f"1px solid {COLOR_BORDER}"
}

# Inject Inter / System Font CDN
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    </head>
    <body style="margin: 0; background-color: #0B0F19;">
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# --- LAYOUT ---
app.layout = html.Div(
    style={
        "backgroundColor": COLOR_BG,
        "color": COLOR_TEXT,
        "padding": "40px 20px",
        "fontFamily": "'Inter', system-ui, -apple-system, sans-serif",
        "minHeight": "100vh",
        "maxWidth": "1280px",
        "margin": "0 auto"
    },
    children=[
        # Header Section
        html.Div([
            html.H1([
                "🛡️ CyberCash",
                html.Span("AI", style={"color": COLOR_NEON_GREEN})
            ], style={"textAlign": "center", "color": "#FFFFFF", "fontWeight": "800", "fontSize": "32px", "marginBottom": "8px", "letterSpacing": "-0.025em"}),
            html.P("Real-time Adaptive Risk Analysis & PoW Mitigation Engine", style={"textAlign": "center", "color": COLOR_MUTED, "fontSize": "16px", "marginTop": "0"}),
        ], style={"marginBottom": "32px"}),

        # Metrics Row
        html.Div(id="live-metrics", style={"display": "flex", "justifyContent": "space-between", "gap": "16px", "marginBottom": "24px", "flexWrap": "wrap"}),

        # Charts Section
        html.Div(
            style={"display": "flex", "gap": "20px", "flexWrap": "wrap"},
            children=[
                # Timeline Chart (~70% width)
                html.Div(
                    dcc.Graph(id="timeline-chart", config={'displayModeBar': False}), 
                    style={"flex": "7", "minWidth": "500px", "backgroundColor": COLOR_CARD, "borderRadius": "8px", "padding": "16px", "border": f"1px solid {COLOR_BORDER}"}
                ),
                
                # Pie Chart (~30% width)
                html.Div(
                    dcc.Graph(id="pie-chart", config={'displayModeBar': False}), 
                    style={"flex": "3", "minWidth": "300px", "backgroundColor": COLOR_CARD, "borderRadius": "8px", "padding": "16px", "border": f"1px solid {COLOR_BORDER}"}
                ),
            ],
        ),

        html.Br(),
        
        # Threat Intelligence Table
        html.Div([
            html.H3("🕵️ Threat Intelligence: Top Suspicious Entities", style={"color": "#FFFFFF", "marginTop": "0", "fontWeight": "700", "fontSize": "20px"}),
            html.P("Real-time identification of IPs attempting brute-force or DDoS behavior.", style={"color": COLOR_MUTED, "fontSize": "14px", "marginBottom": "16px"}),
            html.Div(id="threat-table", style={"borderRadius": "8px", "overflow": "hidden", "border": f"1px solid {COLOR_BORDER}"}),
        ], style={"backgroundColor": COLOR_CARD, "padding": "24px", "borderRadius": "8px", "border": f"1px solid {COLOR_BORDER}"}),

        # Auto-refresh interval (10 seconds)
        dcc.Interval(id="interval-component", interval=10 * 1000, n_intervals=0),
    ],
)


# --- CALLBACKS ---
@app.callback(
    [
        Output("live-metrics", "children"),
        Output("timeline-chart", "figure"),
        Output("pie-chart", "figure"),
        Output("threat-table", "children"),
    ],
    [Input("interval-component", "n_intervals")],
)
def update_dashboard(n):
    try:
        cursor = db.audit_logs.find().sort("timestamp", -1).limit(3000)
        df = pd.DataFrame(list(cursor))
    except Exception as e:
        print(f"Database error: {e}")
        return [html.H3("⚠️ Database Connection Error", style={"color": COLOR_NEON_RED})], {}, {}, html.P(str(e))

    if df.empty:
        return [html.H3("Awaiting System Logs...", style={"color": COLOR_MUTED})], {}, {}, html.P("No active threats recorded yet.", style={"color": COLOR_MUTED})

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # 1. Calculation of Metrics
    total_events = len(df)
    critical_cases = len(df[df["difficulty"] >= 6])
    unique_ips = df["ip"].nunique()
    
    failed_pows = len(df[df["event"] == "FAILED_POW"])
    total_challenges = len(df[df["event"].isin(["SUCCESS", "FAILED_POW"])])
    fail_rate = (failed_pows / total_challenges * 100) if total_challenges > 0 else 0

    metrics = [
        html.Div([
            html.H4("Total Events", style={"color": COLOR_MUTED, "margin": "0 0 8px 0", "fontSize": "13px", "fontWeight": "600", "textTransform": "uppercase"}),
            html.H2(f"{total_events:,}", style={"margin": "0", "color": "#FFFFFF", "fontSize": "28px", "fontWeight": "700"})
        ], style=CARD_STYLE),
        html.Div([
            html.H4("AI Escalations (Dif 6-8)", style={"color": COLOR_MUTED, "margin": "0 0 8px 0", "fontSize": "13px", "fontWeight": "600", "textTransform": "uppercase"}),
            html.H2(critical_cases, style={"margin": "0", "color": COLOR_ORANGE, "fontSize": "28px", "fontWeight": "700"})
        ], style=CARD_STYLE),
        html.Div([
            html.H4("Unique Attacker IPs", style={"color": COLOR_MUTED, "margin": "0 0 8px 0", "fontSize": "13px", "fontWeight": "600", "textTransform": "uppercase"}),
            html.H2(unique_ips, style={"margin": "0", "color": COLOR_NEON_RED, "fontSize": "28px", "fontWeight": "700"})
        ], style=CARD_STYLE),
        html.Div([
            html.H4("Global PoW Fail Rate", style={"color": COLOR_MUTED, "margin": "0 0 8px 0", "fontSize": "13px", "fontWeight": "600", "textTransform": "uppercase"}),
            html.H2(f"{fail_rate:.1f}%", style={"margin": "0", "color": COLOR_NEON_GREEN, "fontSize": "28px", "fontWeight": "700"})
        ], style=CARD_STYLE),
    ]

    # 2. Advanced Timeline Logic
    event_map = {
        'CHALLENGE_REQUESTED': 'Inbound Requests',
        'FAILED_POW': 'Failed Challenges (Bots)',
        'SUCCESS': 'Authorized (Humans)'
    }
    
    timeline_frames = []
    for event_code, label in event_map.items():
        subset = df[df['event'] == event_code].copy()
        if not subset.empty:
            resampled = subset.set_index('timestamp').resample('1min').count()['event'].reset_index()
            resampled['Category'] = label
            timeline_frames.append(resampled)
    
    if timeline_frames:
        plot_df = pd.concat(timeline_frames)
        fig_time = px.area(
            plot_df, x="timestamp", y="event", color="Category",
            title="System Traffic Volume & Resolution",
            template="plotly_dark",
            color_discrete_map={
                'Inbound Requests': COLOR_BLUE,
                'Failed Challenges (Bots)': COLOR_NEON_RED,
                'Authorized (Humans)': COLOR_NEON_GREEN
            }
        )
        fig_time.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", 
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", color=COLOR_MUTED),
            title=dict(font=dict(color="#FFFFFF", size=16, family="Inter, sans-serif")),
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis=dict(gridcolor=COLOR_BORDER, showgrid=True),
            yaxis=dict(gridcolor=COLOR_BORDER, showgrid=True, title="Requests / min"),
            legend=dict(orientation="h", y=-0.2)
        )
    else:
        fig_time = {}

    # 3. Pie Chart (Decision Distribution)
    df['Risk Level'] = df['difficulty'].map({4: 'Low (4)', 6: 'Moderate (6)', 8: 'Critical (8)'})
    
    fig_pie = px.pie(
        df, names="Risk Level", title="AI Assigned Difficulty",
        hole=0.6, template="plotly_dark",
        color="Risk Level",
        color_discrete_map={
            'Low (4)': COLOR_NEON_GREEN, 
            'Moderate (6)': COLOR_ORANGE, 
            'Critical (8)': COLOR_NEON_RED
        },
    )
    fig_pie.update_traces(textinfo='percent+label', textposition='inside')
    fig_pie.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", 
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=COLOR_MUTED),
        title=dict(font=dict(color="#FFFFFF", size=16, family="Inter, sans-serif")),
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=20)
    )

    # 4. Threat Table
    threats = df.groupby("ip").agg(
        Requests=("event", "count"),
        Failed_PoW=("event", lambda x: (x == "FAILED_POW").sum()),
        Max_Difficulty=("difficulty", "max")
    ).reset_index().sort_values(by="Requests", ascending=False).head(10)
    
    threats = threats.rename(columns={"ip": "Source IP", "Requests": "Total Requests", "Failed_PoW": "Failed Attempts", "Max_Difficulty": "Highest PoW Applied"})

    table = dash_table.DataTable(
        data=threats.to_dict("records"),
        columns=[{"name": i, "id": i} for i in threats.columns],
        style_header={
            "backgroundColor": "#1F2937", 
            "color": "#FFFFFF", 
            "fontWeight": "600", 
            "border": "none",
            "padding": "12px",
            "fontFamily": "Inter, sans-serif"
        },
        style_cell={
            "backgroundColor": COLOR_CARD, 
            "color": COLOR_TEXT, 
            "textAlign": "left", 
            "padding": "12px", 
            "border": f"1px solid {COLOR_BORDER}",
            "fontFamily": "Inter, sans-serif",
            "fontSize": "14px"
        },
        style_data_conditional=[
            {
                "if": {"filter_query": "{Highest PoW Applied} >= 8"},
                "backgroundColor": "rgba(255, 51, 102, 0.12)",
                "color": COLOR_NEON_RED,
                "fontWeight": "600"
            }
        ],
    )

    return metrics, fig_time, fig_pie, table


if __name__ == "__main__":
    print("------------------------------------------")
    print("🛡️ CyberCash Enterprise Dashboard starting...")
    print("Access locally: http://127.0.0.1:8050")
    print("------------------------------------------")
    app.run(debug=True)