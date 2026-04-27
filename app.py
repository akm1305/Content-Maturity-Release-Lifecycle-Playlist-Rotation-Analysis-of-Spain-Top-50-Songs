import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from lifecycle_analysis import validate_and_normalize, construct_lifecycle, classify_lifecycle_stage, calculate_churn, get_kpis

# --- Setup Page with Branding ---
st.set_page_config(
    page_title="Spain Top 50 Insights | Atlantic Records",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Atlantic Records Branding (Red, Black, White)
st.markdown("""
    <style>
    /* Main Area Styling */
    .stApp {
        background-color: #0b0b0b;
        color: #f7f7f7;
    }
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #ffffff;
        font-family: 'Helvetica Neue', Arial, sans-serif;
    }
    h1 {
        border-bottom: 3px solid #E32636;
        padding-bottom: 10px;
        margin-bottom: 20px;
    }
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #1a1a1a;
        color: white;
    }
    /* KPI Cards */
    div[data-testid="stMetricValue"] {
        color: #E32636;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# --- Data Loading ---
@st.cache_data
def load_data():
    df = pd.read_csv("Atlantic_Spain (1).csv")
    df = validate_and_normalize(df)
    return df

df_raw = load_data()

# Process Data Objects
@st.cache_data
def process_data(df):
    lifecycle_df = construct_lifecycle(df)
    churn_df = calculate_churn(df)
    staged_df = classify_lifecycle_stage(df, lifecycle_df)
    return lifecycle_df, churn_df, staged_df

lifecycle_df, churn_df, staged_df = process_data(df_raw)

# --- Subsetting Data for Filters ---
# Merge staged_df back to lifecycle_df for some unified filtering
merged_df = staged_df.merge(lifecycle_df.drop(columns=['peak_position', 'is_explicit', 'album_type', 'duration_ms', 'total_tracks']), on='track_id', suffixes=('', '_y'))

# --- Sidebar Filters ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/Atlantic_Records_logo.svg/1200px-Atlantic_Records_logo.svg.png", width=150)
st.sidebar.header("Filter Analytics")

# Date range
min_date = df_raw['date'].min().date()
max_date = df_raw['date'].max().date()

date_range = st.sidebar.date_input("Select Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

# Filters
all_stages = staged_df['stage'].unique().tolist()
selected_stages = st.sidebar.multiselect("Lifecycle Stage", options=all_stages, default=all_stages)

explicit_toggle = st.sidebar.radio("Explicit Content", options=["All", "Explicit Only", "Clean Only"], index=0)

album_options = staged_df['album_type'].unique().tolist()
selected_albums = st.sidebar.multiselect("Album Type", options=album_options, default=album_options)


# --- Apply Filters ---
filtered_df = staged_df.copy()

if len(date_range) == 2:
    start_date, end_date = date_range
    filtered_df = filtered_df[(filtered_df['date'].dt.date >= start_date) & (filtered_df['date'].dt.date <= end_date)]

filtered_df = filtered_df[filtered_df['stage'].isin(selected_stages)]

if explicit_toggle == "Explicit Only":
    filtered_df = filtered_df[filtered_df['is_explicit'] == True]
elif explicit_toggle == "Clean Only":
    filtered_df = filtered_df[filtered_df['is_explicit'] == False]

filtered_df = filtered_df[filtered_df['album_type'].isin(selected_albums)]

# Active tracks in filtered view
active_tracks = filtered_df['track_id'].unique()
filtered_lifecycle = lifecycle_df[lifecycle_df['track_id'].isin(active_tracks)]

# Calculate context specific KPIs based on filtered_lifecycle (Though Churn is usually global, we adjust lifecycle KPIs)
kpis = get_kpis(filtered_lifecycle, churn_df)

# --- Main App ---
st.title("Content Maturity & Release Lifecycle")
st.markdown("*Spain Top 50 Playlist Analytics - Atlantic Records Strategic Insights*")

# --- Overview KPIs ---
st.subheader("Market Performance Dynamics")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Avg Days on Playlist", f"{kpis['Average Days on Playlist']}")
with col2:
    st.metric("Entry-to-Peak Time", f"{kpis['Entry-to-Peak Time']} days")
with col3:
    st.metric("Retention Stability (>30d)", f"{kpis['Retention Stability Index']}%")
with col4:
    st.metric("Daily Churn Rate", kpis['Playlist Churn Rate'])


st.markdown("---")
# --- Visualizations ---

col_viz1, col_viz2 = st.columns([2, 1])

with col_viz1:
    st.subheader("Song Lifecycle Timeline (Position Over Time)")
    # We plot position over time. To avoid clutter, just peak top 20 lines if large, or show scatter.
    timeline_df = filtered_df.copy()
    if len(active_tracks) > 30:
        # If too many, sample a few for visual clarity or highlight top ones
        top_tracks = filtered_lifecycle.sort_values(by='total_days', ascending=False).head(15)['track_id'].tolist()
        timeline_df = timeline_df[timeline_df['track_id'].isin(top_tracks)]
        st.caption("Showing Top 15 Tracks by Longevity for visual clarity in current filter.")
    
    fig_timeline = px.line(timeline_df, x="date", y="position", color="song", hover_name="track_id", 
                           color_discrete_sequence=px.colors.qualitative.Bold)
    fig_timeline.update_layout(yaxis_autorange="reversed", plot_bgcolor="#111111", paper_bgcolor="#0b0b0b", font_color="white")
    st.plotly_chart(fig_timeline, use_container_width=True)

with col_viz2:
    st.subheader("Lifecycle Stage Distribution")
    stage_counts = filtered_df.groupby('stage').size().reset_index(name='count')
    # Use red scale to match branding
    red_scale = ["#FF0000", "#CC0000", "#990000", "#660000", "#330000"]
    fig_stage = px.pie(stage_counts, values='count', names='stage', hole=0.4,
                       color_discrete_sequence=red_scale)
    fig_stage.update_layout(plot_bgcolor="#111111", paper_bgcolor="#0b0b0b", font_color="white")
    st.plotly_chart(fig_stage, use_container_width=True)

st.markdown("---")

col_viz3, col_viz4 = st.columns(2)

with col_viz3:
    st.subheader("Playlist Churn (Entry vs Exit Flow)")
    if len(date_range) == 2:
        flow_df = churn_df[(churn_df['date'].dt.date >= start_date) & (churn_df['date'].dt.date <= end_date)]
    else:
        flow_df = churn_df
        
    fig_flow = go.Figure()
    fig_flow.add_trace(go.Bar(x=flow_df['date'], y=flow_df['entries'], name='Entries', marker_color='#E32636'))
    fig_flow.add_trace(go.Bar(x=flow_df['date'], y=-flow_df['exits'], name='Exits', marker_color='#555555'))
    fig_flow.update_layout(barmode='relative', plot_bgcolor="#111111", paper_bgcolor="#0b0b0b", font_color="white",
                           yaxis_title="Movement Count")
    st.plotly_chart(fig_flow, use_container_width=True)

with col_viz4:
    st.subheader("Content Maturity Comparisons")
    # Using explicit vs clean and single vs album longevity
    comp_data = {
        'Category': ['Explicit vs Clean', 'Explicit vs Clean', 'Single vs Album', 'Single vs Album'],
        'Type': ['Explicit', 'Clean', 'Single', 'Album'],
        'Avg Days on Playlist': [
            filtered_lifecycle[filtered_lifecycle['is_explicit'] == True]['total_days'].mean(),
            filtered_lifecycle[filtered_lifecycle['is_explicit'] == False]['total_days'].mean(),
            filtered_lifecycle[filtered_lifecycle['album_type'] == 'single']['total_days'].mean(),
            filtered_lifecycle[filtered_lifecycle['album_type'] == 'album']['total_days'].mean()
        ]
    }
    comp_df = pd.DataFrame(comp_data).fillna(0) # In case of nan
    
    fig_comp = px.bar(comp_df, x='Category', y='Avg Days on Playlist', color='Type', barmode='group',
                      color_discrete_map={'Explicit': '#E32636', 'Clean': '#FFFFFF', 'Single': '#E32636', 'Album': '#444444'})
    fig_comp.update_layout(plot_bgcolor="#111111", paper_bgcolor="#0b0b0b", font_color="white")
    st.plotly_chart(fig_comp, use_container_width=True)

st.markdown("---")
st.caption("Data Intelligence Application prepared for Atlantic Recording Corporation")
