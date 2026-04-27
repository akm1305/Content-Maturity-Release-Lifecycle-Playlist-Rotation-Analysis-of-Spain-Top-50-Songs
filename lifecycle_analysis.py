import pandas as pd
import numpy as np

def validate_and_normalize(df):
    """
    Data Validation & Normalization
    - Ensure date parsing
    - Normalize song and artist naming
    """
    df = df.copy()
    # Parse date appropriately
    df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y', errors='coerce')
    
    # Text normalization
    df['song'] = df['song'].astype(str).str.title().str.strip()
    df['artist'] = df['artist'].astype(str).str.title().str.strip()
    
    # Create unique identifier
    df['track_id'] = df['song'] + " - " + df['artist']
    
    # Sort
    df = df.sort_values(by=['date', 'position'])
    
    return df

def construct_lifecycle(df):
    """
    Song Lifecycle Construction
    Calculates Entry Date, Exit Date, Total Days, Peak Position, Time to Peak
    """
    # Group by track
    lifecycle = df.groupby('track_id').agg(
        entry_date=('date', 'min'),
        exit_date=('date', 'max'),
        total_days=('date', 'nunique'),
        peak_position=('position', 'min'), # lower number is better position
        is_explicit=('is_explicit', 'first'),
        album_type=('album_type', 'first'),
        duration_ms=('duration_ms', 'first'),
        total_tracks=('total_tracks', 'first')
    ).reset_index()
    
    # Calculate time to peak
    peak_dates = df.loc[df.groupby('track_id')['position'].idxmin(), ['track_id', 'date']]
    peak_dates = peak_dates.rename(columns={'date': 'peak_date'})
    lifecycle = lifecycle.merge(peak_dates, on='track_id')
    
    lifecycle['time_to_peak'] = (lifecycle['peak_date'] - lifecycle['entry_date']).dt.days
    
    return lifecycle

def classify_lifecycle_stage(df, lifecycle_df):
    """
    Lifecycle Stage Classification
    - New Entry (<= 7 days)
    - Growth Phase (rank improving)
    - Peak Phase (Top 10 stability)
    - Mature Phase (stable mid-rank)
    - Decline Phase (rank deterioration)
    Returns df with a 'stage' column for the current date
    """
    # Merge entry_date to calculate age
    df = df.merge(lifecycle_df[['track_id', 'entry_date', 'peak_position']], on='track_id', how='left')
    df['days_since_entry'] = (df['date'] - df['entry_date']).dt.days
    
    stages = []
    
    # To determine growth/decline, we need rank history.
    # A simpler proxy approach for today's snapshot:
    for idx, row in df.iterrows():
        if row['days_since_entry'] <= 7:
            stages.append('New Entry')
        elif row['position'] <= 10:
            stages.append('Peak Phase')
        elif row['position'] > row['peak_position'] + 10:
            stages.append('Decline Phase')
        elif row['days_since_entry'] > 30 and 10 < row['position'] <= 30:
            stages.append('Mature Phase')
        else:
            stages.append('Growth Phase')
            
    df['stage'] = stages
    return df

def calculate_churn(df):
    """
    Playlist Rotation & Churn Analysis
    Calculate daily entries and exits.
    """
    # Tracks per day
    daily_tracks = df.groupby('date')['track_id'].apply(set).to_dict()
    dates = sorted(list(daily_tracks.keys()))
    
    churn_data = []
    for i in range(1, len(dates)):
        prev_date = dates[i-1]
        curr_date = dates[i]
        
        prev_set = daily_tracks[prev_date]
        curr_set = daily_tracks[curr_date]
        
        entries = len(curr_set - prev_set)
        exits = len(prev_set - curr_set)
        
        churn_rate = (entries + exits) / 100.0 # Turnover percentage
        
        churn_data.append({
            'date': curr_date,
            'entries': entries,
            'exits': exits,
            'churn_rate': churn_rate
        })
        
    return pd.DataFrame(churn_data)

def get_kpis(lifecycle_df, churn_df):
    """
    Key Performance Indicators (KPIs)
    """
    kpis = {}
    
    kpis['Average Days on Playlist'] = round(lifecycle_df['total_days'].mean(), 1)
    kpis['Entry-to-Peak Time'] = round(lifecycle_df['time_to_peak'].mean(), 1)
    
    if not churn_df.empty:
        kpis['Playlist Churn Rate'] = f"{round(churn_df['churn_rate'].mean() * 100, 1)}%"
    else:
        kpis['Playlist Churn Rate'] = "N/A"
        
    kpis['Retention Stability Index'] = round((lifecycle_df['total_days'] > 30).mean() * 100, 1) # % of songs lasting > 30 days
    
    explicit_days = lifecycle_df[lifecycle_df['is_explicit'] == True]['total_days'].mean()
    clean_days = lifecycle_df[lifecycle_df['is_explicit'] == False]['total_days'].mean()
    
    kpis['Explicit Content Lifecycle Score'] = round(explicit_days / clean_days, 2) if clean_days > 0 else 0
    
    single_days = lifecycle_df[lifecycle_df['album_type'] == 'single']['total_days'].mean()
    album_days = lifecycle_df[lifecycle_df['album_type'] == 'album']['total_days'].mean()
    
    kpis['Single vs Album Longevity Ratio'] = round(single_days / album_days, 2) if album_days > 0 else 0
    
    return kpis

