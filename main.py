import os
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
from pydantic import BaseModel
from scraper import ejecutar_scrapping_antecedentes

# Inicializamos la aplicación de FastAPI
app = FastAPI(
    title="API Consulta Antecedentes Procuraduría",
    description="API para consultar antecedentes mediante automatización con Pyppeteer y visión con Groq IA.",
    version="1.0.0"
)

# Montar la carpeta static para servir el frontend HTML/CSS/JS
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """
    Ruta raíz que sirve la interfaz web de usuario.
    """
    return FileResponse("static/index.html")

# Definición del esquema del cuerpo de la petición (solicitud JSON esperada)
class SolicitudConsulta(BaseModel):
    tipo_documento: str
    numero_documento: str
    primer_nombre: Optional[str] = ""

@app.post("/consultar-antecedentes")
async def consultar_antecedentes(solicitud: SolicitudConsulta):
    """
    Endpoint principal HTTP POST para la consulta de antecedentes.
    Recibe tipo_documento, numero_documento y primer_nombre (opcional) en formato JSON.
    """
    try:
        resultado_scraper = await asyncio.wait_for(
            ejecutar_scrapping_antecedentes(
                tipo_documento=solicitud.tipo_documento,
                numero_documento=solicitud.numero_documento,
                primer_nombre=solicitud.primer_nombre or ""
            ),
            timeout=60.0
        )

        if resultado_scraper.get("requiere_primer_nombre"):
            return {
                "error": True,
                "requiere_primer_nombre": True,
                "tipo_documento": solicitud.tipo_documento,
                "numero_documento": solicitud.numero_documento,
                "mensaje": resultado_scraper["mensaje"]
            }

        nombre = resultado_scraper.get("nombre", "")

        if not nombre:
            return {
                "error": True,
                "tipo_documento": solicitud.tipo_documento,
                "numero_documento": solicitud.numero_documento,
                "mensaje": "No fue posible completar la consulta. La verificación de seguridad no pudo ser resuelta. Intente nuevamente."
            }

        return {
            "tipo_documento": solicitud.tipo_documento,
            "numero_documento": solicitud.numero_documento,
            "nombre": nombre,
            "tiene_antecedentes": resultado_scraper["tiene_antecedentes"],
            "mensaje": resultado_scraper["mensaje"]
        }

    except asyncio.TimeoutError:
        return {
            "error": True,
            "mensaje": "La consulta tardó demasiado (más de 60 segundos)."
        }
    except Exception as error:
        return {
            "error": True,
            "mensaje": "No fue posible realizar la consulta.",
            "detalle": str(error)
        }

# Punto de entrada si se ejecuta directamente con Python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=False, ws="none")
