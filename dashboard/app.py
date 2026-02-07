"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    AutoHeal AI - Command Center Dashboard                      ║
║                          "The Operator Experience"                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Enterprise-grade NOC Dashboard for DevOps/SRE teams.
Real-time monitoring, AI analysis, and autonomous healing controls.

Run with: streamlit run app.py
"""

import streamlit as st
import httpx
import time
import random
from datetime import datetime, timedelta
from typing import Optional
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# =============================================================================
# CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="AutoHeal AI - Command Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# API Endpoints
API_CONFIG = {
    "incident_manager": "http://localhost:8002",
    "autoheal_agent": "http://localhost:8003",
    "k8s_executor": "http://localhost:8004",
    "audit_service": "http://localhost:8005"
}

# =============================================================================
# CUSTOM CSS - Dark Mode NOC Style
# =============================================================================

def inject_custom_css():
    st.markdown("""
    <style>
    /* ═══════════════════════════════════════════════════════════════════════
       ROOT VARIABLES - Command Center Color Palette
       ═══════════════════════════════════════════════════════════════════════ */
    :root {
        --bg-primary: #0a0e17;
        --bg-secondary: #111827;
        --bg-card: #1a1f2e;
        --bg-card-hover: #242b3d;
        --border-color: #2d3748;
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --accent-blue: #3b82f6;
        --accent-cyan: #06b6d4;
        --status-healthy: #10b981;
        --status-warning: #f59e0b;
        --status-critical: #ef4444;
        --status-info: #6366f1;
        --glow-blue: 0 0 20px rgba(59, 130, 246, 0.3);
        --glow-green: 0 0 20px rgba(16, 185, 129, 0.3);
        --glow-red: 0 0 20px rgba(239, 68, 68, 0.4);
    }

    /* ═══════════════════════════════════════════════════════════════════════
       GLOBAL STYLES
       ═══════════════════════════════════════════════════════════════════════ */
    .stApp {
        background: linear-gradient(135deg, var(--bg-primary) 0%, #0f172a 100%);
    }
    
    .main .block-container {
        padding: 1rem 2rem;
        max-width: 100%;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: var(--text-primary) !important;
    }
    
    p, span, label {
        color: var(--text-secondary) !important;
    }

    /* ═══════════════════════════════════════════════════════════════════════
       HEADER STYLES
       ═══════════════════════════════════════════════════════════════════════ */
    .header-container {
        background: linear-gradient(90deg, var(--bg-card) 0%, #1e293b 100%);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: var(--glow-blue);
    }
    
    .logo-title {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    .logo-icon {
        font-size: 2.5rem;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.8; transform: scale(1.05); }
    }
    
    .main-title {
        font-size: 1.8rem;
        font-weight: 700;
        background: linear-gradient(90deg, #3b82f6, #06b6d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    
    .sub-title {
        font-size: 0.9rem;
        color: var(--text-muted) !important;
        margin: 0;
    }
    
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        border-radius: 50px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    
    .status-healthy {
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid var(--status-healthy);
        color: var(--status-healthy) !important;
        box-shadow: var(--glow-green);
    }
    
    .status-critical {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid var(--status-critical);
        color: var(--status-critical) !important;
        box-shadow: var(--glow-red);
        animation: blink 1s infinite;
    }
    
    @keyframes blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }

    /* ═══════════════════════════════════════════════════════════════════════
       KPI CARDS
       ═══════════════════════════════════════════════════════════════════════ */
    .kpi-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .kpi-card:hover {
        background: var(--bg-card-hover);
        transform: translateY(-2px);
        box-shadow: var(--glow-blue);
    }
    
    .kpi-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan));
    }
    
    .kpi-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: var(--text-primary) !important;
        line-height: 1.2;
    }
    
    .kpi-label {
        font-size: 0.85rem;
        color: var(--text-muted) !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 0.5rem;
    }
    
    .kpi-trend-up {
        color: var(--status-healthy) !important;
        font-size: 0.8rem;
    }
    
    .kpi-trend-down {
        color: var(--status-critical) !important;
        font-size: 0.8rem;
    }

    /* ═══════════════════════════════════════════════════════════════════════
       INCIDENT FEED
       ═══════════════════════════════════════════════════════════════════════ */
    .incident-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        display: flex;
        align-items: center;
        gap: 1rem;
        transition: all 0.2s ease;
        cursor: pointer;
    }
    
    .incident-card:hover {
        background: var(--bg-card-hover);
        border-color: var(--accent-blue);
    }
    
    .severity-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        flex-shrink: 0;
    }
    
    .severity-critical {
        background: var(--status-critical);
        box-shadow: 0 0 10px var(--status-critical);
    }
    
    .severity-high {
        background: var(--status-warning);
        box-shadow: 0 0 10px var(--status-warning);
    }
    
    .severity-medium {
        background: var(--status-info);
    }
    
    .severity-low {
        background: var(--status-healthy);
    }
    
    .incident-content {
        flex: 1;
    }
    
    .incident-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: var(--text-primary) !important;
        margin-bottom: 0.25rem;
    }
    
    .incident-meta {
        font-size: 0.8rem;
        color: var(--text-muted) !important;
    }

    /* ═══════════════════════════════════════════════════════════════════════
       AI TERMINAL
       ═══════════════════════════════════════════════════════════════════════ */
    .terminal-container {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 12px;
        overflow: hidden;
    }
    
    .terminal-header {
        background: #161b22;
        padding: 0.75rem 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        border-bottom: 1px solid #30363d;
    }
    
    .terminal-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
    }
    
    .terminal-body {
        padding: 1rem;
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        font-size: 0.85rem;
        line-height: 1.6;
        min-height: 200px;
        max-height: 300px;
        overflow-y: auto;
    }
    
    .terminal-line {
        margin-bottom: 0.5rem;
    }
    
    .terminal-prompt {
        color: #58a6ff !important;
    }
    
    .terminal-success {
        color: #3fb950 !important;
    }
    
    .terminal-warning {
        color: #d29922 !important;
    }
    
    .terminal-error {
        color: #f85149 !important;
    }
    
    .terminal-info {
        color: #8b949e !important;
    }

    /* ═══════════════════════════════════════════════════════════════════════
       ACTION BUTTONS
       ═══════════════════════════════════════════════════════════════════════ */
    .action-btn {
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.9rem;
        border: none;
        cursor: pointer;
        transition: all 0.2s ease;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .btn-primary {
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        color: white !important;
    }
    
    .btn-primary:hover {
        transform: translateY(-2px);
        box-shadow: var(--glow-blue);
    }
    
    .btn-success {
        background: linear-gradient(135deg, #10b981, #059669);
        color: white !important;
    }
    
    .btn-warning {
        background: linear-gradient(135deg, #f59e0b, #d97706);
        color: white !important;
    }
    
    .btn-danger {
        background: linear-gradient(135deg, #ef4444, #dc2626);
        color: white !important;
    }

    /* ═══════════════════════════════════════════════════════════════════════
       MODE TOGGLE
       ═══════════════════════════════════════════════════════════════════════ */
    .mode-toggle {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 50px;
        padding: 0.5rem;
        display: inline-flex;
        gap: 0.25rem;
    }
    
    .mode-option {
        padding: 0.5rem 1rem;
        border-radius: 50px;
        font-size: 0.85rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
        color: var(--text-muted) !important;
    }
    
    .mode-option.active {
        background: linear-gradient(135deg, #3b82f6, #06b6d4);
        color: white !important;
    }

    /* ═══════════════════════════════════════════════════════════════════════
       SECTION TITLES
       ═══════════════════════════════════════════════════════════════════════ */
    .section-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text-primary) !important;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .section-title::before {
        content: '';
        width: 4px;
        height: 20px;
        background: linear-gradient(180deg, var(--accent-blue), var(--accent-cyan));
        border-radius: 2px;
    }

    /* ═══════════════════════════════════════════════════════════════════════
       SCROLLBAR
       ═══════════════════════════════════════════════════════════════════════ */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: var(--bg-secondary);
    }
    
    ::-webkit-scrollbar-thumb {
        background: var(--border-color);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-muted);
    }

    /* Hide Streamlit branding */
    #MainMenu, footer, header {
        visibility: hidden;
    }
    
    .stDeployButton {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)


# =============================================================================
# API HELPER FUNCTIONS
# =============================================================================

def fetch_api(endpoint: str, path: str, method: str = "GET", data: dict = None) -> Optional[dict]:
    """Fetch data from API endpoint."""
    try:
        url = f"{API_CONFIG.get(endpoint, '')}{path}"
        with httpx.Client(timeout=5.0) as client:
            if method == "GET":
                response = client.get(url)
            else:
                response = client.post(url, json=data)
            
            if response.status_code == 200 or response.status_code == 201:
                return response.json()
    except Exception as e:
        st.session_state.api_error = str(e)
    return None


def check_health() -> dict:
    """Check health of all services."""
    health = {}
    for service, base_url in API_CONFIG.items():
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(f"{base_url}/health")
                health[service] = resp.status_code == 200
        except:
            health[service] = False
    return health


# =============================================================================
# COMPONENTS
# =============================================================================

def render_header():
    """Render the main header with system status."""
    health = check_health()
    all_healthy = all(health.values())
    healthy_count = sum(health.values())
    
    uptime = st.session_state.get('uptime', datetime.now())
    uptime_delta = datetime.now() - uptime
    uptime_str = f"{uptime_delta.seconds // 3600}h {(uptime_delta.seconds % 3600) // 60}m"
    
    status_class = "status-healthy" if all_healthy else "status-critical"
    status_icon = "✓" if all_healthy else "⚠"
    status_text = f"All Systems Operational ({healthy_count}/4)" if all_healthy else f"Degraded ({healthy_count}/4 Services)"
    
    st.markdown(f"""
    <div class="header-container">
        <div class="logo-title">
            <span class="logo-icon">🛡️</span>
            <div>
                <h1 class="main-title">AutoHeal AI</h1>
                <p class="sub-title">Incident Command Center • Autonomous Infrastructure Healing</p>
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 1.5rem;">
            <div style="text-align: right;">
                <div style="color: #94a3b8; font-size: 0.8rem;">UPTIME</div>
                <div style="color: #f1f5f9; font-size: 1.1rem; font-weight: 600;">{uptime_str}</div>
            </div>
            <div style="text-align: right;">
                <div style="color: #94a3b8; font-size: 0.8rem;">LOCAL TIME</div>
                <div style="color: #f1f5f9; font-size: 1.1rem; font-weight: 600;">{datetime.now().strftime("%H:%M:%S")}</div>
            </div>
            <span class="status-badge {status_class}">
                {status_icon} {status_text}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_kpi_cards():
    """Render the KPI metrics cards."""
    # Fetch data
    incidents_data = fetch_api("incident_manager", "/api/v1/incidents") or {"incidents": [], "total": 0}
    healings_data = fetch_api("autoheal_agent", "/api/v1/stats") or {}
    
    total_incidents = incidents_data.get("total", 0)
    active_incidents = len([i for i in incidents_data.get("incidents", []) if i.get("status") != "resolved"])
    success_rate = healings_data.get("success_rate", 0) * 100
    avg_mttr = healings_data.get("average_duration_seconds", 0)
    total_healings = healings_data.get("total_healings", 0)
    mode = healings_data.get("mode", "auto")
    
    cols = st.columns(5)
    
    kpis = [
        {"value": str(total_incidents), "label": "Total Incidents", "trend": "↑ 12% vs last week", "trend_up": False},
        {"value": str(active_incidents), "label": "Active Incidents", "trend": "Currently monitored", "trend_up": None},
        {"value": f"{avg_mttr:.0f}s", "label": "Avg. MTTR", "trend": "↓ 23% improved", "trend_up": True},
        {"value": f"{success_rate:.0f}%", "label": "Auto-Remediation Rate", "trend": f"{total_healings} total healings", "trend_up": True},
        {"value": mode.upper(), "label": "Healing Mode", "trend": "Click to toggle", "trend_up": None},
    ]
    
    for col, kpi in zip(cols, kpis):
        trend_class = ""
        if kpi["trend_up"] is True:
            trend_class = "kpi-trend-up"
        elif kpi["trend_up"] is False:
            trend_class = "kpi-trend-down"
        
        col.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{kpi["value"]}</div>
            <div class="kpi-label">{kpi["label"]}</div>
            <div class="{trend_class}" style="margin-top: 0.5rem; font-size: 0.75rem;">{kpi["trend"]}</div>
        </div>
        """, unsafe_allow_html=True)


def render_latency_chart():
    """Render real-time latency chart with healing events."""
    st.markdown('<div class="section-title">📈 System Latency & Healing Events</div>', unsafe_allow_html=True)
    
    # Generate mock data for demo
    if 'latency_data' not in st.session_state:
        st.session_state.latency_data = []
        st.session_state.healing_events = []
    
    # Simulate new data point
    now = datetime.now()
    base_latency = 50
    
    # Simulate spike and recovery
    time_seconds = now.second + now.minute * 60
    if 20 <= time_seconds % 60 <= 35:  # Spike period
        latency = base_latency + random.uniform(100, 200)
    elif 36 <= time_seconds % 60 <= 40:  # Recovery period
        latency = base_latency + random.uniform(30, 80)
    else:
        latency = base_latency + random.uniform(-10, 20)
    
    st.session_state.latency_data.append({
        "time": now,
        "latency": latency,
        "threshold": 100
    })
    
    # Keep only last 60 points
    st.session_state.latency_data = st.session_state.latency_data[-60:]
    
    if st.session_state.latency_data:
        df = pd.DataFrame(st.session_state.latency_data)
        
        fig = go.Figure()
        
        # Threshold line
        fig.add_trace(go.Scatter(
            x=df['time'],
            y=df['threshold'],
            mode='lines',
            name='Threshold',
            line=dict(color='#ef4444', width=2, dash='dash'),
            fill=None
        ))
        
        # Latency line
        fig.add_trace(go.Scatter(
            x=df['time'],
            y=df['latency'],
            mode='lines',
            name='Latency (ms)',
            line=dict(color='#3b82f6', width=3),
            fill='tozeroy',
            fillcolor='rgba(59, 130, 246, 0.1)'
        ))
        
        # Style
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(26, 31, 46, 0.8)',
            font=dict(color='#94a3b8'),
            height=250,
            margin=dict(l=40, r=20, t=20, b=40),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            xaxis=dict(
                showgrid=True,
                gridcolor='rgba(45, 55, 72, 0.5)',
                tickformat='%H:%M:%S'
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(45, 55, 72, 0.5)',
                title='ms'
            )
        )
        
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


def render_incident_feed():
    """Render live incident feed."""
    st.markdown('<div class="section-title">🚨 Live Incident Feed</div>', unsafe_allow_html=True)
    
    incidents_data = fetch_api("incident_manager", "/api/v1/incidents") or {"incidents": []}
    incidents = incidents_data.get("incidents", [])
    
    if not incidents:
        st.markdown("""
        <div style="text-align: center; padding: 2rem; color: #64748b;">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">✓</div>
            <div>No active incidents. All systems nominal.</div>
        </div>
        """, unsafe_allow_html=True)
        return
    
    for incident in incidents[:5]:  # Show last 5
        severity = incident.get("severity", "medium")
        severity_class = f"severity-{severity}"
        created_at = incident.get("created_at", "")[:19].replace("T", " ")
        
        st.markdown(f"""
        <div class="incident-card">
            <div class="severity-dot {severity_class}"></div>
            <div class="incident-content">
                <div class="incident-title">{incident.get("title", "Unknown Incident")}</div>
                <div class="incident-meta">
                    {incident.get("target_service", "N/A")} • {created_at} • 
                    <span style="color: #3b82f6;">ID: {incident.get("incident_id", "")[:8]}...</span>
                </div>
            </div>
            <div style="text-transform: uppercase; font-size: 0.75rem; padding: 0.25rem 0.75rem; 
                        border-radius: 4px; background: rgba(99, 102, 241, 0.2); color: #818cf8;">
                {incident.get("status", "new")}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button(f"🔍 Analyze", key=f"analyze_{incident.get('incident_id')}"):
            st.session_state.selected_incident = incident


def render_ai_terminal():
    """Render AI Analysis Terminal."""
    st.markdown('<div class="section-title">🤖 AI Reasoning Terminal</div>', unsafe_allow_html=True)
    
    # Get healing history for terminal output
    history_data = fetch_api("autoheal_agent", "/api/v1/history") or {"healings": []}
    healings = history_data.get("healings", [])
    
    terminal_lines = [
        ("prompt", "$ autoheal-agent --status"),
        ("info", f"[{datetime.now().strftime('%H:%M:%S')}] OODA Engine initialized"),
        ("success", "[OBSERVE] Monitoring 4 services across production namespace"),
    ]
    
    if healings:
        latest = healings[0]
        plan = latest.get("plan", {})
        
        terminal_lines.extend([
            ("warning", f"[ALERT] Incident detected: {latest.get('incident_id', 'N/A')[:12]}..."),
            ("prompt", "$ analyzing-root-cause..."),
            ("info", f"[ORIENT] {plan.get('orientation', 'Analyzing patterns...')}"),
            ("success", f"[DECIDE] {plan.get('decision', 'Generating healing plan...')}"),
        ])
        
        for action in plan.get("actions", [])[:2]:
            terminal_lines.append(
                ("success", f"[ACT] Executing: {action.get('action_type', 'unknown')} → {action.get('target', 'N/A')}")
            )
        
        if latest.get("status") == "completed":
            terminal_lines.append(("success", f"[✓] Healing completed successfully in {plan.get('estimated_duration_seconds', 0)}s"))
    else:
        terminal_lines.extend([
            ("info", "[IDLE] No active incidents. Continuing observation..."),
            ("info", "[READY] Autonomous healing mode enabled"),
        ])
    
    terminal_html = ""
    for line_type, text in terminal_lines:
        terminal_html += f'<div class="terminal-line terminal-{line_type}">{text}</div>'
    
    st.markdown(f"""
    <div class="terminal-container">
        <div class="terminal-header">
            <div class="terminal-dot" style="background: #ff5f57;"></div>
            <div class="terminal-dot" style="background: #febc2e;"></div>
            <div class="terminal-dot" style="background: #28c840;"></div>
            <span style="margin-left: 0.5rem; color: #8b949e; font-size: 0.8rem;">ai-reasoning-engine</span>
        </div>
        <div class="terminal-body">
            {terminal_html}
            <div class="terminal-line terminal-prompt" style="animation: blink 1s infinite;">▊</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_action_controls():
    """Render action control buttons."""
    st.markdown('<div class="section-title">⚡ Quick Actions</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔄 Restart Pods", use_container_width=True, type="primary"):
            result = fetch_api("k8s_executor", "/api/v1/execute", "POST", {
                "action_id": f"manual-{int(time.time())}",
                "action_type": "restart_pod",
                "target": "production/demo-app",
                "parameters": {}
            })
            if result:
                st.success("✓ Restart initiated")
    
    with col2:
        if st.button("📈 Scale Up", use_container_width=True):
            result = fetch_api("k8s_executor", "/api/v1/execute", "POST", {
                "action_id": f"manual-{int(time.time())}",
                "action_type": "scale_up",
                "target": "production/demo-app",
                "parameters": {"increment": 1}
            })
            if result:
                st.success("✓ Scale-up initiated")
    
    with col3:
        if st.button("⏪ Rollback", use_container_width=True):
            result = fetch_api("k8s_executor", "/api/v1/execute", "POST", {
                "action_id": f"manual-{int(time.time())}",
                "action_type": "rollback",
                "target": "production/demo-app",
                "parameters": {}
            })
            if result:
                st.success("✓ Rollback initiated")
    
    with col4:
        if st.button("🧪 Simulate Incident", use_container_width=True):
            result = fetch_api("incident_manager", "/api/v1/events/anomaly", "POST", {
                "event_id": f"sim-{int(time.time())}",
                "anomaly_type": "error_rate_spike",
                "severity": random.choice(["high", "critical"]),
                "target_service": "demo-service",
                "target_namespace": "production",
                "metric_name": "error_rate",
                "current_value": random.uniform(0.1, 0.3),
                "threshold_value": 0.05
            })
            if result:
                st.success(f"✓ Incident created: {result.get('incident_id', 'N/A')[:8]}...")


def render_mode_toggle():
    """Render healing mode toggle."""
    st.markdown('<div class="section-title">🎛️ Healing Mode</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        mode = st.radio(
            "Select Mode",
            ["Manual", "Semi-Auto", "Autonomous"],
            horizontal=True,
            index=2,
            label_visibility="collapsed"
        )
        
        mode_descriptions = {
            "Manual": "All actions require approval. Full control, no automation.",
            "Semi-Auto": "Low-risk actions auto-execute. High-risk requires approval.",
            "Autonomous": "Full auto-remediation. AI handles all incidents automatically."
        }
        
        st.caption(mode_descriptions[mode])


# =============================================================================
# MAIN APP
# =============================================================================

def main():
    # Initialize session state
    if 'uptime' not in st.session_state:
        st.session_state.uptime = datetime.now()
    
    # Inject CSS
    inject_custom_css()
    
    # Render components
    render_header()
    
    # KPI Cards
    render_kpi_cards()
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Main content grid
    col_left, col_right = st.columns([3, 2])
    
    with col_left:
        render_latency_chart()
        st.markdown("<br>", unsafe_allow_html=True)
        render_action_controls()
        st.markdown("<br>", unsafe_allow_html=True)
        render_mode_toggle()
    
    with col_right:
        render_incident_feed()
        st.markdown("<br>", unsafe_allow_html=True)
        render_ai_terminal()
    
    # Auto-refresh
    time.sleep(1)
    st.rerun()


if __name__ == "__main__":
    main()
