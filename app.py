import dash
import dash_bootstrap_components as dbc
import sqlalchemy
import sshtunnel
#from decouple import config

# NAME = config('DB_NAME')
# USER = config('DB_USER')
# PASSWORD = config('DB_PASSWORD')
# HOST = config('DB_HOST')
# PORT = config('DB_PORT')
# SSH_USER = config('SSH_USER')
# SSH_PASSWORD = config('SSH_PASSWORD')
#
#
#
# sshtunnel.SSH_TIMEOUT = 5.0
# sshtunnel.TUNNEL_TIMEOUT = 5.0
# meta_tags are required for the app layout to be mobile responsive
app = dash.Dash(__name__, suppress_callback_exceptions=True,  external_stylesheets=[dbc.themes.BOOTSTRAP],
                meta_tags=[{'name': 'viewport',
                            'content': 'width=device-width, initial-scale=1.0'}]
                )
# cache = Cache(app.server, config={
#     'CACHE_TYPE': 'filesystem',
#     'CACHE_DIR': 'cache-directory'
# })
server = app.server
# with sshtunnel.SSHTunnelForwarder(
#         ('ssh.pythonanywhere.com'),
#         ssh_username=SSH_USER, ssh_password=SSH_PASSWORD,
#         remote_bind_address=(NAME, 12175)
# ) as tunnel:
#     engine = sqlalchemy.create_engine('postgresql://' + str(USER) + ':' + str(PASSWORD) + '@localhost:9999/tbic')