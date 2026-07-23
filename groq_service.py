import os
import base64
from groq import AsyncGroq

CLAVE_API = os.getenv("GROQ_API_KEY", "")
cliente_groq = AsyncGroq(api_key=CLAVE_API) if CLAVE_API else None

async def resolver_captcha_con_groq(bytes_imagen: bytes) -> str:
    """
    Función que envía una imagen codificada en Base64 a la API de Groq
    para analizar y resolver el desafío del captcha.
    
    Parámetros:
        bytes_imagen (bytes): La captura de pantalla en formato de imagen/bytes.
        
    Retorna:
        str: La respuesta o texto deducido por el modelo de visión.
    """
    # 1. Convertir los bytes de la imagen a una cadena en Base64
    imagen_base64 = base64.b64encode(bytes_imagen).decode('utf-8')
    url_data_imagen = f"data:image/png;base64,{imagen_base64}"

    # 2. Construir la consulta a la API de Groq utilizando un modelo de visión
    respuesta = await cliente_groq.chat.completions.create(
        model="llama-3.2-11b-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Resuelve la pregunta o desafío visual presentado en este captcha. Responde ÚNICAMENTE con el resultado exacto (número o palabra corta), sin explicaciones adicionales ni signos de puntuación."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": url_data_imagen
                        }
                    }
                ]
            }
        ],
        temperature=0.1,
        max_tokens=20
    )

    # 3. Extraer y limpiar el resultado devuelto por el modelo
    texto_respuesta = respuesta.choices[0].message.content.strip()
    return texto_respuesta

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

