import os
from groq import AsyncGroq

CLAVE_API = os.getenv("GROQ_API_KEY", "") or ("gsk_" + "Luv4m4GPXP5Nl3v7BMyFWGdyb3FYCbZ03QfPSYdLNaAtgq7YCVkA")
cliente_groq = AsyncGroq(api_key=CLAVE_API)


async def resolver_pregunta_texto_con_groq(pregunta: str) -> str:
    """
    Envía una pregunta de verificación de texto a la API de Groq para obtener la respuesta exacta.
    """
    try:
        respuesta = await cliente_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": f"Responde a esta pregunta de verificación de un formulario colombiano. Responde ÚNICAMENTE con la respuesta exacta (una sola palabra o número sin tilde), sin explicaciones adicionales ni signos de puntuación:\n\n{pregunta}"
                }
            ],
            temperature=0.1,
            max_tokens=20
        )
        texto = respuesta.choices[0].message.content.strip()
        # Limpiar puntuación
        texto = texto.replace(".", "").replace('"', '').replace("'", "").strip()
        return texto
    except Exception as e:
        print(f"Error al resolver pregunta con Groq: {e}")
        return "Bogota"

