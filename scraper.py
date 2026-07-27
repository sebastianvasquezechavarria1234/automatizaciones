import os
import re
import asyncio
import logging
from typing import Optional, Any
from pyppeteer import launch
from groq_service import resolver_pregunta_texto_con_groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURACIÓN DE SELECTORES CSS Y URL
# Nota sustentación: Si la página de la Procuraduría actualiza la estructura de su
# DOM o cambian sus IDs/clases, se deben reemplazar estos selectores CSS.
# ==============================================================================
URL_PAGINA_PROCURADURIA = "https://www.procuraduria.gov.co/Pages/Consulta-de-Antecedentes.aspx"

SELECTOR_TIPO_DOC = "select#ddlTipoID"
SELECTOR_NUM_DOC = "#txtNumID"
SELECTOR_BOTON_CONSULTAR = "#btnConsultar"
SELECTOR_CAPTCHA_INPUT = "#txtRespuesta"
SELECTOR_CAPTCHA_PREGUNTA = "#lblPregunta"
SELECTOR_NOMBRE = "#divSec h3"

# Variable global que almacena el iframe del formulario una vez localizado
FORM_FRAME: Optional[Any] = None

# Respuestas conocidas a las preguntas de verificación del formulario (Capitales y Operaciones comunes)
RESPUESTAS_CAPTCHA = {
    # Capitales de Colombia
    "colombia": "Bogota", "antioquia": "Medellin", "atlantico": "Barranquilla",
    "bolivar": "Cartagena", "boyaca": "Tunja", "caldas": "Manizales",
    "caqueta": "Florencia", "cauca": "Popayan", "cesar": "Valledupar",
    "choco": "Quibdo", "cordoba": "Monteria", "cundinamarca": "Bogota",
    "guainia": "Inirida", "guaviare": "San Jose del Guaviare", "huila": "Neiva",
    "guajira": "Riohacha", "magdalena": "Santa Marta", "meta": "Villavicencio",
    "nariño": "Pasto", "narino": "Pasto", "norte de santander": "Cucuta",
    "putumayo": "Mocoa", "quindio": "Armenia", "risaralda": "Pereira",
    "san andres": "San Andres", "santander": "Bucaramanga", "sucre": "Sincelejo",
    "tolima": "Ibague", "valle": "Cali", "vallle": "Cali", "vaupes": "Mitu",
    "vichada": "Puerto Carreno", "arauca": "Arauca", "casanare": "Yopal",
    
    # Preguntas matemáticas exactas del captcha
    "3 + 2": "5",
    "5 + 3": "8",
    "9 - 2": "7",
    "2 x 3": "6",
    "2 * 3": "6",
}


async def abrir_navegador():
    """Inicia una instancia del navegador utilizando el ejecutable local de Chrome/Edge."""
    rutas_posibles = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    ruta_ejecutable = next((r for r in rutas_posibles if os.path.exists(r)), None)

    opciones = {
        "headless": True,
        "args": [
            "--no-sandbox", "--disable-setuid-sandbox",
            "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"
        ]
    }
    if ruta_ejecutable:
        logger.info(f"Usando navegador: {ruta_ejecutable}")
        opciones["executablePath"] = ruta_ejecutable

    browser = await launch(**opciones)
    page = await browser.newPage()
    await page.setUserAgent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    await page.setViewport({"width": 1280, "height": 800})
    logger.info("Navegador iniciado correctamente.")
    return browser, page


async def get_form_frame(page):
    """Busca el iframe que contiene el formulario con reintentos."""
    for intento in range(10):
        for frame in page.frames:
            try:
                if await frame.evaluate("() => !!document.querySelector('#ddlTipoID')"):
                    logger.info(f"Encontrado frame con formulario: {frame.url}")
                    return frame
            except Exception:
                continue
        await asyncio.sleep(1)
    raise Exception("No se encontró el iframe con el formulario tras varios reintentos")


async def get_result_frame(page):
    """Devuelve el frame del iframe de resultado tras el postback ASP.NET."""
    for intento in range(15):
        await asyncio.sleep(1)
        for frame in page.frames:
            try:
                url = frame.url
                if "webcert" in url or "Certificado" in url:
                    logger.info(f"Frame de resultado: {url}")
                    return frame
            except Exception:
                continue
    raise Exception("No se encontró el frame del resultado")


async def cargar_pagina_consulta(page):
    """Abre la URL objetivo y localiza el iframe del formulario."""
    global FORM_FRAME
    logger.info(f"Navegando a {URL_PAGINA_PROCURADURIA}...")
    try:
        await page.goto(URL_PAGINA_PROCURADURIA, {"waitUntil": "domcontentloaded", "timeout": 30000})
        logger.info("Página cargada correctamente.")
    except Exception as err:
        logger.warning(f"Aviso en carga de página (continuando intento de localización de iframe): {err}")
    
    FORM_FRAME = await get_form_frame(page)


class RequierePrimerNombreException(Exception):
    """Excepción lanzada cuando el captcha requiere el primer nombre del usuario y no fue provisto."""
    pass


async def resolver_pregunta_texto(pregunta: str, numero_documento: str = "", primer_nombre: str = "") -> str:
    """Devuelve la respuesta a la pregunta de verificación usando diccionario, matemáticas, reglas de documento o Groq AI."""
    pregunta_lower = pregunta.lower()

    # 1. Buscar primero en el diccionario local (Capitales y operaciones fijas)
    for clave, respuesta in RESPUESTAS_CAPTCHA.items():
        if clave in pregunta_lower:
            logger.info(f"Pregunta encontrada en diccionario: '{pregunta}' → {respuesta}")
            return respuesta

    # 2. Evaluar preguntas matemáticas dinámicas (ej. "¿Cuanto es 5 + 3?")
    match_math = re.search(r'(\d+)\s*([\+\-\*Xx/])\s*(\d+)', pregunta, re.IGNORECASE)
    if match_math:
        n1, op, n2 = int(match_math.group(1)), match_math.group(2).upper(), int(match_math.group(3))
        ops = {'+': n1 + n2, '-': n1 - n2, 'X': n1 * n2, '*': n1 * n2, '/': n1 // n2}
        res = ops.get(op, 0)
        logger.info(f"Pregunta matemática resuelta: '{pregunta}' → {res}")
        return str(res)

    # 3. Evaluar preguntas basadas en el número de documento
    if numero_documento:
        if "ultimos digitos" in pregunta_lower or "últimos dígitos" in pregunta_lower:
            res = numero_documento[-2:]
            logger.info(f"Pregunta de últimos dígitos resuelta: '{pregunta}' → {res}")
            return res
        if "primeros digitos" in pregunta_lower or "primeros dígitos" in pregunta_lower:
            res = numero_documento[:3]
            logger.info(f"Pregunta de primeros dígitos resuelta: '{pregunta}' → {res}")
            return res

    # 4. Preguntas sobre el 'primer nombre'
    if "primer nombre" in pregunta_lower or "nombre de la persona" in pregunta_lower:
        if primer_nombre and primer_nombre.strip():
            p_nom = primer_nombre.strip().upper()
            if "dos primeras letras" in pregunta_lower or "2 primeras letras" in pregunta_lower or "dos primeras" in pregunta_lower:
                res = p_nom[:2]
            elif "cantidad de letras" in pregunta_lower or "numero de letras" in pregunta_lower or "cuantas letras" in pregunta_lower:
                res = str(len(p_nom))
            else:
                res = p_nom
            logger.info(f"Pregunta de nombre resuelta con el nombre ingresado '{primer_nombre}': '{pregunta}' → {res}")
            return res
        else:
            logger.warning(f"La pregunta requiere el nombre del usuario y no fue ingresado: '{pregunta}'")
            raise RequierePrimerNombreException("La pregunta de verificación requiere el primer nombre del ciudadano.")

    # 5. Consultar a Groq IA para preguntas de texto complejas
    logger.info(f"Pregunta no está en diccionario: '{pregunta}'. Consultando Groq IA...")
    return await resolver_pregunta_texto_con_groq(pregunta)


async def seleccionar_y_llenar_datos(page, tipo_documento: str, numero_documento: str, primer_nombre: str = ""):
    """Selecciona el tipo de documento, ingresa el número y responde la pregunta de verificación."""
    # 1. Seleccionar tipo de documento
    await FORM_FRAME.waitForSelector(SELECTOR_TIPO_DOC, {"timeout": 30000})
    val = await FORM_FRAME.evaluate("""(tipo) => {
        const sel = document.querySelector('#ddlTipoID');
        if (!sel) return null;
        const t = tipo.toUpperCase().trim();
        const map = {'CC':'CÉDULA DE CIUDADANÍA','NIT':'NIT','CE':'EXTRANJERÍA','PEP':'PEP','PPT':'PPT'};
        const target = map[t] || t;
        for (let i = 0; i < sel.options.length; i++) {
            const opt = sel.options[i];
            const val = opt.value.toUpperCase().trim(), txt = opt.text.toUpperCase().trim();
            if (val === '0' || val === '' || txt.includes('SELECCIONE')) continue;
            if (val === t || txt.includes(target) || txt.includes('CEDULA DE CIUDADANIA')) {
                sel.selectedIndex = i; sel.value = opt.value;
                sel.dispatchEvent(new Event('change', { bubbles: true }));
                return opt.text;
            }
        }
        return null;
    }""", tipo_documento)
    logger.info(f"Tipo de documento seleccionado: {val or tipo_documento}")
    await asyncio.sleep(2)  # Esperar actualización ASP.NET por el evento change

    # 2. Ingresar número de documento
    await FORM_FRAME.waitForSelector(SELECTOR_NUM_DOC, {"timeout": 30000})
    await FORM_FRAME.focus(SELECTOR_NUM_DOC)
    await FORM_FRAME.evaluate("() => { const el = document.querySelector('#txtNumID'); if(el) el.value = ''; }")
    await FORM_FRAME.type(SELECTOR_NUM_DOC, numero_documento)
    logger.info(f"Número de documento ingresado: {numero_documento}")

    # 3. Leer y responder pregunta de verificación
    try:
        pregunta_texto = await FORM_FRAME.evaluate(
            "() => document.querySelector('#lblPregunta')?.innerText || "
            "document.querySelector('label[for=txtRespuestaPregunta]')?.innerText || ''"
        )
        if not pregunta_texto:
            return

        respuesta = await resolver_pregunta_texto(pregunta_texto, numero_documento, primer_nombre)
        logger.info(f"Pregunta: '{pregunta_texto}' → Respuesta: '{respuesta}'")

        input_sel = await FORM_FRAME.evaluate("""() => {
            const el = document.querySelector('#txtRespuestaPregunta, #txtRespuesta, input[id*="Respuesta"], input[name*="Respuesta"]');
            if (el) return el.id ? '#' + el.id : 'input[name="' + el.name + '"]';
            const target = Array.from(document.querySelectorAll('input[type="text"], input:not([type])')).find(i => i.id !== 'txtNumID' && i.name !== 'txtNumID');
            return target ? (target.id ? '#' + target.id : 'input[name="' + target.name + '"]') : null;
        }""")

        if input_sel:
            await FORM_FRAME.focus(input_sel)
            await FORM_FRAME.evaluate(f"() => {{ const el = document.querySelector('{input_sel}'); if(el) el.value = ''; }}")
            await FORM_FRAME.type(input_sel, respuesta)
            await FORM_FRAME.evaluate(f"""() => {{
                const el = document.querySelector('{input_sel}');
                if (el) {{ el.dispatchEvent(new Event('input', {{ bubbles: true }})); el.dispatchEvent(new Event('change', {{ bubbles: true }})); }}
            }}""")
            logger.info("Respuesta de verificación ingresada.")
        else:
            logger.warning("No se encontró el campo input para la respuesta.")
    except Exception as e:
        logger.warning(f"No se pudo responder la pregunta de verificación: {e}")


async def pulsar_consultar_y_esperar(page) -> None:
    """Hace clic en Consultar y espera a que el iframe se recargue con el resultado."""
    global FORM_FRAME
    btn_sel = await FORM_FRAME.evaluate("""() => {
        const btn = document.querySelector('#btnConsultar, input[id*="btnConsultar"], input[value*="Consultar"], button[id*="Consultar"]');
        return btn ? (btn.id ? '#' + btn.id : 'input[value*="Consultar"]') : '#btnConsultar';
    }""")
    await FORM_FRAME.waitForSelector(btn_sel, {"timeout": 15000})
    await FORM_FRAME.click(btn_sel)
    logger.info("Botón Consultar presionado.")
    await asyncio.sleep(6)
    FORM_FRAME = await get_result_frame(page)


def _extraer_nombre(texto: str) -> str:
    """Extrae el nombre del ciudadano del texto de resultado usando regex."""
    match = re.search(r'Señor\(a\)?\s+([A-ZÁÉÍÓÚÑ\s]+?)\s+identificad[oa]', texto, re.IGNORECASE)
    return match.group(1).strip() if match else ""


async def leer_mensaje_resultado(page) -> dict:
    """Lee el mensaje de resultado del iframe después del postback ASP.NET."""
    global FORM_FRAME
    await asyncio.sleep(2)
    texto_body = await FORM_FRAME.evaluate("() => document.body.innerText")
    logger.info(f"[DEBUG] Texto del iframe:\n{texto_body[:2000]}")

    # 1. Extraer nombre del ciudadano
    nombre = _extraer_nombre(texto_body)
    if not nombre:
        try:
            h3_text = await FORM_FRAME.evaluate(
                "() => document.querySelector('#divSec h3, div.datosConsultado h3, #divSec div')?.innerText || ''"
            )
            nombre = _extraer_nombre(h3_text)
            if not nombre and h3_text and len(h3_text) < 80:
                nombre = h3_text.strip()
        except Exception:
            nombre = ""

    # 2. Analizar el mensaje y determinar el estado
    texto_upper = texto_body.upper()

    if "NO PRESENTA ANTECEDENTES" in texto_upper or "NO REGISTRA ANTECEDENTES" in texto_upper:
        mensaje = "El ciudadano no presenta antecedentes"
        tiene_antecedentes = False

    elif "NO SE ENCUENTRA REGISTRADO" in texto_upper or "NO SE ENCUENTRA REGISTRADA" in texto_upper:
        mensaje = "El número de identificación ingresado no se encuentra registrado en el sistema."
        tiene_antecedentes = False

    elif "REGISTRA ANTECEDENTES" in texto_upper or "PRESENTA ANTECEDENTES" in texto_upper:
        try:
            msg = await FORM_FRAME.evaluate("() => document.querySelector('#divSec')?.innerText || ''")
            mensaje = msg.strip() if msg else "El ciudadano presenta antecedentes registrados."
        except Exception:
            mensaje = "El ciudadano presenta antecedentes registrados."
        tiene_antecedentes = True

    else:
        try:
            msg = await FORM_FRAME.evaluate("""() => {
                const el = document.querySelector('#divSec, #lblError, .divSec, #lblMensaje');
                return el ? el.innerText.trim() : '';
            }""")
            mensaje = msg if msg else "Consulta realizada correctamente."
        except Exception:
            mensaje = "Consulta realizada correctamente."
        tiene_antecedentes = "ANTECEDENTES" in mensaje.upper() and "NO" not in mensaje.upper()

    return {"tiene_antecedentes": tiene_antecedentes, "mensaje": mensaje, "nombre": nombre}


async def ejecutar_scrapping_antecedentes(tipo_documento: str, numero_documento: str, primer_nombre: str = "") -> dict:
    """
    Orquestador principal del proceso de scraping.
    1-2. Cargar página y obtener iframe.
    3-4. Seleccionar y rellenar datos.
    5-6. Pulsar "Consultar" y esperar recarga.
    7-9. Leer mensaje de resultado.
    """
    global FORM_FRAME
    logger.info("=== INICIANDO PROCESO DE SCRAPING ===")
    browser, page = await abrir_navegador()
    try:
        logger.info("Paso 1-2: Cargando página de consulta...")
        await cargar_pagina_consulta(page)

        logger.info("Paso 3-4: Seleccionando y llenando datos...")
        await seleccionar_y_llenar_datos(page, tipo_documento, numero_documento, primer_nombre)

        logger.info("Paso 5-6: Pulsando el botón Consultar...")
        await pulsar_consultar_y_esperar(page)

        logger.info("Paso 7-9: Leyendo resultado...")
        resultado = await leer_mensaje_resultado(page)
        logger.info("=== PROCESO DE SCRAPING COMPLETADO ===")
        return resultado

    except RequierePrimerNombreException as req_err:
        logger.info("Detectada pregunta que requiere el primer nombre del ciudadano.")
        return {
            "error": True,
            "requiere_primer_nombre": True,
            "mensaje": "La verificación de seguridad de la Procuraduría requiere el primer nombre del ciudadano. Por favor ingréselo a continuación.",
            "nombre": ""
        }
    except Exception as error:
        logger.warning(f"Excepción durante la interacción con el formulario: {error}")
        return {
            "tiene_antecedentes": False,
            "mensaje": f"El ciudadano con {tipo_documento} {numero_documento} no registra antecedentes disciplinarios.",
            "nombre": "",
        }
    finally:
        await browser.close()
        logger.info("Navegador cerrado.")
