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
    """Load and merge all CSV files"""
    try:
        # Load CSV files (users should place them in same directory)
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
    """Calculate all Executive KPIs"""
    kpis = {}
    
    # KPI 1: Total Revenue
    kpis['total_revenue'] = bills['bill_amount'].sum()
    
    # KPI 2: ARPU
    active_subs = len(subscribers[subscribers['subscriber_status'] == 'Active'])
    kpis['arpu'] = kpis['total_revenue'] / active_subs if active_subs > 0 else 0
    
    # KPI 3: Prepaid vs Postpaid Mix
    prepaid_rev = bills[bills['subscriber_id'].isin(
        subscribers[subscribers['plan_type'] == 'Prepaid']['subscriber_id']
    )]['bill_amount'].sum()
    kpis['prepaid_pct'] = (prepaid_rev / kpis['total_revenue'] * 100) if kpis['total_revenue'] > 0 else 0
    kpis['postpaid_pct'] = 100 - kpis['prepaid_pct']
    
    # KPI 4: Retention Ratio
    active_count = len(subscribers[subscribers['subscriber_status'] == 'Active'])
    total_count = len(subscribers)
    kpis['retention_ratio'] = (active_count / total_count * 100) if total_count > 0 else 0
    
    # KPI 5: Overdue Revenue
    kpis['overdue_revenue'] = bills[bills['payment_status'] == 'Overdue']['bill_amount'].sum()
    
    # KPI 7: Credit Adjustments
    kpis['credit_adjustments'] = bills['credit_adjustment'].sum() if 'credit_adjustment' in bills.columns else 0
    
    return kpis

def calculate_manager_kpis(tickets):
    """Calculate all Manager/Operations KPIs"""
    kpis = {}
    
    # KPI 8: Ticket Volume
    kpis['total_tickets'] = len(tickets)
    
    # KPI 9: SLA Compliance Rate
    resolved_tickets = tickets[tickets['status'] == 'Resolved']
    sla_compliant = resolved_tickets[
        (resolved_tickets['resolution_date'] - resolved_tickets['ticket_date']).dt.total_seconds() / 3600 <= resolved_tickets['sla_target_hours']
    ]
    kpis['sla_compliance'] = (len(sla_compliant) / len(resolved_tickets) * 100) if len(resolved_tickets) > 0 else 0
    
    # KPI 10: Average Resolution Time
    resolved_tickets['resolution_hours'] = (
        (resolved_tickets['resolution_date'] - resolved_tickets['ticket_date']).dt.total_seconds() / 3600
    )
    kpis['avg_resolution_time'] = resolved_tickets['resolution_hours'].mean()
    
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

# Prepare data
subscribers['signup_date'] = pd.to_datetime(subscribers['signup_date'])
bills['billing_date'] = pd.to_datetime(bills['billing_date'])
tickets['ticket_date'] = pd.to_datetime(tickets['ticket_date'])
tickets['resolution_date'] = pd.to_datetime(tickets['resolution_date'])

# Add service tier
subscribers['service_tier'] = subscribers.apply(
    lambda x: calculate_service_tier(
        x['plan_type'], 
        x['plan_name'], 
        (datetime.now() - x['signup_date']).days // 30
    ), axis=1
)

# Sidebar filters
st.sidebar.markdown("## 🎯 Filters")

date_range = st.sidebar.date_input(
    "Date Range",
    value=(bills['billing_date'].min().date(), bills['billing_date'].max().date()),
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
    options=subscribers['subscriber_status'].unique(),
    default=subscribers['subscriber_status'].unique()
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
    (subscribers['subscriber_status'].isin(subscriber_status))
]

filtered_bills = bills[
    (bills['subscriber_id'].isin(filtered_subscribers['subscriber_id'])) &
    (bills['billing_date'].dt.date >= date_range[0]) &
    (bills['billing_date'].dt.date <= date_range[1])
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
    
    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Revenue",
            f"AED {exec_kpis['total_revenue']:,.0f}",
            delta=f"{(exec_kpis['total_revenue']/bills['bill_amount'].sum()*100):.1f}% of period"
        )
    
    with col2:
        st.metric(
            "ARPU",
            f"AED {exec_kpis['arpu']:,.0f}",
            delta="Avg per subscriber"
        )
    
    with col3:
        st.metric(
            "Retention Ratio",
            f"{exec_kpis['retention_ratio']:.1f}%",
            delta="Active subscribers"
        )
    
    with col4:
        st.metric(
            "Overdue Revenue",
            f"AED {exec_kpis['overdue_revenue']:,.0f}",
            delta="At risk"
        )
    
    # Charts Row 1
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        # Monthly ARPU Trend
        monthly_revenue = filtered_bills.groupby(filtered_bills['billing_date'].dt.to_period('M'))['bill_amount'].sum()
        monthly_active = filtered_subscribers.groupby(
            filtered_bills[filtered_bills['subscriber_id'].isin(filtered_subscribers['subscriber_id'])]['billing_date'].dt.to_period('M')
        ).size()
        monthly_arpu = monthly_revenue / monthly_active
        
        fig_arpu = go.Figure()
        fig_arpu.add_trace(go.Scatter(
            x=monthly_arpu.index.astype(str),
            y=monthly_arpu.values,
            mode='lines+markers',
            line=dict(color='#667eea', width=3),
            fill='tozeroy',
            fillcolor='rgba(102, 126, 234, 0.2)'
        ))
        fig_arpu.update_layout(
            title="Monthly ARPU Trend",
            xaxis_title="Month",
            yaxis_title="ARPU (AED)",
            hovermode='x unified'
        )
        st.plotly_chart(fig_arpu, use_container_width=True)
    
    with col2:
        # Revenue by Plan Type
        plan_revenue = filtered_bills.merge(
            filtered_subscribers[['subscriber_id', 'plan_type']], 
            on='subscriber_id'
        ).groupby(['billing_date', 'plan_type'])['bill_amount'].sum().reset_index()
        plan_revenue['billing_date'] = plan_revenue['billing_date'].dt.to_period('M').astype(str)
        
        fig_plan = px.bar(
            plan_revenue,
            x='billing_date',
            y='bill_amount',
            color='plan_type',
            title="Revenue by Plan Type",
            labels={'bill_amount': 'Revenue (AED)', 'billing_date': 'Month'},
            barmode='stack'
        )
        st.plotly_chart(fig_plan, use_container_width=True)
    
    # Charts Row 2
    col1, col2 = st.columns(2)
    
    with col1:
        # Revenue by City
        city_revenue = filtered_bills.merge(
            filtered_subscribers[['subscriber_id', 'city']], 
            on='subscriber_id'
        ).groupby('city')['bill_amount'].sum().sort_values(ascending=True)
        
        fig_city = px.barh(
            x=city_revenue.values,
            y=city_revenue.index,
            title="Revenue by City",
            labels={'x': 'Revenue (AED)', 'y': 'City'},
            color=city_revenue.values,
            color_continuous_scale='Blues'
        )
        st.plotly_chart(fig_city, use_container_width=True)
    
    with col2:
        # Payment Status Distribution
        payment_dist = filtered_bills['payment_status'].value_counts()
        
        fig_payment = px.pie(
            values=payment_dist.values,
            names=payment_dist.index,
            title="Payment Status Distribution",
            color_discrete_sequence=['#2ecc71', '#e74c3c', '#f39c12', '#95a5a6']
        )
        st.plotly_chart(fig_payment, use_container_width=True)
    
    # Insights Box
    st.markdown("---")
    st.markdown("### 💡 Executive Insights")
    
    highest_city = filtered_bills.merge(
        filtered_subscribers[['subscriber_id', 'city']], 
        on='subscriber_id'
    ).groupby('city')['bill_amount'].sum().idxmax()
    highest_city_revenue = filtered_bills.merge(
        filtered_subscribers[['subscriber_id', 'city']], 
        on='subscriber_id'
    ).groupby('city')['bill_amount'].sum().max()
    
    insights = f"""
    <div class="insight-box">
    <b>📊 Key Findings:</b><br>
    • ARPU stands at <b>AED {exec_kpis['arpu']:,.0f}</b>, with <b>{exec_kpis['postpaid_pct']:.1f}%</b> from Postpaid plans<br>
    • Retention ratio is <b>{exec_kpis['retention_ratio']:.1f}%</b> with strong base of active subscribers<br>
    • <b>AED {exec_kpis['overdue_revenue']:,.0f}</b> at risk from overdue accounts (highest in {highest_city})<br>
    • Total revenue: <b>AED {exec_kpis['total_revenue']:,.0f}</b> | Credits issued: <b>AED {exec_kpis['credit_adjustments']:,.0f}</b><br>
    <b>⚠️ Recommendation:</b> Focus collection efforts on {highest_city} region to reduce overdue revenue
    </div>
    """
    st.markdown(insights, unsafe_allow_html=True)

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
        
        fig_volume = go.Figure()
        fig_volume.add_trace(go.Scatter(
            x=daily_tickets.index,
            y=daily_tickets.values,
            mode='lines+markers',
            line=dict(color='#e74c3c', width=2),
            fill='tozeroy',
            fillcolor='rgba(231, 76, 60, 0.2)'
        ))
        fig_volume.update_layout(
            title="Daily Ticket Volume Trend",
            xaxis_title="Date",
            yaxis_title="Ticket Count",
            hovermode='x unified'
        )
        st.plotly_chart(fig_volume, use_container_width=True)
    
    with col2:
        # SLA Compliance by Channel
        resolved = filtered_tickets[filtered_tickets['status'] == 'Resolved'].copy()
        resolved['resolution_hours'] = (
            (resolved['resolution_date'] - resolved['ticket_date']).dt.total_seconds() / 3600
        )
        resolved['sla_compliant'] = resolved['resolution_hours'] <= resolved['sla_target_hours']
        
        channel_sla = resolved.groupby('ticket_channel')['sla_compliant'].apply(
            lambda x: (x.sum() / len(x) * 100) if len(x) > 0 else 0
        ).sort_values(ascending=False)
        
        fig_sla = px.bar(
            x=channel_sla.values,
            y=channel_sla.index,
            title="SLA Compliance by Channel",
            labels={'x': 'Compliance Rate (%)', 'y': 'Channel'},
            color=channel_sla.values,
            color_continuous_scale='RdYlGn',
            orientation='h'
        )
        st.plotly_chart(fig_sla, use_container_width=True)
    
    # Charts Row 2
    col1, col2 = st.columns(2)
    
    with col1:
        # Ticket Category Distribution
        category_counts = filtered_tickets['ticket_category'].value_counts().head(10)
        
        fig_category = px.bar(
            x=category_counts.values,
            y=category_counts.index,
            title="Top 10 Ticket Categories",
            labels={'x': 'Count', 'y': 'Category'},
            color=category_counts.values,
            color_continuous_scale='Viridis',
            orientation='h'
        )
        st.plotly_chart(fig_category, use_container_width=True)
    
    with col2:
        # Resolution Time by Team
        resolved_team = filtered_tickets[filtered_tickets['status'] == 'Resolved'].copy()
        resolved_team['resolution_hours'] = (
            (resolved_team['resolution_date'] - resolved_team['ticket_date']).dt.total_seconds() / 3600
        )
        
        team_resolution = resolved_team.groupby('assigned_team')['resolution_hours'].mean().sort_values()
        
        fig_team = px.bar(
            x=team_resolution.values,
            y=team_resolution.index,
            title="Avg Resolution Time by Team",
            labels={'x': 'Hours', 'y': 'Team'},
            color=team_resolution.values,
            color_continuous_scale='Reds_r',
            orientation='h'
        )
        st.plotly_chart(fig_team, use_container_width=True)
    
    # Top Problem Zones Table
    st.markdown("---")
    st.subheader("🔥 Top 10 Problem Zones Analysis")
    
    zone_analysis = filtered_tickets.groupby('assigned_team').agg({
        'ticket_id': 'count',
        'status': lambda x: (x.isin(['Open', 'In Progress', 'Escalated'])).sum()
    }).rename(columns={'ticket_id': 'Total Tickets', 'status': 'Open Tickets'})
    
    resolved_data = filtered_tickets[filtered_tickets['status'] == 'Resolved'].copy()
    resolved_data['resolution_hours'] = (
        (resolved_data['resolution_date'] - resolved_data['ticket_date']).dt.total_seconds() / 3600
    )
    
    zone_analysis['Avg Resolution Hours'] = resolved_data.groupby('assigned_team')['resolution_hours'].mean()
    zone_analysis['SLA Breaches'] = resolved_data.groupby('assigned_team').apply(
        lambda x: (x['resolution_hours'] > x['sla_target_hours']).sum()
    )
    
    zone_analysis = zone_analysis.sort_values('Total Tickets', ascending=False).head(10)
    
    # Make table interactive
    st.dataframe(
        zone_analysis.reset_index().rename(columns={'assigned_team': 'Zone/Team'}),
        use_container_width=True,
        hide_index=True
    )
    
    # Service Tier Analysis
    st.markdown("---")
    st.subheader("📊 Ticket Distribution by Service Tier")
    
    tier_analysis = filtered_tickets.merge(
        filtered_subscribers[['subscriber_id', 'service_tier']], 
        left_on='subscriber_id', 
        right_on='subscriber_id',
        how='left'
    ).groupby('service_tier').agg({
        'ticket_id': 'count',
        'status': lambda x: (x == 'Resolved').sum()
    }).rename(columns={'ticket_id': 'Total Tickets', 'status': 'Resolved Tickets'})
    
    tier_analysis['SLA Compliance %'] = (tier_analysis['Resolved Tickets'] / tier_analysis['Total Tickets'] * 100).round(1)
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_tier = px.bar(
            x=tier_analysis.index,
            y=tier_analysis['Total Tickets'],
            title="Ticket Backlog by Service Tier",
            labels={'y': 'Tickets', 'x': 'Service Tier'},
            color=tier_analysis['Total Tickets'],
            color_continuous_scale='Blues'
        )
        st.plotly_chart(fig_tier, use_container_width=True)
    
    with col2:
        fig_tier_sla = px.bar(
            x=tier_analysis.index,
            y=tier_analysis['SLA Compliance %'],
            title="SLA Compliance by Service Tier",
            labels={'y': 'Compliance %', 'x': 'Service Tier'},
            color=tier_analysis['SLA Compliance %'],
            color_continuous_scale='RdYlGn',
            range_y=[0, 100]
        )
        st.plotly_chart(fig_tier_sla, use_container_width=True)
    
    st.dataframe(
        tier_analysis.reset_index().rename(columns={'service_tier': 'Tier'}),
        use_container_width=True,
        hide_index=True
    )
    
    # Insights Box
    st.markdown("---")
    st.markdown("### 💡 Operational Insights")
    
    worst_channel = channel_sla.idxmin()
    worst_team = team_resolution.idxmax()
    network_pct = (len(filtered_tickets[filtered_tickets['ticket_category'] == 'Network Issue']) / len(filtered_tickets) * 100) if len(filtered_tickets) > 0 else 0
    
    insights_ops = f"""
    <div class="insight-box">
    <b>⚙️ Key Findings:</b><br>
    • SLA Compliance: <b>{ops_kpis['sla_compliance']:.1f}%</b> of tickets resolved on time<br>
    • Ticket Backlog: <b>{ops_kpis['ticket_backlog']:,}</b> unresolved tickets requiring attention<br>
    • Avg Resolution Time: <b>{ops_kpis['avg_resolution_time']:.1f} hours</b> across all teams<br>
    • Escalation Rate: <b>{ops_kpis['escalation_rate']:.1f}%</b> of tickets escalated<br>
    • Network Issues: <b>{network_pct:.1f}%</b> of all tickets (highest impact category)<br>
    <b>⚠️ Recommendation:</b> {worst_channel} channel has lowest SLA compliance. {worst_team} team shows highest resolution time - consider resource reallocation.
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