from flask import Flask, render_template
import pandas as pd
import sqlite3
import plotly.graph_objects as go
import plotly.io as pio
from dash import Dash, dash_table, html

app = Flask(__name__)

def get_data():
    conn = sqlite3.connect('wifi_scans.db')
    df_scans = pd.read_sql_query("SELECT * FROM scans", conn)
    df_oscans = pd.read_sql_query("SELECT * FROM open_scans", conn)
    conn.close()
    return df_scans, df_oscans

@app.route('/')
def index():
    df_scans, df_oscans = get_data()
    # Filtrar redes únicas
    """df_unique_scans = df_scans.drop_duplicates(subset=['ssid', 'auth', 'encrypt', 'strength'])
    df_unique_oscans = df_oscans.drop_duplicates(subset=['ssid', 'auth', 'encrypt', 'strength'])"""
    
    # Verificar se 'area' é numérica e converter para int, ou ordenar semanticamente
    df_scans['area_numeric'] = pd.to_numeric(df_scans['area'], errors='coerce')
    df_oscans['area_numeric'] = pd.to_numeric(df_oscans['area'], errors='coerce')
    
    # Separar e ordenar valores numéricos e não numéricos
    numeric_areas = sorted(df_scans[df_scans['area_numeric'].notnull()]['area_numeric'].unique())
    string_areas = sorted(df_scans[df_scans['area_numeric'].isnull()]['area'].unique())
    sorted_areas = numeric_areas + string_areas

    # Gerar gráfico de linha com Plotly
    #redes fechadas
    fig = go.Figure()
    for ssid in df_scans['ssid'].unique():
        df_ssid = df_scans[df_scans['ssid'] == ssid]
        fig.add_trace(go.Scatter(x=df_ssid['area'], y=df_ssid['strength'], mode='lines+markers', name=ssid))

    fig.update_layout(title='Força do Sinal por SSID', 
                      xaxis_title='area', 
                      yaxis_title='Força do Sinal (%)', 
                      xaxis=dict(categoryorder='array',
                      categoryarray=sorted_areas))

    graph_html = pio.to_html(fig, full_html=False)
    
    
    #redes abertas
    fig = go.Figure()
    for ossid in df_oscans['ssid'].unique():
        df_ossid = df_oscans[df_oscans['ssid'] == ossid]
        fig.add_trace(go.Scatter(x=df_ossid['area'], y=df_ossid['strength'], mode='lines+markers', name=ossid))

    fig.update_layout(title='Força do Sinal por SSID', 
                      xaxis_title='area', 
                      yaxis_title='Força do Sinal (%)', 
                      xaxis=dict(categoryorder='array',
                      categoryarray=sorted_areas))
    
    
    grapho_html = pio.to_html(fig, full_html=False)

    return render_template('index.html', graph_html=graph_html, grapho_html=grapho_html)

# Configuração do Dash
dash_app = Dash(__name__, server=app, url_base_pathname='/dash/')
df_scans, df_oscans = get_data()
#df_unique_scans = df_scans.drop_duplicates(subset=['ssid', 'auth', 'encrypt', 'strength'])

dash_app.layout = html.Div([
    dash_table.DataTable(
        id='table',
        columns=[{"name": i, "id": i, "presentation": "dropdown"} for i in df_scans.columns],
        data=df_scans.to_dict('records'),
        editable=False,
        filter_action="native",
        sort_action="native",
        sort_mode="multi",
        page_action="native",
        page_current=0,
        page_size=100,
        export_format='csv',
        dropdown={
            col: {
                "options": [{"label": str(i), "value": str(i)} for i in df_scans[col].unique()]
            } for col in df_scans.columns
        },
        style_table={'overflowX': 'auto'},
        style_cell={
            'height': 'auto',
            'minWidth': '100px', 'width': '100px', 'maxWidth': '100px',
            'whiteSpace': 'normal'
        },
        style_header={
            'backgroundColor': 'rgb(230, 230, 230)',
            'fontWeight': 'bold'
        },
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(248, 248, 248)'
            }
        ]
    )
])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)