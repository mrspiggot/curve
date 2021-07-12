import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
from app import app
from dash.dependencies import Input, Output
import datetime
import pandas as pd
import QuantLib as ql
import plotly.express as px
from modules.curve import Curve
import plotly.graph_objects as go
from plotly.subplots import make_subplots

WIDTH = "14%"

currency = dcc.Dropdown(
    id="currency-dd",
    options=[
        {'label': 'USD', 'value': 'USD'},
        {'label': 'EUR', 'value': 'EUR'},
        {'label': 'GBP', 'value': 'GBP'}
    ],
    placeholder="Select Currency",
    value = "USD"
)
type = dcc.Dropdown(
    id="type-dd",
    options=[
        {'label': 'Discount (OIS)', 'value': 'OIS'},
        {'label': 'Forecast (IBOR)', 'value': 'LIBOR'},

    ],
    placeholder="Select Type",
    value='LIBOR'
)
tenor = dcc.Dropdown(
    id="tenor-dd",
    options=[
        {'label': 'Overnight', 'value': 'O/N'},
        {'label': 'One Month', 'value': '1M'},
        {'label': 'Three Month', 'value': '3M'},
        {'label': 'Six Month', 'value': '6M'},
    ],
    placeholder="Select Tenor",
    value='3M'
)
calendar = dcc.Dropdown(
    id="calendar-dd",
    options=[
        {'label': 'TARGET', 'value': 'TARGET'},
        {'label': 'US Libor Impact', 'value': 'US Libor Impact'},
        {'label': 'US Fed', 'value': 'US Fed'},
        {'label': 'US Govt Bond', 'value': 'US Govt Bond'},
        {'label': 'US Settlement', 'value': 'US Settlement'},
        {'label': 'Frankfurt Settlement', 'value': 'Frankfurt Settlement'},
        {'label': 'Eurex', 'value': 'Eurex'},
        {'label': 'UK Exchange', 'value': 'UK Exchange'},
        {'label': 'UK settlement Month', 'value': 'UK Settlement'},
    ],
    placeholder="Select Calendar(s)",
    multi=True,
    value='US Libor Impact'
)
display = dcc.Dropdown(
    id="display-dd",
    options=[
        {'label': 'Zeros', 'value': 'Zeros'},
        {'label': 'Spots', 'value': 'Spots'},
        {'label': 'Forwards', 'value': 'Forwards'},
        {'label': 'DFs', 'value': 'DF'},
    ],
    placeholder="Select Tenor",
    multi=True,
    value=['Zeros', 'DF']
)

build = dbc.Button("Build Curve", color="success", className="mr-1", id="build-btn")

layout = html.Div([
    dbc.Row([
        html.H6("Currency:", style={"width": WIDTH}),
        html.H6("Curve Type:", style={"width": WIDTH}),
        html.H6("Tenor:", style={"width": WIDTH}),
        html.H6("Holiday calendar(s):", style={"width": WIDTH}),
        html.H6("Display:", style={"width": WIDTH}),
    ]),
    dbc.Row([
        html.Div(currency, style={"width": WIDTH}),
        html.Div(type, style={"width": WIDTH}),
        html.Div(tenor, style={"width": WIDTH}),
        html.Div(calendar, style={"width": WIDTH}),
        html.Div(display, style={"width": WIDTH}),
        html.Div(html.P(""), style={"width": "5%"}),
        html.Div(build, style={"width": WIDTH}),
        ]
    ),
    dcc.Loading(
        dcc.Graph(id='curve'), fullscreen=True, type='graph'
    ),
])

@app.callback(Output('curve', 'figure'),
              [Input('build-btn', 'n_clicks'),
               Input('currency-dd', 'value'),
               Input('type-dd', 'value'),
               Input('tenor-dd', 'value'),
               Input('calendar-dd', 'value'),
               ])
def display_curve(click, currency, type, tenor, holidays):
    print('clicks =', click)
    crv = Curve(currency, type, tenor)
    df = crv.build_spot_curve()
    print(df)
    print(df.info())

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Add traces
    fig.add_trace(
        go.Scatter(x=df['Date'].tolist(), y=df['Zero'].tolist(), line={'shape': 'spline', 'smoothing': 1.3}, name="Zeros"),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(x=df['Date'].tolist(),  y=df['Discount Factor'].tolist(), line={'shape': 'spline', 'smoothing': 1.3}, name="Discount Factors"),
        secondary_y=True,
    )
    title_text = crv.currency + " " + crv.type + " " + crv.tenor + " Curve"
    fig.update_layout(
        title_text=title_text
    )
    fig.update_yaxes(
        title_text="<b>primary</b> Zeros and Forwards (%)",
        secondary_y=False)
    fig.update_yaxes(
        title_text="<b>secondary</b> Discount Factors",
        secondary_y=True)


    return fig