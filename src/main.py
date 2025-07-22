from dotenv import load_dotenv
from starlette.applications import Starlette

from src.lifespan import lifespan
from src.routes import routes

load_dotenv()


app = Starlette(
    debug=True,
    routes=routes,
    lifespan=lifespan,
)
