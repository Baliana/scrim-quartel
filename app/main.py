from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import auth, usuarios, categorias, materiais, emprestimos

app = FastAPI(
    title="Sistema de Controle de Materiais",
    description="API para cadastro de materiais, controle de empréstimos/devoluções "
                "de itens e notificações via WhatsApp (Twilio).",
    version="1.0.0",
)

# ---------------------------------------------------------------------
# CORS — permite o frontend (HTML/CSS/JS puro) consumir a API
# ---------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------
# Tratamento de erros de validação em português
# ---------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Dados inválidos", "erros": exc.errors()},
    )


# ---------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(categorias.router)
app.include_router(materiais.router)
app.include_router(emprestimos.router)


@app.get("/", tags=["Status"])
def raiz():
    return {"status": "ok", "servico": "API Sistema de Controle de Materiais"}


@app.get("/health", tags=["Status"])
def health_check():
    return {"status": "healthy"}
