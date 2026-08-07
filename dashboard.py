import os
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, dash_table, Input, Output
from pymongo import MongoClient
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
app = Dash(__name__)
app.title = "CyberCash AI Sentinel"

# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI")
client:MongoClient  = MongoClient(MONGO_URI)
db = client.cybercash_db

# --- LAYOUT ---
app.layout = html.Div(
    style={
        "backgroundColor": "#0b0b0b",
        "color": "#ffffff",
        "padding": "30px",
        "fontFamily": "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
    },
    children=[
        # Header Section
        html.Div([
            html.H1("🛡️ CyberCash AI Sentinel", style={"textAlign": "center", "color": "#AB63FA", "marginBottom": "5px"}),
            html.P("Real-time Adaptive Risk Analysis & PoW Mitigation Engine", style={"textAlign": "center", "color": "#888", "fontSize": "18px"}),
        ], style={"marginBottom": "40px"}),

        # Metrics Row
        html.Div(id="live-metrics", style={"display": "flex", "justifyContent": "space-around", "marginBottom": "40px"}),

        # Charts Section
        html.Div(
            style={"display": "flex", "gap": "25px", "flexWrap": "wrap"},
            children=[
                # Timeline Chart (Takes 70% width)
                html.Div(dcc.Graph(id="timeline-chart"), style={"flex": "2", "minWidth": "600px", "backgroundColor": "#151515", "borderRadius": "10px", "padding": "10px"}),
                # Pie Chart (Takes 30% width)
                html.Div(dcc.Graph(id="pie-chart"), style={"flex": "1", "minWidth": "300px", "backgroundColor": "#151515", "borderRadius": "10px", "padding": "10px"}),
            ],
        ),

        html.Br(),
        html.Hr(style={"borderColor": "#333"}),
        
        # Threat Intelligence Table
        html.Div([
            html.H3("🕵️ Threat Intelligence: Top Suspicious Entities", style={"color": "#EF553B", "marginTop": "20px"}),
            html.P("Real-time identification of fingerprints attempting IP-spoofing or Botnet behavior.", style={"color": "#666"}),
            html.Div(id="threat-table", style={"marginTop": "15px"}),
        ]),

        # Auto-refresh interval (Set to 10 seconds)
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
    # Fetch Data from MongoDB
    cursor = db.audit_logs.find().sort("timestamp", -1).limit(2000)
    df = pd.DataFrame(list(cursor))

    if df.empty:
        return [html.H3("Awaiting System Logs...", style={"color": "#888"})], {}, {}, html.P("No active threats recorded yet.")

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # 1. Calculation of Top Metrics
    total_events = len(df)
    critical_cases = len(df[df["difficulty"] == 8])
    unique_fingerprints = df["fingerprint"].nunique()

    metrics = [
        html.Div([html.H4("Total Events", style={"color": "#888"}), html.H2(f"{total_events:,}")], style={"textAlign": "center"}),
        html.Div([html.H4("AI Level-8 Escalations", style={"color": "#AB63FA"}), html.H2(critical_cases)], style={"textAlign": "center"}),
        html.Div([html.H4("Identified Threat Actors", style={"color": "#EF553B"}), html.H2(unique_fingerprints)], style={"textAlign": "center"}),
    ]

    # 2. Advanced Timeline Logic (By Event Type)
    # We create a dataframe for each event category
    event_map = {
        'CHALLENGE_REQUESTED': 'Inbound Requests',
        'INVALID_CHALLENGE': 'Blocked Threats',
        'SUCCESS': 'Authorized Access'
    }
    
    timeline_frames = []
    for event_code, label in event_map.items():
        subset = df[df['event'] == event_code].copy()
        if not subset.empty:
            # Resample to 1 minute and count occurrences
            resampled = subset.set_index('timestamp').resample('1min').count()['event'].reset_index()
            resampled['Category'] = label
            timeline_frames.append(resampled)
    
    if timeline_frames:
        plot_df = pd.concat(timeline_frames)
        fig_time = px.line(
            plot_df, x="timestamp", y="event", color="Category",
            title="System Traffic Analysis (Real-time Filtering)",
            template="plotly_dark",
            color_discrete_map={
                'Inbound Requests': '#636EFA', # Blue
                'Blocked Threats': '#EF553B',  # Red
                'Authorized Access': '#00CC96' # Green
            }
        )
    else:
        fig_time = {}

    # 3. Pie Chart (Decision Distribution)
    fig_pie = px.pie(
        df, names="difficulty", title="AI Decision Distribution (PoW Levels)",
        hole=0.4, template="plotly_dark",
        color="difficulty",
        color_discrete_map={4: '#00CC96', 6: '#EF553B', 8: '#AB63FA'},
    )
    fig_pie.update_traces(textinfo='percent+label')

    # 4. Threat Table (Suspect Identification)
    threats = (
        df.groupby("fingerprint")
        .agg({"difficulty": "max", "ip": "nunique", "event": "count"})
        .reset_index()
        .rename(columns={"event": "Requests", "ip": "Unique IPs Used", "difficulty": "Max Difficulty"})
        .sort_values(by="Requests", ascending=False)
        .head(10)
    )

    table = dash_table.DataTable(
        data=threats.to_dict("records"),
        columns=[{"name": i, "id": i} for i in threats.columns],
        style_header={"backgroundColor": "#222", "color": "white", "fontWeight": "bold", "border": "1px solid #444"},
        style_cell={"backgroundColor": "#151515", "color": "#ccc", "textAlign": "left", "padding": "10px", "border": "1px solid #222"},
        style_data_conditional=[
            {
                "if": {"filter_query": "{Requests} > 25"},
                "backgroundColor": "#3d1111",
                "color": "#ffaaaa",
                "fontWeight": "bold"
            }
        ],
    )

    return metrics, fig_time, fig_pie, table


if __name__ == "__main__":
    print("------------------------------------------")
    print("🛡️ CyberCash Dashboard is starting...")
    print("Access locally: http://127.0.0.1:8050")
    print("------------------------------------------")
    app.run(debug=False)