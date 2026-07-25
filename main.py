from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Zentrale Dienste und Module importieren (Nur das, was wirklich als Service existiert)
from database import database_service
from mail_services import mail_service
from modules import ki_aktiv_fuer_sektor, hole_seele
from ws_manager import manager
import utils

# Alle Router und deren Konfigurationsfunktionen importieren
from admin_routes import router as admin_router, set_admin_router_config
from auth_routes import router as auth_router, set_auth_router_config
from routesvideo_live import router as video_router, set_video_router_config
from routes_forum import router as forum_router, set_forum_router_config
from routesapi_misc import router as misc_router, set_misc_router_config

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def create_app() -> FastAPI:
    app = FastAPI(
        title="M&M Community",
        version="1.0.0",
        description="Vollständig verdrahtete API inklusive Live-Video und Standard-Video.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    # Sichere Datenbankverbindung holen
    def _get_db():
        try:
            return database_service.get_db()
        except Exception:
            return None

    db = _get_db()

    # Konfigurationen an die Router übergeben
    set_auth_router_config(
        database=db,
        ws_manager=manager,
        module_service_instance=None,
        utils_module=utils,
        mail_service=mail_service,
    )

    set_video_router_config(
        database=db,
        ws_manager=manager,
        module_service_instance=None,
        utils_module=utils,
    )

    set_admin_router_config(
        database=db,
        ws_manager=manager,
        module_service_instance=None,
        utils_module=utils,
    )

    set_forum_router_config(
        database=db,
        ws_manager=manager,
        module_service_instance=None,
        utils_module=utils,
    )

    set_misc_router_config(
        database=db,
        ws_manager=manager,
        module_service_instance=None,
    )

    # Alle Router offiziell an den Hauptschalter anstecken
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(video_router)
    app.include_router(forum_router)
    app.include_router(misc_router)

    # Startseite
    @app.get("/")
    async def home(request: Request):
        return templates.TemplateResponse(request, "index.html", {"request": request})

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=10000, reload=False)