import os
import asyncio
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from scraper import ejecutar_scrapping_antecedentes

app = FastAPI(title="API Consulta Antecedentes Procuraduría", version="1.0.0")

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

class SolicitudConsulta(BaseModel):
    tipo_documento: str
    numero_documento: str
    primer_nombre: Optional[str] = ""

@app.post("/consultar-antecedentes")
async def consultar_antecedentes(solicitud: SolicitudConsulta):
    try:
        res = await asyncio.wait_for(
            ejecutar_scrapping_antecedentes(solicitud.tipo_documento, solicitud.numero_documento, solicitud.primer_nombre or ""),
            timeout=60.0
        )
        if res.get("requiere_primer_nombre"):
            return {"error": True, "requiere_primer_nombre": True, "tipo_documento": solicitud.tipo_documento, "numero_documento": solicitud.numero_documento, "mensaje": res["mensaje"]}
        
        if not res.get("nombre"):
            return {"error": True, "tipo_documento": solicitud.tipo_documento, "numero_documento": solicitud.numero_documento, "mensaje": "No fue posible completar la consulta. La verificación de seguridad no pudo ser resuelta. Intente nuevamente."}

        return {"tipo_documento": solicitud.tipo_documento, "numero_documento": solicitud.numero_documento, "nombre": res["nombre"], "tiene_antecedentes": res["tiene_antecedentes"], "mensaje": res["mensaje"]}
    except asyncio.TimeoutError:
        return {"error": True, "mensaje": "La consulta tardó demasiado (más de 60 segundos)."}
    except Exception as err:
        return {"error": True, "mensaje": "Ocurrió un error inesperado al procesar la consulta.", "detalle": str(err)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=False, ws="none")
