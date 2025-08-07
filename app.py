import pandas as pd
import dash
from dash import dcc, html, Input, Output
import plotly.express as px
import plotly.graph_objects as go
from dash import dash_table


 # Get the current directory of the running script
current_dir = os.path.dirname(os.path.abspath(__file__))

    
    # Build the relative path to the CSV file
file_path = os.path.join(current_dir, "'SA20_Auction.csv'")
    

# Load and preprocess data
df = pd.read_csv(file_path)
# Clean data
df = df[df['Full Name'].notna()]  # Remove empty rows
df = df[df['Winner'] != 'Unsold']  # Focus on sold players

# Convert bid amounts to numeric
teams = ['MI CT', 'PR', 'JSK', 'PC', 'DSG', 'SEC']
for team in teams:
    df[team] = df[team].str.replace(',', '').str.replace('"', '').astype(float)

# Melt data for visualization
melted_df = pd.melt(df, id_vars=['Full Name', 'Set', 'Role', 'Country', 'Winner'], 
                    value_vars=teams, var_name='Bidding Team', value_name='Bid Amount')

team_purses = {'MI CT': 17000, 'JSK': 20740, 'PC': 28050, 'PR': 20740, 'DSG': 17000, 'SEC': 28050}

# --- New Composite Score Calculations ---

# Identify the highest bid in the entire auction
highest_auction_bid = df[teams].max().max()

# Identify the highest bid for each role
highest_role_bid = melted_df.groupby('Role')['Bid Amount'].max().reset_index()
highest_role_bid.rename(columns={'Bid Amount': 'Highest Role Bid'}, inplace=True)
melted_df = pd.merge(melted_df, highest_role_bid, on='Role', how='left')

# Calculate the new, more granular scores for each bid
melted_df['Bid Strength Score'] = (melted_df['Bid Amount'] / melted_df['Bidding Team'].map(team_purses)) * 100
melted_df['Relative Value Score'] = (melted_df['Bid Amount'] / highest_auction_bid) * 100
melted_df['Role Priority Score'] = (melted_df['Bid Amount'] / melted_df['Highest Role Bid']) * 100

# Define weights for the composite score (you can adjust these)
alpha = 0.3 # Weight for Bid Strength
beta = 0.4  # Weight for Relative Value
gamma = 0.3 # Weight for Role Priority

# Calculate the final Composite Score
melted_df['Composite Score'] = (alpha * melted_df['Bid Strength Score'] +
                                 beta * melted_df['Relative Value Score'] +
                                 gamma * melted_df['Role Priority Score'])

# Filter for the players who were actually sold to a team (to show the final composite score)
sold_players_df = melted_df[melted_df['Winner'] == melted_df['Bidding Team']]
sold_players_df = sold_players_df[['Full Name', 'Winner', 'Role', 'Country', 'Bid Amount', 'Composite Score']].sort_values(by='Composite Score', ascending=False)

# Remove rows with no bid amount
melted_df = melted_df[melted_df['Bid Amount'].notna()]

# Calculate metrics
team_purses = {'MI CT': 17000, 'JSK': 20740, 'PC': 28050, 'PR': 20740, 'DSG': 17000, 'SEC': 28050}
total_spent = melted_df.groupby('Bidding Team')['Bid Amount'].sum().reset_index()
total_spent['Purse Remaining'] = total_spent['Bidding Team'].map(team_purses) - total_spent['Bid Amount']

# Create Dash app
app = dash.Dash(__name__)

server = app.server

app.layout = html.Div([
    html.H1("SA T20 Auction Valuation Dashboard", style={'textAlign': 'center'}),
    
    html.Div([
        html.Div([
            dcc.Dropdown(
                id='team-selector',
                options=[{'label': team, 'value': team} for team in teams],
                value=['MI CT', 'PC'],
                multi=True
            ),
            dcc.Dropdown(
                id='set-selector',
                options=[{'label': s, 'value': s} for s in melted_df['Set'].unique()],
                value=melted_df['Set'].unique()[0],
                clearable=False
            ),
            dcc.Graph(id='team-spending')
        ], style={'width': '48%', 'display': 'inline-block'}),
        
        html.Div([
            dcc.Dropdown(
                id='role-selector',
                options=[{'label': role, 'value': role} for role in df['Role'].unique()],
                value='Batsman'
            ),
            dcc.Graph(id='role-spending')
        ], style={'width': '48%', 'display': 'inline-block', 'float': 'right'})
    ]),
    
    html.Div([
        dcc.Graph(id='player-valuation-heatmap')
    ]),
    
    html.Div([
        dcc.Dropdown(
            id='metric-selector',
            options=[
                {'label': 'Total Bid Amount', 'value': 'sum'},
                {'label': 'Number of Players', 'value': 'count'},
                {'label': 'Average Bid', 'value': 'mean'}
            ],
            value='sum'
        ),
        dcc.Graph(id='team-role-analysis')
    ]),
    
    html.Div([
        dcc.Graph(id='purse-utilization')
    ]),
    
    html.Div([
        html.H2("Player Composite Score and Valuation Table", style={'textAlign': 'center', 'marginTop': '50px'}),
        dcc.Dropdown(
            id='composite-score-role-filter',
            options=[{'label': 'All Roles', 'value': 'All'}] + [{'label': role, 'value': role} for role in sorted(sold_players_df['Role'].unique())],
            value='All',
            clearable=False
        ),
        html.Div(id='composite-score-table-container')
    ]),
])

# Callbacks for interactivity
@app.callback(
    Output('team-spending', 'figure'),
    Input('team-selector', 'value'),
    Input('set-selector', 'value') #
)
def update_team_spending(selected_teams, selected_set):
    if not isinstance(selected_teams, list):
        selected_teams = [selected_teams]
    
    # --- New Filtering Logic ---
    filtered = melted_df[
        (melted_df['Bidding Team'].isin(selected_teams)) &
        (melted_df['Set'] == selected_set)
    ]
    
    # Sort the filtered data by bid amount to make it easier to read
    filtered = filtered.sort_values(by='Bid Amount', ascending=False)
    
    fig = px.bar(filtered, x='Full Name', y='Bid Amount', color='Bidding Team',
                  title=f'Team Bidding Patterns for {selected_set}', 
                  hover_data=['Role', 'Set'])
    fig.update_layout(barmode='group')
    return fig

@app.callback(
    Output('role-spending', 'figure'),
    Input('role-selector', 'value')
)
def update_role_spending(selected_role):
    role_df = melted_df[melted_df['Role'] == selected_role]
    fig = px.box(role_df, x='Bidding Team', y='Bid Amount', 
                 title=f'Bid Distribution for {selected_role}s',
                 color='Bidding Team')
    return fig

@app.callback(
    Output('player-valuation-heatmap', 'figure'),
    Input('team-selector', 'value')
)
def update_heatmap(selected_teams):
    if not isinstance(selected_teams, list):
        selected_teams = [selected_teams]
    
    heatmap_data = melted_df[melted_df['Bidding Team'].isin(selected_teams)]
    heatmap_data = heatmap_data.pivot_table(index='Full Name', columns='Bidding Team', 
                                          values='Bid Amount', aggfunc='sum')
    
    fig = px.imshow(heatmap_data, 
                   labels=dict(x="Team", y="Player", color="Bid Amount"),
                   title="Player Valuation Heatmap",
                   color_continuous_scale='Viridis')
    return fig

@app.callback(
    Output('team-role-analysis', 'figure'),
    Input('metric-selector', 'value')
)
def update_team_role_analysis(metric):
    if metric == 'count':
        analysis_df = melted_df.groupby(['Bidding Team', 'Role']).size().reset_index(name='Player Count')
        y_col = 'Player Count'
    else:
        analysis_df = melted_df.groupby(['Bidding Team', 'Role']).agg({'Bid Amount': metric}).reset_index()
        y_col = 'Bid Amount'
    
    fig = px.bar(analysis_df, x='Bidding Team', y=y_col, color='Role',
                title=f'Team Spending by Role ({metric})',
                barmode='group')
    return fig

@app.callback(
    Output('purse-utilization', 'figure'),
    Input('team-selector', 'value')
)
def update_purse_utilization(selected_teams):
    if not isinstance(selected_teams, list):
        selected_teams = [selected_teams]
    
    filtered = total_spent[total_spent['Bidding Team'].isin(selected_teams)]
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=filtered['Bidding Team'],
        y=filtered['Bid Amount'],
        name='Amount Spent',
        marker_color='indianred'
    ))
    
    fig.add_trace(go.Bar(
        x=filtered['Bidding Team'],
        y=filtered['Purse Remaining'],
        name='Purse Remaining',
        marker_color='lightsalmon'
    ))
    
    fig.update_layout(barmode='stack', title='Purse Utilization by Team')
    return fig
@app.callback(
    Output('composite-score-table-container', 'children'),
    Input('composite-score-role-filter', 'value')
)
def update_composite_score_table(selected_role):
    if selected_role == 'All':
        filtered_df = sold_players_df
    else:
        filtered_df = sold_players_df[sold_players_df['Role'] == selected_role]

    return dash_table.DataTable(
        id='table',
        columns=[{"name": i, "id": i} for i in filtered_df.columns],
        data=filtered_df.to_dict('records'),
        sort_action="native",
        filter_action="native",
        page_action="native",
        page_current=0,
        page_size=10,
        style_table={'overflowX': 'auto'},
        style_cell={
            'height': 'auto',
            'minWidth': '100px', 'width': '100px', 'maxWidth': '180px',
            'whiteSpace': 'normal'
        }
    )

if __name__ == '__main__':
    app.run(debug=True)
