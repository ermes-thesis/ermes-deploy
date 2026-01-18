import streamlit as st
import pandas as pd
import json
import glob
import os
import networkx as nx
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import numpy as np
import time
import math
import io

# --- CONFIGURATION ---
LOG_PATTERN = "./logs/**/*.ndjson" 
# How long (in seconds) to keep a node's data visible if no new dump arrives.
DATA_TTL_SECONDS = 15 
# Threshold: Clusters are formed in chunks of this size.
CLUSTER_SIZE = 100

# Set page to wide mode for better visualization
st.set_page_config(page_title="Ermes Visualizer", layout="wide")

# --- UI TWEAK: REMOVE TOP PADDING ---
st.markdown("""
        <style>
               .block-container {
                    padding-top: 0rem;
                    padding-bottom: 0rem;
                    margin-top: 0rem;
                }
                /* Optional: Hides the default hamburger menu and header bar */
                header {visibility: hidden;} 
        </style>
        """, unsafe_allow_html=True)

def get_node_name_from_path(filepath):
    directory = os.path.dirname(filepath)
    return os.path.basename(directory)

@st.cache_data
def load_data():
    all_records = []
    files = glob.glob(LOG_PATTERN, recursive=True)
    
    if not files:
        return pd.DataFrame()

    for filepath in files:
        if os.path.isdir(filepath): continue
        
        node_id = get_node_name_from_path(filepath)
        
        with open(filepath, 'r') as f:
            for line in f:
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    if data.get('is_local') is not True: continue

                    is_strong = data.get('is_strong')
                    if is_strong:
                        c_type = 'Sequential'
                    else:
                        c_type = 'Eventual' 

                    all_records.append({
                        'raw_time': data['timestamp'],
                        'collection_id': data['collection_id'],
                        'node_id': node_id,
                        'is_leader': data.get('is_leader', False),
                        'collection_size': data.get('collection_size', 10),
                        'consistency': c_type
                    })
                except (json.JSONDecodeError, KeyError):
                    continue

    df = pd.DataFrame(all_records)
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['raw_time'])
        df = df.sort_values('timestamp')
    
    return df

def get_snapshot_at_time(df, current_time, all_nodes, ttl_seconds):
    current_frame_rows = []
    for node in all_nodes:
        node_df = df[df['node_id'] == node]
        past_dumps = node_df[node_df['timestamp'] <= current_time]
        
        if not past_dumps.empty:
            last_dump_time = past_dumps['timestamp'].max()
            if (current_time - last_dump_time).total_seconds() <= ttl_seconds:
                snapshot = past_dumps[past_dumps['timestamp'] == last_dump_time]
                current_frame_rows.append(snapshot)

    if current_frame_rows:
        return pd.concat(current_frame_rows)
    else:
        return pd.DataFrame(columns=df.columns)

def get_collection_history(df, collection_id):
    if df.empty: return pd.DataFrame()
    history = df[df['collection_id'] == collection_id].copy()
    history = history.sort_values('timestamp')
    return history[['timestamp', 'node_id', 'is_leader', 'collection_size', 'consistency']]

def get_node_path_str(df, collection_id, current_time):
    """
    Returns a string representing the history of nodes for a collection ID 
    up to the current_time (e.g., '57 -> 55 -> 50').
    Only tracks LEADERS to avoid noise from replicas.
    """
    # Filter for specific collection, time, AND IS_LEADER
    mask = (df['collection_id'] == collection_id) & \
           (df['timestamp'] <= current_time) & \
           (df['is_leader'] == True)
           
    history = df.loc[mask, 'node_id']
    
    if history.empty:
        return "Unknown"
    
    # Identify changes: keep row if it's the first row OR if node_id is different from previous
    # This preserves order and removes consecutive duplicates
    changes = history.loc[history.shift() != history]
    
    # Format names (take last part of IP if present to save space)
    names = [n.split('.')[-1] if '.' in n else n for n in changes]
    return " → ".join(names)

def calculate_spiral_offset(i, total_count, cluster_mode=False):
    if total_count == 1:
        return 0, 0
    
    if cluster_mode:
        # Use wider spiral immediately for clusters to ensure spacing
        # Skip circle mode to avoid fixed-radius overlap issues with large markers
        golden_angle = 2.39996 
        spread = 0.065 # Tight layout
        r = spread * math.sqrt(i + 1)
        theta = i * golden_angle
        return r * math.cos(theta), r * math.sin(theta)
        
    elif total_count <= 12:
        rad = 0.25
        ang = (2 * math.pi * i / total_count) - (math.pi / 2)
        return rad * math.cos(ang), rad * math.sin(ang)
    else:
        golden_angle = 2.39996 
        spread = 0.06           
        r = spread * math.sqrt(i + 1)
        theta = i * golden_angle
        return r * math.cos(theta), r * math.sin(theta)

# --- ENGINE 1: MATPLOTLIB (FAST / ANIMATION / NO FLICKER) ---
def create_matplotlib_figure(G, pos, current_frame_df, selected_collections, current_time_label, all_nodes):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_ylim(-0.5, 2.5)
    ax.set_xlim(-3.5, 3.5)

    # Draw Infrastructure
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color='#aaaaaa', width=2)
    nodes_draw = nx.draw_networkx_nodes(G, pos, ax=ax, node_size=2000, node_color='#e0e0e0', edgecolors='black')
    nodes_draw.set_zorder(2)
    
    labels = {n: n.split('.')[-1] if '.' in n else n for n in all_nodes}
    labels_draw = nx.draw_networkx_labels(G, pos, ax=ax, labels=labels, font_size=10, font_weight='bold')
    for _, t in labels_draw.items(): t.set_zorder(3)

    # Group Data
    node_groups = {}
    active_leaders = 0
    active_replicas = 0

    for _, row in current_frame_df.iterrows():
        if selected_collections and row['collection_id'] not in selected_collections: continue
        if row['is_leader']: active_leaders += 1
        else: active_replicas += 1

        nid = row['node_id']
        if nid not in node_groups: node_groups[nid] = []
        node_groups[nid].append(row)

    x_vals, y_vals, colors, sizes = [], [], [], []

    for nid, rows in node_groups.items():
        if nid not in pos: continue
        base_x, base_y = pos[nid]
        
        # Split into Chunks of CLUSTER_SIZE
        item_elements = []
        cluster_elements = []
        
        # 1. Create Chunks
        num_items = len(rows)
        chunks = [rows[i:i + CLUSTER_SIZE] for i in range(0, num_items, CLUSTER_SIZE)]
        
        for chunk in chunks:
            if len(chunk) == CLUSTER_SIZE:
                cluster_elements.append({'type': 'cluster', 'count': len(chunk)})
            else:
                for item in chunk:
                    item_elements.append({'type': 'item', 'data': item})

        # 2. Combine: Items first, Clusters last
        visual_elements = item_elements + cluster_elements
        count = len(visual_elements)
        
        has_clusters = len(cluster_elements) > 0

        for i, elem in enumerate(visual_elements):
            off_x, off_y = calculate_spiral_offset(i, count, cluster_mode=has_clusters)
            
            x_vals.append(base_x + off_x)
            y_vals.append(base_y + off_y)
            
            if elem['type'] == 'cluster':
                colors.append('#F5A927') # Gold for cluster
                sizes.append(1200)       # Big size
            else:
                row = elem['data']
                colors.append('#ff4444' if row['is_leader'] else '#4444ff')
                
                plotly_size_equivalent = 12 if selected_collections else max(6, min(15, row['collection_size'] / 5))
                mpl_size = (plotly_size_equivalent ** 2) * 0.8
                sizes.append(mpl_size)

    if x_vals:
        ax.scatter(x_vals, y_vals, c=colors, s=sizes, alpha=0.9, edgecolors='white', linewidth=1.0, zorder=4)

    ax.set_title(f"State at {current_time_label}", fontsize=14)
    ax.axis('off')
    return fig, active_leaders, active_replicas

# --- ENGINE 2: PLOTLY (INTERACTIVE / SLIDER) ---
def create_plotly_figure(G, pos, current_frame_df, selected_collections, current_time_label, all_nodes, full_df, current_dt):
    fig = go.Figure()

    # 1. Edges
    edge_x, edge_y = [], []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=2, color='#aaaaaa'),
        hoverinfo='none', mode='lines', name='Connections'
    ))

    # 2. Nodes
    node_x, node_y, node_text = [], [], []
    for node in all_nodes:
        if node in pos:
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            node_text.append(node.split('.')[-1] if '.' in node else node)

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        marker=dict(size=45, color='#e0e0e0', line=dict(width=2, color='black')),
        text=node_text, textposition="middle center",
        textfont=dict(size=12, color='black', family="monospace", weight='bold'),
        hoverinfo='text', hovertext=[f"Node: {n}" for n in all_nodes], name='Nodes'
    ))

    # 3. Collections & Clusters
    node_groups = {}
    active_leaders, active_replicas = 0, 0
    
    for _, row in current_frame_df.iterrows():
        if selected_collections and row['collection_id'] not in selected_collections: continue
        if row['is_leader']: active_leaders += 1
        else: active_replicas += 1

        nid = row['node_id']
        if nid not in node_groups: node_groups[nid] = []
        node_groups[nid].append(row)

    # Arrays for Plotly
    item_x, item_y, item_c, item_s, item_custom, item_hover = [], [], [], [], [], []
    clust_x, clust_y, clust_s, clust_custom, clust_hover = [], [], [], [], []

    for nid, rows in node_groups.items():
        if nid not in pos: continue
        base_x, base_y = pos[nid]
        
        # Split into Chunks
        num_items = len(rows)
        chunks = [rows[i:i + CLUSTER_SIZE] for i in range(0, num_items, CLUSTER_SIZE)]
        
        # Separate lists for sorting
        item_elements = []
        cluster_elements = []

        for chunk in chunks:
            if len(chunk) == CLUSTER_SIZE:
                ids_in_cluster = [r['collection_id'] for r in chunk]
                cluster_elements.append({'type': 'cluster', 'ids': ids_in_cluster})
            else:
                for item in chunk:
                    item_elements.append({'type': 'item', 'data': item})
        
        # Combine: Items FIRST, Clusters LAST
        visual_elements = item_elements + cluster_elements
        count = len(visual_elements)
        has_clusters = len(cluster_elements) > 0

        for i, elem in enumerate(visual_elements):
            off_x, off_y = calculate_spiral_offset(i, count, cluster_mode=has_clusters)
            abs_x = base_x + off_x
            abs_y = base_y + off_y
            
            if elem['type'] == 'cluster':
                clust_x.append(abs_x)
                clust_y.append(abs_y)
                clust_s.append(60)
                # Store NODE ID in customdata to ensure correct sidebar lookup
                id_str = f"CLUSTER|{nid}|" + ",".join(elem['ids'])
                clust_custom.append(id_str)
                clust_hover.append(f"Cluster of {CLUSTER_SIZE} items<br>Click to view IDs")
            else:
                row = elem['data']
                item_x.append(abs_x)
                item_y.append(abs_y)
                item_c.append('#ff4444' if row['is_leader'] else '#4444ff')
                
                s = 12 if selected_collections else max(6, min(15, row['collection_size'] / 5))
                item_s.append(s)
                item_custom.append(row['collection_id']) 
                
                role = "Leader" if row['is_leader'] else "Replica"
                
                # --- CALCULATE HISTORY FOR HOVER ---
                # Only show history for leaders, filtered by LEADERSHIP movement
                if row['is_leader']:
                    hist_str = get_node_path_str(full_df, row['collection_id'], current_dt)
                    hover_text = f"<b>ID:</b> {row['collection_id']}<br><b>Role:</b> {role}<br><b>History:</b> {hist_str}<br><b>Size:</b> {row['collection_size']}<br><b>Type:</b> {row['consistency']}"
                else:
                    hover_text = f"<b>ID:</b> {row['collection_id']}<br><b>Role:</b> {role}<br><b>Size:</b> {row['collection_size']}<br><b>Type:</b> {row['consistency']}"
                
                item_hover.append(hover_text)

    # Add Item Trace
    if item_x:
        fig.add_trace(go.Scatter(
            x=item_x, y=item_y, mode='markers',
            marker=dict(size=item_s, color=item_c, line=dict(width=1, color='white'), opacity=0.9),
            customdata=item_custom, hovertemplate="%{hovertext}<extra></extra>", hovertext=item_hover, name='Collections'
        ))

    # Add Cluster Trace
    if clust_x:
        fig.add_trace(go.Scatter(
            x=clust_x, y=clust_y, mode='markers', # No text mode
            marker=dict(size=clust_s, color='#F5A927', line=dict(width=1, color='white')),
            customdata=clust_custom,
            hoverinfo='text', hovertext=clust_hover, name='Clusters'
        ))

    # Layout
    fig.update_layout(
        title=dict(text=f"State at {current_time_label}", x=0.5, xanchor='center'),
        showlegend=False, plot_bgcolor='white',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-3.5, 3.5]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.5, 2.5]),
        margin=dict(l=10, r=10, t=40, b=10), dragmode='pan', height=600
    )
    return fig, active_leaders, active_replicas

def main():
    st.title("Ermes Infrastructure Visualization")

    with st.spinner('Loading and processing logs...'):
        df = load_data()

    if df.empty:
        st.error(f"No data found in `{LOG_PATTERN}`. Please check your file path.")
        return

    # --- STATE MANAGEMENT ---
    if 'tracked_collections_widget' not in st.session_state:
        st.session_state.tracked_collections_widget = []
    
    if 'cluster_view_ids' not in st.session_state:
        st.session_state.cluster_view_ids = None

    if 'cluster_view_node' not in st.session_state:
        st.session_state.cluster_view_node = None

    # Check if a click from the graph requested a selection update
    if 'pending_selection' in st.session_state:
        st.session_state.tracked_collections_widget = st.session_state.pending_selection
        del st.session_state.pending_selection

    # --- GRAPH TOPOLOGY ---
    all_nodes = df['node_id'].unique()
    G = nx.Graph()
    G.add_nodes_from(all_nodes)

    hierarchy_pos = {
        "10.10.101.57": np.array([0, 2]), "10.10.101.55": np.array([-2, 1]),
        "10.10.101.56": np.array([2, 1]), "10.10.101.50": np.array([-3, 0]),
        "10.10.101.51": np.array([-1, 0]), "10.10.101.52": np.array([1, 0]),
        "10.10.101.53": np.array([2, 0]), "10.10.101.54": np.array([3, 0]),
    }
    hierarchy_edges = [
        ("10.10.101.57", "10.10.101.55"), ("10.10.101.57", "10.10.101.56"),
        ("10.10.101.55", "10.10.101.50"), ("10.10.101.55", "10.10.101.51"),
        ("10.10.101.56", "10.10.101.52"), ("10.10.101.56", "10.10.101.53"),
        ("10.10.101.56", "10.10.101.54")
    ]
    pos = {n: hierarchy_pos[n] for n in all_nodes if n in hierarchy_pos}
    G.add_edges_from([(u, v) for u, v in hierarchy_edges if u in all_nodes and v in all_nodes])
    
    unknown = [n for n in all_nodes if n not in pos]
    for i, n in enumerate(unknown): pos[n] = np.array([i, -1]) 

    # --- CONTROLS ---
    st.sidebar.header("Controls")
    unique_collections = sorted(df['collection_id'].unique())
    
    selected_collections = st.sidebar.multiselect(
        "Filter / Inspect Collections", unique_collections, key="tracked_collections_widget"
    )

    # Timeline
    min_time = df['timestamp'].min()
    max_time = df['timestamp'].max()
    timeline = pd.date_range(start=min_time, end=max_time, freq='1s')
    time_labels = [t.strftime('%H:%M:%S') for t in timeline]
    
    col_play, col_slider = st.columns([1, 5])
    with col_play:
        st.write("")
        play_clicked = st.button("▶️ Play")
    with col_slider:
        selected_time_label = st.select_slider("Timeline", options=time_labels)
    
    current_time_idx = time_labels.index(selected_time_label)
    current_time = timeline[current_time_idx]

    # --- SIDEBAR CLUSTER DETAILS (Shown only when selected) ---
    if st.session_state.cluster_view_ids:
        st.sidebar.divider()
        st.sidebar.info("📂 **Cluster Details**")
        
        # Filter relevant records efficiently
        relevant_records = df[
            (df['collection_id'].isin(st.session_state.cluster_view_ids)) & 
            (df['timestamp'] <= current_time)
        ].copy()
        
        # KEY FIX: Filter specifically for the NODE we clicked
        if st.session_state.cluster_view_node:
            relevant_records = relevant_records[relevant_records['node_id'] == st.session_state.cluster_view_node]

        # Get latest per collection_id
        relevant_records = relevant_records.sort_values('timestamp', ascending=False)
        latest_states = relevant_records.drop_duplicates(subset=['collection_id'])
        
        # Apply TTL check
        valid_states = latest_states[
            (current_time - latest_states['timestamp']).dt.total_seconds() <= DATA_TTL_SECONDS
        ]
        
        if not valid_states.empty:
            st.sidebar.write(f"Showing **{len(valid_states)}** active items in cluster:")
            
            # Show the common node once
            common_node = valid_states['node_id'].iloc[0]
            st.sidebar.markdown(f"**Located on Node:** `{common_node}`")

            # Format for display
            display_df = valid_states[['collection_id', 'node_id', 'is_leader', 'collection_size', 'consistency']].copy()
            display_df['Role'] = display_df['is_leader'].apply(lambda x: '🔴 Leader' if x else '🔵 Follower')
            
            # --- CALCULATE HISTORY FOR SIDEBAR ---
            # We calculate this only for the active items to avoid performance hit on the whole DF
            # Only for leaders, else show placeholder
            display_df['History'] = display_df.apply(
                lambda r: get_node_path_str(df, r['collection_id'], current_time) if r['is_leader'] else "-", axis=1
            )
            
            display_df = display_df.rename(columns={
                'collection_id': 'ID',
                'collection_size': 'Size',
                'consistency': 'Type'
            })
            # Removed 'Node' from columns
            st.sidebar.dataframe(
                display_df[['ID', 'Role', 'History', 'Size', 'Type']], 
                hide_index=True,
                column_config={
                    "ID": st.column_config.TextColumn("ID", width="small"),
                    "Role": st.column_config.TextColumn("Role", width="small"),
                    "History": st.column_config.TextColumn("History", width="medium"),
                }
            )
        else:
            st.sidebar.warning("No active data for these IDs at this time.")

        if st.sidebar.button("Clear Cluster View"):
            st.session_state.cluster_view_ids = None
            st.session_state.cluster_view_node = None
            st.rerun()

    # --- VIEWPORT ---
    col_graph, col_info = st.columns([3, 1])
    
    with col_info:
        stats_placeholder = st.empty()
        with stats_placeholder.container():
             st.markdown("### Global Stats")
             st.markdown("Waiting for frame...")

    with col_graph:
        graph_placeholder = st.empty()

    # --- RENDER LOGIC ---
    if play_clicked:
        # ANIMATION MODE (MATPLOTLIB)
        start_idx = 0 
        
        for i in range(start_idx, len(time_labels)):
            t_val = timeline[i]
            l_val = time_labels[i]
            
            step_df = get_snapshot_at_time(df, t_val, all_nodes, DATA_TTL_SECONDS)
            
            fig, leaders, replicas = create_matplotlib_figure(
                G, pos, step_df, selected_collections, l_val, all_nodes
            )
            
            buf = io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches='tight')
            buf.seek(0)
            graph_placeholder.image(buf, width='stretch')
            plt.close(fig)

            with stats_placeholder.container():
                st.markdown("### Global Stats")
                st.markdown(f"**Time:** {l_val}")
                st.markdown(f"**Leaders:** {leaders}")
                st.markdown(f"**Replicas:** {replicas}")
                st.markdown("---")
                st.markdown("**Legend**")
                st.markdown("🔴 Leader | 🔵 Follower")
                st.markdown(f"🟡 Cluster ({CLUSTER_SIZE} items)")
            
            time.sleep(0.1)

    else:
        # INTERACTIVE MODE (PLOTLY)
        step_df = get_snapshot_at_time(df, current_time, all_nodes, DATA_TTL_SECONDS)
        
        # Pass full df and current_time for history calculation
        fig, leaders, replicas = create_plotly_figure(
            G, pos, step_df, selected_collections, selected_time_label, all_nodes, df, current_time
        )
        
        with graph_placeholder:
            event = st.plotly_chart(
                fig, width='stretch', 
                on_select="rerun", selection_mode="points", key="main_chart"
            )

        with stats_placeholder.container():
            st.markdown("### Global Stats")
            st.markdown(f"**Time:** {selected_time_label}")
            st.markdown(f"**Leaders:** {leaders}")
            st.markdown(f"**Replicas:** {replicas}")
            st.markdown("---")
            st.markdown("**Legend**")
            st.markdown("🔴 Leader | 🔵 Follower")
            st.markdown(f"🟡 Cluster ({CLUSTER_SIZE} items)")
            st.info("Hover to see details. Click to filter.")

        # --- EVENT HANDLING ---
        if event and event.selection and event.selection.points:
            clicked_point = event.selection.points[0]
            if "customdata" in clicked_point:
                data = clicked_point["customdata"]
                
                # Check if it is a CLUSTER or a SINGLE ITEM
                if isinstance(data, str) and data.startswith("CLUSTER|"):
                    # Handle Cluster Click: Show IDs
                    # Format: CLUSTER|node_id|id1,id2...
                    parts = data.split("|")
                    if len(parts) >= 3:
                        clicked_node = parts[1]
                        ids_str = parts[2]
                        id_list = ids_str.split(",")
                        
                        if st.session_state.cluster_view_ids != id_list or st.session_state.cluster_view_node != clicked_node:
                            st.session_state.cluster_view_ids = id_list
                            st.session_state.cluster_view_node = clicked_node
                            st.rerun()
                        
                else:
                    # Handle Item Click: Filter
                    clicked_id = data
                    current_selection = st.session_state.tracked_collections_widget
                    if clicked_id not in current_selection:
                        st.session_state.pending_selection = [clicked_id]
                        st.rerun()

    # --- HISTORY PANEL ---
    if selected_collections:
        st.divider()
        st.subheader("🔍 Selected Collection History")
        cols = st.columns(len(selected_collections))
        for idx, cid in enumerate(selected_collections):
            with cols[idx]:
                st.markdown(f"#### ID: `{cid}`")
                history_df = get_collection_history(df, cid)
                if not history_df.empty:
                    latest = history_df.iloc[-1]
                    st.markdown(f"**Current Node:** `{latest['node_id']}`")
                    st.markdown(f"**Type:** {latest['consistency']}")
                    display_hist = history_df.copy()
                    display_hist['Time'] = display_hist['timestamp'].dt.strftime('%H:%M:%S')
                    display_hist['Role'] = display_hist['is_leader'].apply(lambda x: '🔴 Leader' if x else '🔵 Follower')
                    st.dataframe(display_hist[['Time', 'node_id', 'Role']], hide_index=True, width='stretch', height=200)
                else:
                    st.warning("No history found.")

if __name__ == "__main__":
    main()