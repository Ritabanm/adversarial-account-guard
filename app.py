import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import json
import os
from sklearn.metrics import roc_curve, precision_recall_curve

from data_generator import EcommerceDataGenerator
from classifier import FakeAccountClassifier

# Set page configuration
st.set_page_config(
    page_title="Adversarial Account Guard - Risk Console",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Persistent JSON Actions Database
ACTIONS_FILE = 'audit_actions.json'

def load_manual_actions():
    if os.path.exists(ACTIONS_FILE):
        try:
            with open(ACTIONS_FILE, 'r') as f:
                data = json.load(f)
            # Convert string timestamps back to datetime
            for acct_id, info in data.items():
                info['timestamp'] = datetime.strptime(info['timestamp'], '%Y-%m-%d %H:%M:%S')
            return data
        except Exception as e:
            st.error(f"Error loading manual actions: {e}")
            return {}
    return {}

def save_manual_action(acct_id, action_type, user="TrustAgent_01"):
    actions = load_manual_actions()
    if action_type is None:
        if acct_id in actions:
            del actions[acct_id]
    else:
        actions[acct_id] = {
            'action': action_type,
            'timestamp': datetime.now(),
            'user': user
        }
    
    try:
        # Convert datetime to string for serialization
        serialized = {}
        for aid, info in actions.items():
            serialized[aid] = {
                'action': info['action'],
                'timestamp': info['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'user': info['user']
            }
        with open(ACTIONS_FILE, 'w') as f:
            json.dump(serialized, f, indent=4)
        st.session_state['account_actions'] = actions
    except Exception as e:
        st.error(f"Error saving manual actions: {e}")

# Load actions into session state initially
if 'account_actions' not in st.session_state:
    st.session_state['account_actions'] = load_manual_actions()

# Custom CSS for modern styling
st.markdown("""
<style>
    /* Global modifications */
    .main .block-container {
        padding-top: 2rem;
    }
    
    /* Header card */
    .header-container {
        background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
        padding: 24px;
        border-radius: 12px;
        margin-bottom: 25px;
        border: 1px solid #312e81;
    }
    
    /* Status indicators */
    .badge-suspended {
        background-color: #fee2e2;
        color: #ef4444;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85em;
        border: 1px solid #fca5a5;
    }
    .badge-safe {
        background-color: #d1fae5;
        color: #10b981;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85em;
        border: 1px solid #6ee7b7;
    }
    .badge-audit {
        background-color: #fef3c7;
        color: #f59e0b;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85em;
        border: 1px solid #fde047;
    }
    .badge-unresolved {
        background-color: #f3f4f6;
        color: #6b7280;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85em;
        border: 1px solid #e5e7eb;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- SESSION STATE & INITIALIZATION -----------------

def get_session_data(num_genuine=1000, num_fake=100, attack_severity=0.8, force=False):
    """Initializes or resets data in Streamlit's session state."""
    if 'data_initialized' not in st.session_state or force:
        with st.spinner("Generating simulation data and training machine learning model..."):
            # Generate synthetic data
            generator = EcommerceDataGenerator(seed=42)
            df_accounts, df_reviews = generator.generate_data(
                num_genuine=num_genuine,
                num_fake=num_fake,
                attack_severity=attack_severity
            )
            
            # Train the classifier (all models)
            clf = FakeAccountClassifier()
            df_features_raw, train_auc = clf.train(df_accounts, df_reviews)
            
            # Predict risk probabilities for all models and store
            df_scored = df_features_raw.copy()
            df_scored['risk_score_rf'] = clf.predict_risk(df_accounts, df_reviews, model_type='rf')['risk_score']
            df_scored['risk_score_gbdt'] = clf.predict_risk(df_accounts, df_reviews, model_type='gbdt')['risk_score']
            df_scored['risk_score_unsup'] = clf.predict_risk(df_accounts, df_reviews, model_type='unsup')['risk_score']
            
            # Store in session state
            st.session_state['df_accounts'] = df_accounts
            st.session_state['df_reviews'] = df_reviews
            st.session_state['df_scored'] = df_scored
            st.session_state['classifier'] = clf
            st.session_state['train_auc'] = train_auc
            st.session_state['num_genuine'] = num_genuine
            st.session_state['num_fake'] = num_fake
            st.session_state['attack_severity'] = attack_severity
            st.session_state['data_initialized'] = True

# Trigger default initialization if not already set
get_session_data()

# Read active datasets from session state
df_accounts = st.session_state['df_accounts']
df_reviews = st.session_state['df_reviews']
df_scored_all = st.session_state['df_scored'].copy()
clf = st.session_state['classifier']
train_auc = st.session_state['train_auc']

# ----------------- SIDEBAR CONTROLS -----------------

with st.sidebar:
    st.image("https://img.icons8.com/nolan/96/shield.png", width=60)
    st.title("Risk ML Console")
    st.write("benchmarking fraud detection pipelines.")
    
    st.divider()
    
    # Model Selection (Job Description alignment: "Implement and compare models")
    st.subheader("⚙️ Active Decision Model")
    active_model_desc = st.selectbox(
        "Active Decision Model",
        options=[
            "Random Forest (Supervised Ensemble)", 
            "GBDT / HistGradientBoosting (Supervised)", 
            "Isolation Forest (Unsupervised Anomaly)"
        ],
        index=0,
        label_visibility="collapsed"
    )
    
    # Map to model code
    model_code = "rf"
    if "GBDT" in active_model_desc:
        model_code = "gbdt"
    elif "Isolation Forest" in active_model_desc:
        model_code = "unsup"
        
    # Map current active risk score
    df_scored = df_scored_all.copy()
    df_scored['risk_score'] = df_scored[f'risk_score_{model_code}']
    
    # Active Operational Threshold
    st.write("")
    op_threshold = st.slider(
        "Enforcement Risk Threshold", 
        min_value=0.0, 
        max_value=1.0, 
        value=0.50, 
        step=0.05,
        help="Accounts with risk scores above this threshold are flagged automatically for enforcement."
    )
    
    st.divider()
    
    # Model Status Card
    st.subheader("Console Metrics")
    total_accounts = len(df_scored)
    flagged_accounts = (df_scored['risk_score'] >= op_threshold).sum()
    manual_actions = st.session_state['account_actions']
    actioned_count = len(manual_actions)
    
    st.metric(label="Automatically Flagged", value=f"{flagged_accounts}", delta=f"{(flagged_accounts/total_accounts):.1%}")
    st.metric(label="Database Action Resolutions", value=f"{actioned_count}")

# ----------------- APPLICATION HEADER -----------------

st.markdown("""
<div class="header-container">
    <h1 style="color: #ffffff; margin: 0; padding-bottom: 5px; font-weight: 700;">🛡️ Adversarial Account Guard</h1>
    <p style="color: #ffffff; margin: 0; font-size: 1.1em; opacity: 0.9;">
        Marketplace Safety Console: Supervised GBDTs & Unsupervised Anomaly detection of collusive review farms and bad actors.
    </p>
</div>
""", unsafe_allow_html=True)

# Tabs definitions
tab_dashboard, tab_investigate, tab_sandbox, tab_batch = st.tabs([
    "📊 Risk Overview Dashboard", 
    "🔍 Account Auditor Console", 
    "🧪 Model Comparison & Operational Sandbox", 
    "📁 Batch Log Scoring"
])

# ----------------- TAB 1: OVERVIEW DASHBOARD -----------------

with tab_dashboard:
    # Top level metrics cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Analyzed Accounts", 
            value=f"{total_accounts:,}",
            help="Total registered customer accounts evaluated in active window."
        )
    with col2:
        flag_rate = (flagged_accounts / total_accounts) * 100
        st.metric(
            label="AI Flagged (Above Operational Threshold)", 
            value=f"{flagged_accounts:,}", 
            delta=f"{flag_rate:.1f}% flag rate",
            delta_color="inverse"
        )
    with col3:
        suspended_count = sum(1 for a in manual_actions.values() if a['action'] == 'SUSPENDED')
        st.metric(label="Database Manual Suspensions", value=f"{suspended_count}", help="Persisted to audit_actions.json")
    with col4:
        whitelisted_count = sum(1 for a in manual_actions.values() if a['action'] == 'SAFE')
        st.metric(label="Whitelisted Accounts", value=f"{whitelisted_count}", help="Whitelisted from automated model flags.")
        
    st.write("")
    
    # Graph Area
    g_col1, g_col2 = st.columns(2)
    
    with g_col1:
        st.subheader("Active Model Risk Score Distribution")
        # Histogram of risk scores
        fig_hist = px.histogram(
            df_scored, 
            x='risk_score',
            nbins=20,
            labels={'risk_score': 'AI Suspiciousness Score', 'count': 'Number of Accounts'},
            color_discrete_sequence=['#4f46e5'],
            opacity=0.85
        )
        # Add threshold line
        fig_hist.add_vline(x=op_threshold, line_width=3, line_dash="dash", line_color="#dc2626")
        fig_hist.add_vrect(x0=op_threshold, x1=1.0, fillcolor="#fee2e2", opacity=0.3, line_width=0)
        
        fig_hist.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=True, gridcolor='#e2e8f0'),
            yaxis=dict(showgrid=True, gridcolor='#e2e8f0'),
            margin=dict(l=40, r=40, t=10, b=40),
            height=320
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    with g_col2:
        st.subheader("Temporal Signup Activity & AI Risk")
        # Scatter plot of sign up time vs risk score to highlight adversarial registration spikes
        df_plot = df_scored.copy()
        df_plot['signup_date'] = pd.to_datetime(df_plot['signup_time'])
        df_plot['Classification'] = df_plot['is_fake'].apply(lambda x: 'Fake (Ground Truth)' if x == 1 else 'Genuine')
        
        fig_scatter = px.scatter(
            df_plot,
            x='signup_date',
            y='risk_score',
            color='Classification',
            color_discrete_map={'Genuine': '#10b981', 'Fake (Ground Truth)': '#dc2626'},
            hover_data=['account_id', 'username', 'review_count'],
            opacity=0.75
        )
        fig_scatter.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=True, gridcolor='#e2e8f0'),
            yaxis=dict(showgrid=True, gridcolor='#e2e8f0'),
            margin=dict(l=40, r=40, t=10, b=40),
            height=320,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    # Secondary row of graphs
    g_col3, g_col4 = st.columns([1.2, 1.8])
    
    with g_col3:
        st.subheader("Key Random Forest Feature Importances")
        df_imp = clf.get_feature_importances()
        feature_labels_map = {
            'ip_shared_count': 'IP Reuse Count',
            'subnet_shared_count': 'Subnet Reuse Count',
            'device_shared_count': 'Device Reuse Count',
            'review_count': 'Reviews Written',
            'avg_rating': 'Avg Rating Given',
            'rating_std': 'Rating Standard Dev',
            'extreme_rating_ratio': 'Ratio of 1/5 Stars',
            'min_delay_hours': 'Min Signup-to-Review Delay',
            'avg_delay_hours': 'Avg Signup-to-Review Delay',
            'seller_entropy': 'Seller Concentration Entropy',
            'avg_text_freq': 'Avg Review Text Duplicity'
        }
        df_imp['Feature Name'] = df_imp['feature'].map(feature_labels_map)
        
        fig_imp = px.bar(
            df_imp.sort_values(by='importance', ascending=True),
            x='importance',
            y='Feature Name',
            orientation='h',
            color='importance',
            color_continuous_scale=px.colors.sequential.Sunsetdark
        )
        fig_imp.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            coloraxis_showscale=False,
            margin=dict(l=40, r=20, t=10, b=40),
            height=350,
            xaxis=dict(showgrid=True, gridcolor='#e2e8f0'),
            yaxis=dict(showgrid=False)
        )
        st.plotly_chart(fig_imp, use_container_width=True)

    with g_col4:
        st.subheader("Flagged Review Collusion Hotspots (Target Sellers)")
        # Identify sellers receiving the most reviews from flagged accounts
        df_revs_scored = df_reviews.merge(df_scored[['account_id', 'risk_score', 'is_fake']], on='account_id', how='left')
        flagged_revs = df_revs_scored[df_revs_scored['risk_score'] >= op_threshold]
        
        if len(flagged_revs) > 0:
            seller_hotspots = flagged_revs.groupby('seller_id').agg(
                flagged_reviews=('review_id', 'count'),
                avg_rating=('rating', 'mean')
            ).reset_index().sort_values(by='flagged_reviews', ascending=False).head(8)
            
            fig_hotspots = px.bar(
                seller_hotspots,
                x='seller_id',
                y='flagged_reviews',
                color='avg_rating',
                labels={'flagged_reviews': 'Reviews Posted by Flagged Accounts', 'seller_id': 'Seller ID', 'avg_rating': 'Avg Rating'},
                color_continuous_scale='RdYlGn',
                range_color=[1, 5]
            )
            fig_hotspots.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=40, r=40, t=10, b=40),
                height=350,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='#e2e8f0')
            )
            st.plotly_chart(fig_hotspots, use_container_width=True)
        else:
            st.info("No flagged reviews available at current operational settings.")

# ----------------- TAB 2: ACCOUNT INVESTIGATION CONSOLE -----------------

with tab_investigate:
    st.subheader("Manual Audit Queue")
    
    # Filtering settings
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        min_risk = st.slider("Filter Minimum Risk Score", 0.0, 1.0, 0.4, 0.05)
    with filter_col2:
        search_query = st.text_input("Search Username / User ID", placeholder="e.g. USR-F00001, user_1234")
    with filter_col3:
        status_filter = st.selectbox(
            "Audit Override Resolution Status",
            options=["All Accounts", "Unresolved Flagged", "Banned / Suspended", "Whitelisted", "Pending Audit"]
        )
        
    # Apply filters
    df_filtered = df_scored.copy()
    df_filtered = df_filtered[df_filtered['risk_score'] >= min_risk]
    
    if search_query:
        df_filtered = df_filtered[
            df_filtered['account_id'].str.contains(search_query, case=False) |
            df_filtered['username'].str.contains(search_query, case=False)
        ]
        
    # Load manual action statuses
    actions_map = st.session_state['account_actions']
    def get_status_str(acct_id):
        if acct_id in actions_map:
            act = actions_map[acct_id]['action']
            if act == 'SUSPENDED': return 'Suspended'
            if act == 'SAFE': return 'Whitelisted'
            if act == 'AUDIT': return 'Pending Audit'
        return 'Unresolved'
        
    df_filtered['status'] = df_filtered['account_id'].apply(get_status_str)
    
    if status_filter == "Unresolved Flagged":
        df_filtered = df_filtered[df_filtered['status'] == 'Unresolved']
    elif status_filter == "Banned / Suspended":
        df_filtered = df_filtered[df_filtered['status'] == 'Suspended']
    elif status_filter == "Whitelisted":
        df_filtered = df_filtered[df_filtered['status'] == 'Whitelisted']
    elif status_filter == "Pending Audit":
        df_filtered = df_filtered[df_filtered['status'] == 'Pending Audit']

    # Display count
    st.write(f"Showing **{len(df_filtered)}** accounts matching filter criteria:")
    
    # Table columns
    display_cols = [
        'account_id', 'username', 'risk_score', 'status',
        'ip_shared_count', 'device_shared_count', 'review_count', 'avg_rating', 'signup_time'
    ]
    
    # Selectbox selection
    selected_row = None
    if not df_filtered.empty:
        df_disp = df_filtered[display_cols].copy()
        df_disp['risk_score'] = df_disp['risk_score'].apply(lambda x: f"{x:.2%}")
        
        list_options = [f"{row['account_id']} - {row['username']} (Risk: {row['risk_score']})" for idx, row in df_disp.iterrows()]
        selected_option = st.selectbox("Select an account below to inspect detailed device fingerprint & review logs:", list_options)
        
        if selected_option:
            selected_id = selected_option.split(" ")[0]
            selected_row = df_scored[df_scored['account_id'] == selected_id].iloc[0]
            # Fetch scores across all models for comparison
            selected_row_all = df_scored_all[df_scored_all['account_id'] == selected_id].iloc[0]
    else:
        st.warning("No accounts found matching filters.")

    st.divider()

    # Detailed Audit Dashboard
    if selected_row is not None:
        st.markdown(f"### Audit Card: `{selected_row['account_id']}` ({selected_row['username']})")
        
        # Resolution Status Display
        current_status = get_status_str(selected_row['account_id'])
        if current_status == 'Suspended':
            action_info = actions_map[selected_row['account_id']]
            st.markdown(f'<span class="badge-suspended">🚫 SUSPENDED (Action Database Persistent)</span> by {action_info["user"]} on {action_info["timestamp"].strftime("%Y-%m-%d %H:%M:%S")}', unsafe_allow_html=True)
        elif current_status == 'Whitelisted':
            action_info = actions_map[selected_row['account_id']]
            st.markdown(f'<span class="badge-safe">🛡️ SAFE / WHITELISTED (Action Database Persistent)</span> by {action_info["user"]} on {action_info["timestamp"].strftime("%Y-%m-%d %H:%M:%S")}', unsafe_allow_html=True)
        elif current_status == 'Pending Audit':
            action_info = actions_map[selected_row['account_id']]
            st.markdown(f'<span class="badge-audit">⏳ PENDING AUDIT (Action Database Persistent)</span> assigned by {action_info["user"]} on {action_info["timestamp"].strftime("%Y-%m-%d %H:%M:%S")}', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge-unresolved">🔍 UNRESOLVED</span> flagged by active operational model', unsafe_allow_html=True)
            
        st.write("")
        
        # Model Comparison Bench for Selected User
        st.markdown("##### ⚙️ Multi-Model Benchmarking Scores")
        score_col1, score_col2, score_col3 = st.columns(3)
        with score_col1:
            st.metric(label="Random Forest Risk", value=f"{selected_row_all['risk_score_rf']:.2%}")
        with score_col2:
            st.metric(label="HistGBDT Risk", value=f"{selected_row_all['risk_score_gbdt']:.2%}")
        with score_col3:
            st.metric(label="Isolation Forest (Unsupervised Anomaly)", value=f"{selected_row_all['risk_score_unsup']:.2%}")
        
        st.write("")
        
        # Top level breakdown: Risk meter + Administration buttons
        card_col1, card_col2 = st.columns([1, 1])
        
        with card_col1:
            risk_pct = selected_row['risk_score'] * 100
            
            # Risk Gauge Chart
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = risk_pct,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': f"Active Risk Score ({model_code.upper()})", 'font': {'size': 16}},
                number = {'suffix': "%"},
                gauge = {
                    'axis': {'range': [None, 100], 'tickwidth': 1},
                    'bar': {'color': "#f15c22"},
                    'bgcolor': "white",
                    'borderwidth': 2,
                    'bordercolor': "#cbd5e1",
                    'steps': [
                        {'range': [0, 30], 'color': '#d1fae5'},
                        {'range': [30, 70], 'color': '#fef3c7'},
                        {'range': [70, 100], 'color': '#fee2e2'}
                    ]
                }
            ))
            fig_gauge.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                font={'family': "Arial"},
                height=220,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig_gauge, use_container_width=True)

        with card_col2:
            st.markdown("##### Administrative Remediation Enforcement")
            st.write("Write an override resolution to the persistent database:")
            
            act_sub1, act_sub2, act_sub3 = st.columns(3)
            with act_sub1:
                if st.button("🚫 Suspend/Ban", key="btn_suspend_v2", use_container_width=True):
                    save_manual_action(selected_row['account_id'], 'SUSPENDED')
                    st.success("Action saved persistently to audit_actions.json!")
                    st.rerun()
            with act_sub2:
                if st.button("🛡️ Approve / Safe", key="btn_safe_v2", use_container_width=True):
                    save_manual_action(selected_row['account_id'], 'SAFE')
                    st.success("Action saved persistently to audit_actions.json!")
                    st.rerun()
            with act_sub3:
                if st.button("⏳ Escalate Audit", key="btn_audit_v2", use_container_width=True):
                    save_manual_action(selected_row['account_id'], 'AUDIT')
                    st.success("Action saved persistently to audit_actions.json!")
                    st.rerun()
                    
            if current_status != 'Unresolved':
                if st.button("🔄 Clear manual override from DB", key="btn_reset_v2", type="secondary"):
                    save_manual_action(selected_row['account_id'], None)
                    st.success("Manual override cleared from persistent storage.")
                    st.rerun()
            
            st.divider()
            acc_meta = df_accounts[df_accounts['account_id'] == selected_row['account_id']].iloc[0]
            st.markdown(f"""
            - **Registration IP**: `{acc_meta['signup_ip']}`
            - **Hardware Device ID**: `{acc_meta['device_id']}`
            - **Registrant Country**: `{acc_meta['country']}`
            - **Signup Timestamp**: `{pd.to_datetime(acc_meta['signup_time']).strftime('%Y-%m-%d %H:%M:%S')}`
            """)

        # Compare features with cohorts
        st.markdown("##### 🔍 Deep-Dive Explainer: Feature Values vs Normal & Bot Cohorts")
        st.write("Comparing this user's behavior features to the medians of Genuine vs Bot accounts:")
        
        # Calculate medians
        gen_meds = df_scored_all[df_scored_all['is_fake'] == 0][clf.feature_cols].median()
        fake_meds = df_scored_all[df_scored_all['is_fake'] == 1][clf.feature_cols].median()
        
        feature_labels = {
            'ip_shared_count': 'IP sharing count (exact match)',
            'subnet_shared_count': 'Subnet sharing count (/24 match)',
            'device_shared_count': 'Hardware Device reuse count',
            'review_count': 'Total posted reviews',
            'avg_rating': 'Average review score',
            'rating_std': 'Rating standard deviation',
            'extreme_rating_ratio': 'Ratio of 1 or 5 star reviews',
            'min_delay_hours': 'Min delay between registration & review (hrs)',
            'avg_delay_hours': 'Avg delay between registration & review (hrs)',
            'seller_entropy': 'Seller review entropy (lower = concentrated)',
            'avg_text_freq': 'Average text duplicity across system'
        }
        
        explain_rows = []
        for feat in clf.feature_cols:
            val = selected_row[feat]
            gen_val = gen_meds[feat]
            fake_val = fake_meds[feat]
            
            # Simple heuristic risk assessment for visualization
            risk_level = "🟢 Low"
            if feat in ['ip_shared_count', 'subnet_shared_count', 'device_shared_count'] and val > 0:
                risk_level = "🔴 High" if val > 2 else "🟡 Medium"
            elif feat == 'min_delay_hours' and val < 24:
                risk_level = "🔴 High"
            elif feat == 'avg_text_freq' and val > 2:
                risk_level = "🔴 High"
            elif feat == 'seller_entropy' and selected_row['review_count'] > 1 and val < 0.5:
                risk_level = "🔴 High"
                
            explain_rows.append({
                'Indicator': feature_labels[feat],
                'User Value': f"{val:.4f}" if isinstance(val, float) else str(val),
                'Genuine User Median': f"{gen_val:.4f}" if isinstance(gen_val, float) else str(gen_val),
                'Bot Account Median': f"{fake_val:.4f}" if isinstance(fake_val, float) else str(fake_val),
                'Feature Risk Level': risk_level
            })
            
        st.table(pd.DataFrame(explain_rows))
        
        # User Review History Table
        st.markdown("##### 📝 Review History Log")
        user_revs = df_reviews[df_reviews['account_id'] == selected_row['account_id']].copy()
        
        if not user_revs.empty:
            user_revs['review_time'] = pd.to_datetime(user_revs['review_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            user_revs = user_revs.sort_values(by='review_time', ascending=False)
            st.dataframe(
                user_revs[['review_id', 'product_id', 'seller_id', 'rating', 'review_time', 'review_text']],
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("This user has not submitted any review logs yet.")

# ----------------- TAB 3: MODEL COMPARISON & SANDBOX -----------------

with tab_sandbox:
    st.subheader("Model Benchmarking & Competing Objectives Sandbox")
    st.write("""
        Risk Engineering requires balancing **competing objectives**: catching as much fraud as possible (high Recall) 
        while minimizing customer friction and false bans of genuine users (low False Positive Rate).
    """)
    
    # 1. Operational Threshold Simulator
    st.markdown("### 🎛️ Operational Threshold Simulator")
    
    sim_col1, sim_col2 = st.columns([1, 1.2])
    
    with sim_col1:
        st.markdown("##### Adjust Operational Enforcement Level")
        sim_threshold = st.slider(
            "Enforcement Threshold (Risk cutoff)", 
            min_value=0.0, 
            max_value=1.0, 
            value=0.50, 
            step=0.05,
            key="sim_slider_threshold"
        )
        
        # Calculate rates for selected threshold and active model
        # Target labels y and predicted probabilities y_prob
        y_true = df_scored['is_fake']
        y_prob = df_scored['risk_score']
        
        flagged = y_prob >= sim_threshold
        actual_fake = y_true == 1
        actual_gen = y_true == 0
        
        total_fakes = actual_fake.sum()
        total_gens = actual_gen.sum()
        
        true_positives = (flagged & actual_fake).sum()
        false_positives = (flagged & actual_gen).sum()
        
        recall_rate = true_positives / total_fakes if total_fakes > 0 else 0.0
        fpr_rate = false_positives / total_gens if total_gens > 0 else 0.0
        precision_rate = true_positives / flagged.sum() if flagged.sum() > 0 else 0.0
        
        st.write("")
        st.metric(
            label="🎯 Scammer Catch Rate (Recall / Sensitivity)", 
            value=f"{recall_rate:.2%}",
            help="Percentage of total fake accounts that are caught and flagged by the model."
        )
        st.metric(
            label="⚠️ Customer Friction Rate (False Positive Rate)", 
            value=f"{fpr_rate:.2%}",
            delta="- Lower is better",
            delta_color="normal" if fpr_rate > 0.05 else "inverse",
            help="Percentage of completely genuine users who are incorrectly flagged, resulting in false bans and customer friction."
        )
        st.metric(
            label="🎯 Target Precision", 
            value=f"{precision_rate:.2%}",
            help="When the AI flags an account, the probability that it actually is a fake account."
        )

    with sim_col2:
        st.markdown("##### Operational Curve (FPR vs TPR Trade-off)")
        
        # Generate full ROC curve coordinates
        fpr_curve, tpr_curve, thresholds = roc_curve(y_true, y_prob)
        
        fig_roc = go.Figure()
        
        # Diagonal random line
        fig_roc.add_trace(go.Scatter(
            x=[0, 1], y=[0, 1], 
            line=dict(dash='dash', color='#cbd5e1'),
            name="Random Guess"
        ))
        
        # Model ROC Line
        fig_roc.add_trace(go.Scatter(
            x=fpr_curve, y=tpr_curve,
            mode='lines',
            line=dict(color='#4f46e5', width=3),
            name=f"ROC ({model_code.upper()})",
            hovertext=[f"Threshold: {t:.2%}" for t in thresholds]
        ))
        
        # Current Operating Point Dot
        fig_roc.add_trace(go.Scatter(
            x=[fpr_rate], y=[recall_rate],
            mode='markers',
            marker=dict(size=14, color='#dc2626', line=dict(width=2, color='white')),
            name="Operational Threshold Point"
        ))
        
        fig_roc.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(title="False Positive Rate (Friction)", showgrid=True, gridcolor='#e2e8f0', range=[-0.02, 1.02]),
            yaxis=dict(title="True Positive Rate (Recall)", showgrid=True, gridcolor='#e2e8f0', range=[-0.02, 1.02]),
            margin=dict(l=40, r=40, t=10, b=40),
            height=340,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_roc, use_container_width=True)

    st.divider()

    # 2. Benchmark Supervised Models (RF vs GBDT vs Unsupervised)
    st.markdown("### 📊 Model Performance Benchmarking (A/B Test Verification)")
    st.write("Below are the evaluation metrics computed on the test dataset split (30% holdout):")
    
    # Split training dataset locally for instant evaluation
    from sklearn.model_selection import train_test_split
    
    train_acc, test_acc = train_test_split(df_accounts, test_size=0.3, random_state=42, stratify=df_accounts['is_fake'])
    train_rev = df_reviews[df_reviews['account_id'].isin(train_acc['account_id'])]
    test_rev = df_reviews[df_reviews['account_id'].isin(test_acc['account_id'])]
    
    # Evaluate
    eval_metrics = clf.evaluate(test_acc, test_rev)
    
    bench_data = []
    for model_name, metrics in eval_metrics.items():
        name_map = {
            'rf': 'Random Forest (Supervised Ensemble)',
            'gbdt': 'HistGradientBoosting (GBDT Supervised)',
            'unsup': 'Isolation Forest (Unsupervised Anomaly)'
        }
        bench_data.append({
            'Model Architecture': name_map[model_name],
            'Accuracy': f"{metrics['accuracy']:.2%}",
            'Precision (Fake Account)': f"{metrics['precision_fake']:.2%}",
            'Recall (Catch Rate)': f"{metrics['recall_fake']:.2%}",
            'F1-Score': f"{metrics['f1_fake']:.2%}",
            'Area under ROC (AUC)': f"{metrics['roc_auc']:.4f}"
        })
        
    st.table(pd.DataFrame(bench_data))
    
    with st.expander("🔬 Retrain Simulation Engine Settings"):
        st.write("Adjust the baseline simulation density to retrain the models from scratch:")
        
        sim_col_s1, sim_col_s2, sim_col_s3 = st.columns(3)
        with sim_col_s1:
            param_genuine = st.number_input("Genuine Accounts Count", min_value=100, max_value=5000, value=1000, step=100)
        with sim_col_s2:
            param_fake = st.number_input("Fake Accounts Count", min_value=10, max_value=1000, value=120, step=10)
        with sim_col_s3:
            param_severity = st.slider("Collusion Ratio", 0.1, 1.0, 0.85)
            
        if st.button("🧪 Re-run Simulation & Retrain All Models", type="primary"):
            get_session_data(
                num_genuine=param_genuine,
                num_fake=param_fake,
                attack_severity=param_severity,
                force=True
            )
            st.success("Re-simulation complete. Models retrained successfully!")
            st.rerun()

# ----------------- TAB 4: BATCH CLASSIFIER UPLOAD -----------------

with tab_batch:
    st.subheader("Process Batch Log Files")
    st.write("""
        Upload CSV log files containing registration metadata and review logs to execute the classifier.
        You can inspect flagged anomalies and download the results.
    """)
    
    # Select Batch Scoring Model
    st.markdown("##### 1. Select Batch Scoring Configuration")
    batch_model_desc = st.selectbox(
        "Select Scoring Engine Model",
        options=["Random Forest (Supervised)", "GBDT / HistGradientBoosting (Supervised)", "Isolation Forest (Unsupervised)"],
        key="batch_model_selector"
    )
    batch_model_code = "rf"
    if "GBDT" in batch_model_desc:
        batch_model_code = "gbdt"
    elif "Isolation Forest" in batch_model_desc:
        batch_model_code = "unsup"
        
    st.divider()
    
    # Provide templates
    st.markdown("##### 2. Download Demo Datasets")
    st.write("Download these templates to see the expected layout or test the uploader directly:")
    
    # Construct CSVs to download
    acc_buffer = io.StringIO()
    df_accounts[['account_id', 'username', 'signup_time', 'signup_ip', 'device_id', 'country']].to_csv(acc_buffer, index=False)
    csv_accounts_data = acc_buffer.getvalue()
    
    rev_buffer = io.StringIO()
    df_reviews[['review_id', 'account_id', 'product_id', 'seller_id', 'rating', 'review_time', 'review_text']].to_csv(rev_buffer, index=False)
    csv_reviews_data = rev_buffer.getvalue()
    
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            label="📥 Download Demo Accounts Log (.csv)",
            data=csv_accounts_data,
            file_name="demo_accounts.csv",
            mime="text/csv",
            use_container_width=True
        )
    with dl_col2:
        st.download_button(
            label="📥 Download Demo Reviews Log (.csv)",
            data=csv_reviews_data,
            file_name="demo_reviews.csv",
            mime="text/csv",
            use_container_width=True
        )
        
    st.divider()
    
    st.markdown("##### 3. Upload Logs for Scoring")
    up_col1, up_col2 = st.columns(2)
    
    with up_col1:
        uploaded_accounts = st.file_uploader("Upload Accounts CSV", type=["csv"], help="Expected columns: account_id, username, signup_time, signup_ip, device_id, country")
    with up_col2:
        uploaded_reviews = st.file_uploader("Upload Reviews CSV", type=["csv"], help="Expected columns: review_id, account_id, product_id, seller_id, rating, review_time, review_text")
        
    if uploaded_accounts and uploaded_reviews:
        try:
            df_up_acc = pd.read_csv(uploaded_accounts)
            df_up_rev = pd.read_csv(uploaded_reviews)
            
            # Convert registration time formats
            df_up_acc['signup_time'] = pd.to_datetime(df_up_acc['signup_time'])
            df_up_rev['review_time'] = pd.to_datetime(df_up_rev['review_time'])
            
            with st.spinner("Scoring uploaded accounts..."):
                # Predict risk scores using active model
                df_scored_batch = clf.predict_risk(df_up_acc, df_up_rev, model_type=batch_model_code)
                
                # Show summary
                total_batch = len(df_scored_batch)
                flagged_batch = (df_scored_batch['risk_score'] >= op_threshold).sum()
                
                st.success(f"Processing complete! Scored **{total_batch}** accounts using {batch_model_desc}. Found **{flagged_batch}** flagged anomalies (above threshold {op_threshold:.0%}).")
                
                # Plotly distribution for batch
                fig_batch = px.histogram(
                    df_scored_batch, 
                    x='risk_score',
                    title="Batch Risk Score Distribution",
                    labels={'risk_score': 'Risk Score'},
                    color_discrete_sequence=['#4f46e5']
                )
                fig_batch.add_vline(x=op_threshold, line_width=3, line_dash="dash", line_color="#dc2626")
                fig_batch.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    height=280
                )
                st.plotly_chart(fig_batch, use_container_width=True)
                
                # Display flagged items
                df_flagged_batch = df_scored_batch[df_scored_batch['risk_score'] >= op_threshold].sort_values(by='risk_score', ascending=False)
                
                st.write("##### Flagged Accounts:")
                st.dataframe(
                    df_flagged_batch[['account_id', 'username', 'risk_score', 'ip_shared_count', 'device_shared_count', 'review_count']],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Download link for results
                out_buffer = io.StringIO()
                df_scored_batch.to_csv(out_buffer, index=False)
                st.download_button(
                    label="📥 Download Scored Accounts Results (.csv)",
                    data=out_buffer.getvalue(),
                    file_name="scored_accounts_results.csv",
                    mime="text/csv",
                    type="primary"
                )
        except Exception as e:
            st.error(f"Error parsing log files: {e}")
            st.info("Please verify that the column names match the templates exactly.")
