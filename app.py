import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Page configuration
st.set_page_config(
    page_title="Telecom KPI Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .insight-box {
        background-color: #f0f2f6;
        border-left: 5px solid #667eea;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    """Load and merge all CSV files - USES ACTUAL COLUMN NAMES"""
    try:
        # Load CSV files with correct column names
        subscribers = pd.read_csv('SUBSCRIBERS.csv')
        bills = pd.read_csv('BILLS.csv')
        tickets = pd.read_csv('TICKETS.csv')
        usage = pd.read_csv('USAGE_RECORDS.csv')
        
        return subscribers, bills, tickets, usage
    except FileNotFoundError as e:
        st.error(f"❌ Missing data file: {e}")
        st.info("Please ensure SUBSCRIBERS.csv, BILLS.csv, TICKETS.csv, and USAGE_RECORDS.csv are in the same directory as app.py")
        st.stop()

def calculate_service_tier(plan_type, plan_name, tenure_months):
    """Rule-based service tier classification"""
    if plan_type == 'Postpaid':
        if (plan_name == 'Unlimited' or tenure_months > 36):
            return 'Priority 1 (Critical)'
        elif (plan_name == 'Premium' or tenure_months > 12):
            return 'Priority 2 (High)'
        else:
            return 'Priority 3 (Standard)'
    else:
        return 'Priority 4 (Basic)'

def flag_anomalies(series):
    """Flag unusual metrics using IQR"""
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    upper_bound = Q3 + 1.5 * IQR
    return series > upper_bound

def calculate_executive_kpis(subscribers, bills, tickets):
    """Calculate all Executive KPIs - FIXED FOR YOUR ACTUAL COLUMNS"""
    kpis = {}
    
    # KPI 1: Total Revenue
    kpis['total_revenue'] = bills['bill_amount'].sum()
    
    # KPI 2: ARPU
    active_subs = len(subscribers[subscribers['status'] == 'Active'])
    kpis['arpu'] = kpis['total_revenue'] / active_subs if active_subs > 0 else 0
    
    # KPI 3: Prepaid vs Postpaid Mix
    prepaid_rev = bills[bills['subscriber_id'].isin(
        subscribers[subscribers['plan_type'] == 'Prepaid']['subscriber_id']
    )]['bill_amount'].sum()
    kpis['prepaid_pct'] = (prepaid_rev / kpis['total_revenue'] * 100) if kpis['total_revenue'] > 0 else 0
    kpis['postpaid_pct'] = 100 - kpis['prepaid_pct']
    
    # KPI 4: Retention Ratio
    active_count = len(subscribers[subscribers['status'] == 'Active'])
    total_count = len(subscribers)
    kpis['retention_ratio'] = (active_count / total_count * 100) if total_count > 0 else 0
    
    # KPI 5: Overdue Revenue
    kpis['overdue_revenue'] = bills[bills['payment_status'] == 'Overdue']['bill_amount'].sum()
    
    # KPI 7: Credit Adjustments
    kpis['credit_adjustments'] = bills['credit_adjustment'].sum() if 'credit_adjustment' in bills.columns else 0
    
    return kpis

def calculate_manager_kpis(tickets):
    """Calculate all Manager/Operations KPIs - FIXED FOR YOUR ACTUAL COLUMNS"""
    kpis = {}
    
    # KPI 8: Ticket Volume
    kpis['total_tickets'] = len(tickets)
    
    # KPI 9: SLA Compliance Rate
    resolved_tickets = tickets[tickets['status'] == 'Resolved'].copy()
    
    if len(resolved_tickets) > 0:
        # Calculate resolution time in hours
        resolved_tickets['resolution_hours'] = (
            (pd.to_datetime(resolved_tickets['resolution_date'], errors='coerce') - 
             pd.to_datetime(resolved_tickets['ticket_date'])).dt.total_seconds() / 3600
        )
        
        sla_compliant = resolved_tickets[
            resolved_tickets['resolution_hours'] <= resolved_tickets['sla_target_hours']
        ]
        kpis['sla_compliance'] = (len(sla_compliant) / len(resolved_tickets) * 100)
    else:
        kpis['sla_compliance'] = 0
    
    # KPI 10: Average Resolution Time
    if len(resolved_tickets) > 0:
        kpis['avg_resolution_time'] = resolved_tickets['resolution_hours'].mean()
    else:
        kpis['avg_resolution_time'] = 0
    
    # KPI 11: Ticket Backlog
    open_tickets = tickets[tickets['status'].isin(['Open', 'In Progress', 'Escalated'])]
    kpis['ticket_backlog'] = len(open_tickets)
    
    # KPI 12: Escalation Rate
    escalated = len(tickets[tickets['status'] == 'Escalated'])
    kpis['escalation_rate'] = (escalated / len(tickets) * 100) if len(tickets) > 0 else 0
    
    # KPI 14: Network Issue Ratio
    network_issues = len(tickets[tickets['ticket_category'] == 'Network Issue'])
    kpis['network_issue_ratio'] = (network_issues / len(tickets) * 100) if len(tickets) > 0 else 0
    
    return kpis

# Load data
subscribers, bills, tickets, usage = load_data()

# ===== PREPARE DATA - USE ACTUAL COLUMN NAMES =====
# Convert dates using actual column names from your CSVs
subscribers['activation_date'] = pd.to_datetime(subscribers['activation_date'])
bills['billing_month'] = pd.to_datetime(bills['billing_month'])
tickets['ticket_date'] = pd.to_datetime(tickets['ticket_date'])
tickets['resolution_date'] = pd.to_datetime(tickets['resolution_date'], errors='coerce')
usage['usage_date'] = pd.to_datetime(usage['usage_date'])

# Add service tier using actual column names
subscribers['service_tier'] = subscribers.apply(
    lambda x: calculate_service_tier(
        x['plan_type'], 
        x['plan_name'], 
        (datetime.now() - x['activation_date']).days // 30
    ), axis=1
)

# Sidebar filters
st.sidebar.markdown("## 🎯 Filters")

date_range = st.sidebar.date_input(
    "Date Range",
    value=(bills['billing_month'].min().date(), bills['billing_month'].max().date()),
    key="date_range"
)

cities = st.sidebar.multiselect(
    "Cities",
    options=sorted(subscribers['city'].unique()),
    default=sorted(subscribers['city'].unique())[:3]
)

plan_types = st.sidebar.multiselect(
    "Plan Types",
    options=subscribers['plan_type'].unique(),
    default=subscribers['plan_type'].unique()
)

plan_names = st.sidebar.multiselect(
    "Plan Names",
    options=subscribers['plan_name'].unique(),
    default=subscribers['plan_name'].unique()
)

ticket_categories = st.sidebar.multiselect(
    "Ticket Categories",
    options=tickets['ticket_category'].unique(),
    default=tickets['ticket_category'].unique()
)

subscriber_status = st.sidebar.multiselect(
    "Subscriber Status",
    options=subscribers['status'].unique(),
    default=subscribers['status'].unique()
)

# View toggle
st.sidebar.markdown("---")
view_type = st.sidebar.radio(
    "📊 Select View",
    options=["Executive View", "Manager View"],
    index=0
)

# Apply filters
filtered_subscribers = subscribers[
    (subscribers['city'].isin(cities)) &
    (subscribers['plan_type'].isin(plan_types)) &
    (subscribers['plan_name'].isin(plan_names)) &
    (subscribers['status'].isin(subscriber_status))
]

filtered_bills = bills[
    (bills['subscriber_id'].isin(filtered_subscribers['subscriber_id'])) &
    (bills['billing_month'].dt.date >= date_range[0]) &
    (bills['billing_month'].dt.date <= date_range[1])
]

filtered_tickets = tickets[
    (tickets['ticket_date'].dt.date >= date_range[0]) &
    (tickets['ticket_date'].dt.date <= date_range[1]) &
    (tickets['ticket_category'].isin(ticket_categories))
]

# ==================== EXECUTIVE VIEW ====================
if view_type == "Executive View":
    st.title("📈 Executive Dashboard")
    st.markdown("Strategic KPIs for C-Level Decision Making")
    
    # Calculate KPIs
    exec_kpis = calculate_executive_kpis(filtered_subscribers, filtered_bills, filtered_tickets)
    
    # KPI Cards Row 1
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "Total Revenue",
            f"AED {exec_kpis['total_revenue']:,.0f}",
            delta=f"{(exec_kpis['total_revenue']/1e6):.2f}M"
        )
    
    with col2:
        st.metric(
            "ARPU",
            f"AED {exec_kpis['arpu']:,.0f}",
            delta="Per Subscriber"
        )
    
    with col3:
        st.metric(
            "Retention Ratio",
            f"{exec_kpis['retention_ratio']:.1f}%",
            delta="Active Subs"
        )
    
    with col4:
        st.metric(
            "Overdue Revenue",
            f"AED {exec_kpis['overdue_revenue']:,.0f}",
            delta="At Risk"
        )
    
    with col5:
        st.metric(
            "Credit Adjustments",
            f"AED {exec_kpis['credit_adjustments']:,.0f}",
            delta="Total Issued"
        )
    
    # Charts Row 1
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        # Revenue Trend
        revenue_trend = filtered_bills.groupby(filtered_bills['billing_month'].dt.date)['bill_amount'].sum()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=revenue_trend.index,
            y=revenue_trend.values,
            mode='lines+markers',
            line=dict(color='#667eea', width=3),
            fill='tozeroy',
            fillcolor='rgba(102, 126, 234, 0.2)'
        ))
        fig.update_layout(
            title="Monthly Revenue Trend",
            xaxis_title="Date",
            yaxis_title="Revenue (AED)",
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Plan Mix
        plan_revenue = filtered_bills.merge(
            filtered_subscribers[['subscriber_id', 'plan_type']], 
            on='subscriber_id'
        ).groupby('plan_type')['bill_amount'].sum()
        
        fig = px.pie(
            values=plan_revenue.values,
            names=plan_revenue.index,
            title="Revenue by Plan Type",
            color_discrete_sequence=['#667eea', '#764ba2']
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Charts Row 2
    col1, col2 = st.columns(2)
    
    with col1:
        # Revenue by City
        city_revenue = filtered_bills.merge(
            filtered_subscribers[['subscriber_id', 'city']], 
            on='subscriber_id'
        ).groupby('city')['bill_amount'].sum().sort_values(ascending=False)
        
        fig = px.bar(
            x=city_revenue.index,
            y=city_revenue.values,
            title="Revenue by City",
            labels={'y': 'Revenue (AED)', 'x': 'City'},
            color=city_revenue.values,
            color_continuous_scale='Blues'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Subscriber Status
        status_counts = filtered_subscribers['status'].value_counts()
        
        fig = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Subscriber Status Distribution",
            color_discrete_map={'Active': '#2ecc71', 'Suspended': '#e74c3c', 'Churned': '#95a5a6'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Payment Status
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        payment_status = filtered_bills['payment_status'].value_counts()
        
        fig = px.bar(
            x=payment_status.index,
            y=payment_status.values,
            title="Bill Payment Status Distribution",
            labels={'y': 'Count', 'x': 'Status'},
            color=payment_status.index,
            color_discrete_map={'Paid': '#2ecc71', 'Overdue': '#e74c3c', 'Partial': '#f39c12', 'Pending': '#3498db'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Top Plans by Revenue
        plan_revenue = filtered_bills.merge(
            filtered_subscribers[['subscriber_id', 'plan_name']], 
            on='subscriber_id'
        ).groupby('plan_name')['bill_amount'].sum().sort_values(ascending=False)
        
        fig = px.bar(
            x=plan_revenue.values,
            y=plan_revenue.index,
            orientation='h',
            title="Top Plans by Revenue",
            labels={'x': 'Revenue (AED)', 'y': 'Plan Name'},
            color=plan_revenue.values,
            color_continuous_scale='Greens'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Insights
    st.markdown("---")
    st.markdown("### 💡 Executive Insights")
    
    top_city = filtered_bills.merge(
        filtered_subscribers[['subscriber_id', 'city']], 
        on='subscriber_id'
    ).groupby('city')['bill_amount'].sum().idxmax() if len(filtered_bills) > 0 else 'N/A'
    
    insights_exec = f"""
    <div class="insight-box">
    <b>📊 Key Findings:</b><br>
    • Total Revenue: <b>AED {exec_kpis['total_revenue']:,.0f}</b><br>
    • ARPU: <b>AED {exec_kpis['arpu']:,.0f}</b><br>
    • Retention Ratio: <b>{exec_kpis['retention_ratio']:.1f}%</b><br>
    • Overdue Revenue: <b>AED {exec_kpis['overdue_revenue']:,.0f}</b> ({(exec_kpis['overdue_revenue']/exec_kpis['total_revenue']*100):.1f}% of total)<br>
    • Top Performing City: <b>{top_city}</b><br>
    <b>⚠️ Recommendation:</b> Focus on improving collection from overdue accounts and maintaining retention rates.
    </div>
    """
    st.markdown(insights_exec, unsafe_allow_html=True)

# ==================== MANAGER VIEW ====================
else:
    st.title("⚙️ Operations Dashboard")
    st.markdown("Operational KPIs for COO and Support Teams")
    
    # Calculate KPIs
    ops_kpis = calculate_manager_kpis(filtered_tickets)
    
    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "SLA Compliance Rate",
            f"{ops_kpis['sla_compliance']:.1f}%",
            delta="Tickets resolved on time"
        )
    
    with col2:
        st.metric(
            "Ticket Backlog",
            f"{ops_kpis['ticket_backlog']:,}",
            delta="Unresolved tickets"
        )
    
    with col3:
        st.metric(
            "Avg Resolution Time",
            f"{ops_kpis['avg_resolution_time']:.1f} hrs",
            delta="Mean resolution"
        )
    
    with col4:
        st.metric(
            "Escalation Rate",
            f"{ops_kpis['escalation_rate']:.1f}%",
            delta="Tickets escalated"
        )
    
    # Charts Row 1
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        # Daily Ticket Volume
        daily_tickets = filtered_tickets.groupby(filtered_tickets['ticket_date'].dt.date).size()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily_tickets.index,
            y=daily_tickets.values,
            mode='lines+markers',
            line=dict(color='#e74c3c', width=2),
            fill='tozeroy',
            fillcolor='rgba(231, 76, 60, 0.2)'
        ))
        fig.update_layout(
            title="Daily Ticket Volume Trend",
            xaxis_title="Date",
            yaxis_title="Ticket Count",
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Ticket Category Distribution
        category_counts = filtered_tickets['ticket_category'].value_counts().head(10)
        
        fig = px.bar(
            x=category_counts.values,
            y=category_counts.index,
            orientation='h',
            title="Top 10 Ticket Categories",
            labels={'x': 'Count', 'y': 'Category'},
            color=category_counts.values,
            color_continuous_scale='Viridis'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Charts Row 2
    col1, col2 = st.columns(2)
    
    with col1:
        # Ticket Status Distribution
        status_counts = filtered_tickets['status'].value_counts()
        
        fig = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Ticket Status Distribution",
            color_discrete_map={'Resolved': '#2ecc71', 'Open': '#e74c3c', 'In Progress': '#f39c12', 'Escalated': '#95a5a6'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Tickets by Channel
        channel_counts = filtered_tickets['ticket_channel'].value_counts()
        
        fig = px.bar(
            x=channel_counts.index,
            y=channel_counts.values,
            title="Tickets by Channel",
            labels={'y': 'Count', 'x': 'Channel'},
            color=channel_counts.values,
            color_continuous_scale='Blues'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Team Analysis
    st.markdown("---")
    st.subheader("👥 Team Performance Analysis")
    
    team_analysis = filtered_tickets.groupby('assigned_team').agg({
        'ticket_id': 'count',
        'status': lambda x: (x == 'Resolved').sum()
    }).rename(columns={'ticket_id': 'Total Tickets', 'status': 'Resolved Tickets'})
    
    team_analysis['Efficiency %'] = (team_analysis['Resolved Tickets'] / team_analysis['Total Tickets'] * 100).round(1)
    
    st.dataframe(
        team_analysis.reset_index().rename(columns={'assigned_team': 'Team'}),
        use_container_width=True,
        hide_index=True
    )
    
    # Priority Distribution
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        priority_counts = filtered_tickets['priority'].value_counts()
        
        fig = px.pie(
            values=priority_counts.values,
            names=priority_counts.index,
            title="Ticket Priority Distribution",
            color_discrete_sequence=['#2ecc71', '#f39c12', '#e74c3c', '#c0392b']
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Resolution Time by Channel
        resolved = filtered_tickets[filtered_tickets['status'] == 'Resolved'].copy()
        resolved['resolution_hours'] = (
            (pd.to_datetime(resolved['resolution_date'], errors='coerce') - 
             pd.to_datetime(resolved['ticket_date'])).dt.total_seconds() / 3600
        )
        
        if len(resolved) > 0:
            channel_resolution = resolved.groupby('ticket_channel')['resolution_hours'].mean().sort_values()
            
            fig = px.bar(
                x=channel_resolution.values,
                y=channel_resolution.index,
                orientation='h',
                title="Avg Resolution Time by Channel",
                labels={'x': 'Hours', 'y': 'Channel'},
                color=channel_resolution.values,
                color_continuous_scale='Reds_r'
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Insights Box
    st.markdown("---")
    st.markdown("### 💡 Operational Insights")
    
    network_pct = (len(filtered_tickets[filtered_tickets['ticket_category'] == 'Network Issue']) / len(filtered_tickets) * 100) if len(filtered_tickets) > 0 else 0
    
    insights_ops = f"""
    <div class="insight-box">
    <b>⚙️ Key Findings:</b><br>
    • SLA Compliance: <b>{ops_kpis['sla_compliance']:.1f}%</b> of tickets resolved on time<br>
    • Ticket Backlog: <b>{ops_kpis['ticket_backlog']:,}</b> unresolved tickets<br>
    • Avg Resolution Time: <b>{ops_kpis['avg_resolution_time']:.1f} hours</b><br>
    • Escalation Rate: <b>{ops_kpis['escalation_rate']:.1f}%</b><br>
    • Network Issues: <b>{network_pct:.1f}%</b> of all tickets<br>
    <b>⚠️ Recommendation:</b> Focus on network issues and improve team efficiency to meet SLA targets.
    </div>
    """
    st.markdown(insights_ops, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #999; font-size: 12px;'>"
    "Telecom KPI Dashboard | Data-Driven Decision Making | Last Updated: " + 
    datetime.now().strftime("%Y-%m-%d %H:%M:%S") +
    "</div>",
    unsafe_allow_html=True
)
