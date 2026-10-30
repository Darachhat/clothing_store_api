from app.core.config import settings
from app.main import app, lifespan

__all__ = ["app", "lifespan"]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app"
        , host   = "0.0.0.0"
        , port   = settings.PORT
        , reload = (settings.ENV == "development")
    )

