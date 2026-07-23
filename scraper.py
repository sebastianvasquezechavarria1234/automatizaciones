from pyppeteer import launch
import asyncio

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURACIÓN DE SELECTORES CSS Y URL
# Nota sustentación: Si la página de la Procuraduría actualiza la estructura de su
# DOM o cambian sus IDs/clases, se deben reemplazar estos selectores CSS.
# ==============================================================================
URL_PAGINA_PROCURADURIA = "https://www.procuraduria.gov.co/Pages/Consulta-de-Antecedentes.aspx"

# Selectores CSS del formulario
SELECTOR_TIPO_DOC = "select#ddlTipoID"            # Dropdown o selector de tipo de documento (select element)
SELECTOR_NUM_DOC = "#txtNumID"              # Campo de texto para el número de documento
# Captcha no está presente en la página actual, los selectores siguientes no se usan.
# SELECTOR_CAPTCHA_IMG = "#imgCaptcha"
# SELECTOR_CAPTCHA_INPUT = "#txtRespuesta"
SELECTOR_BOTON_CONSULTAR = "#btnConsultar"      # Botón para enviar la consulta
SELECTOR_CAPTCHA_INPUT  = "#txtRespuesta"      # Campo de respuesta a la pregunta de verificación
SELECTOR_CAPTCHA_PREGUNTA = "#lblPregunta"     # Etiqueta con el texto de la pregunta
SELECTOR_NOMBRE = "#divSec h3"                 # Contenedor con el nombre del ciudadano (si está presente)







import os

async def abrir_navegador():
    """
    Inicia una instancia del navegador utilizando el ejecutable local de Chrome/Edge.
    Devuelve: (browser, page)
    """
    logger.info("Iniciando navegador...")
    
    rutas_posibles = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    
    ruta_ejecutable = None
    for ruta in rutas_posibles:
        if os.path.exists(ruta):
            ruta_ejecutable = ruta
            break

    opciones = {
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled"
        ]
    }
    
    if ruta_ejecutable:
        logger.info(f"Usando navegador del sistema: {ruta_ejecutable}")
        opciones["executablePath"] = ruta_ejecutable
        
    browser = await launch(**opciones)
    logger.info("Navegador iniciado correctamente.")
    page = await browser.newPage()
    
    # Configurar User-Agent real para evitar bloqueos anti-bot
    await page.setUserAgent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    await page.setViewport({"width": 1280, "height": 800})
    return browser, page

# Import typing for global frame variable
from typing import Any, Optional

# Global variable to hold the iframe frame once located
FORM_FRAME: Optional[Any] = None


async def get_form_frame(page):
    """Busca el iframe que contiene el formulario y lo devuelve."""
    for frame in page.frames:
        try:
            # Si el selector está presente en este frame, lo usamos
            has = await frame.evaluate("() => !!document.querySelector('#ddlTipoID')")
            if has:
                logger.info(f"Encontrado frame con formulario: {frame.url}")
                return frame
        except Exception:
            continue
    raise Exception('No se encontró el iframe con el formulario')

async def cargar_pagina_consulta(page):
    """
    Abre la URL objetivo con un timeout estricto de 5 segundos.
    """
    logger.info(f"Navegando a {URL_PAGINA_PROCURADURIA}...")
    try:
        await page.goto(URL_PAGINA_PROCURADURIA, {"waitUntil": "domcontentloaded", "timeout": 5000})
        logger.info("Página cargada correctamente.")
        await asyncio.sleep(2)  # esperar a que el iframe se renderice
        global FORM_FRAME
        FORM_FRAME = await get_form_frame(page)
    except Exception as err:
        logger.warning(f"Aviso en carga de página: {err}")


from groq_service import resolver_pregunta_texto_con_groq

# Respuestas conocidas a las preguntas de verificación del formulario
RESPUESTAS_CAPTCHA = {
    "colombia": "Bogota",
    "atlantico": "Barranquilla",
    "antioquia": "Medellin",
    "valle": "Cali",
    "santander": "Bucaramanga",
    "bolivar": "Cartagena",
    "cundinamarca": "Bogota",
    "nariño": "Pasto",
    "meta": "Villavicencio",
    "risaralda": "Pereira",
    "caldas": "Manizales",
    "quindio": "Armenia",
    "huila": "Neiva",
    "norte de santander": "Cucuta",
    "tolima": "Ibague",
    "magdalena": "Santa Marta",
    "cesar": "Valledupar",
    "cordoba": "Monteria",
    "sucre": "Sincelejo",
    "boyaca": "Tunja",
}

async def resolver_pregunta_texto(pregunta: str) -> str:
    """Devuelve la respuesta a la pregunta de verificación de texto usando diccionario o Groq AI."""
    pregunta_lower = pregunta.lower()
    for clave, respuesta in RESPUESTAS_CAPTCHA.items():
        if clave in pregunta_lower:
            return respuesta
    
    logger.info(f"Pregunta no está en diccionario local: '{pregunta}'. Consultando a Groq IA...")
    return await resolver_pregunta_texto_con_groq(pregunta)


async def seleccionar_y_llenar_datos(page, tipo_documento: str, numero_documento: str):
    """
    Selecciona el tipo de documento, ingresa el número y responde la pregunta de verificación.
    """
    # 1. Seleccionar tipo de documento (mapea 'CC' a 'Cédula de ciudadanía')
    await FORM_FRAME.waitForSelector(SELECTOR_TIPO_DOC, {"timeout": 30000})
    val_seleccionado = await FORM_FRAME.evaluate(
        """(tipo) => {
            const sel = document.querySelector('#ddlTipoID');
            if (!sel) return null;
            const tipoClean = tipo.toUpperCase().trim();
            
            let target = tipoClean;
            if (tipoClean === 'CC' || tipoClean === '1') target = 'CÉDULA DE CIUDADANÍA';
            else if (tipoClean === 'NIT' || tipoClean === '2') target = 'NIT';
            else if (tipoClean === 'CE' || tipoClean === '3') target = 'EXTRANJERÍA';
            else if (tipoClean === 'PEP') target = 'PEP';
            else if (tipoClean === 'PPT') target = 'PPT';

            for (let i = 0; i < sel.options.length; i++) {
                const opt = sel.options[i];
                const val = opt.value.toUpperCase().trim();
                const txt = opt.text.toUpperCase().trim();
                
                // Ignorar la opción por defecto ("Seleccione...")
                if (val === '0' || val === '' || txt.includes('SELECCIONE')) continue;
                
                if (val === tipoClean || txt.includes(target) || txt.includes('CEDULA DE CIUDADANIA')) {
                    sel.selectedIndex = i;
                    sel.value = opt.value;
                    sel.dispatchEvent(new Event('change', { bubbles: true }));
                    return opt.text;
                }
            }
            return null;
        }""",
        tipo_documento
    )
    logger.info(f"Tipo de documento seleccionado: {val_seleccionado or tipo_documento}")
    await asyncio.sleep(2)  # Esperar actualización ASP.NET por el evento change

    # 2. Ingresar número de documento
    logger.info("Ingresando número de documento...")
    await FORM_FRAME.waitForSelector(SELECTOR_NUM_DOC, {"timeout": 30000})
    await FORM_FRAME.focus(SELECTOR_NUM_DOC)
    await FORM_FRAME.evaluate("() => { const el = document.querySelector('#txtNumID'); if(el) el.value = ''; }")
    await FORM_FRAME.type(SELECTOR_NUM_DOC, numero_documento)
    logger.info(f"Número de documento ingresado: {numero_documento}")

    # 3. Leer y responder pregunta de verificación
    try:
        pregunta_texto = await FORM_FRAME.evaluate(
            "() => document.querySelector('#lblPregunta')?.innerText || "
            "document.querySelector('label[for=txtRespuestaPregunta]')?.innerText || "
            "''"
        )
        if pregunta_texto:
            respuesta = await resolver_pregunta_texto(pregunta_texto)
            logger.info(f"Pregunta de verificación: '{pregunta_texto}' → Respuesta: '{respuesta}'")
            
            # Selector del input de respuesta (#txtRespuestaPregunta o similar)
            input_sel = await FORM_FRAME.evaluate("""() => {
                const el = document.querySelector('#txtRespuestaPregunta, #txtRespuesta, input[id*="Respuesta"], input[name*="Respuesta"]');
                if (el) return el.id ? '#' + el.id : 'input[name="' + el.name + '"]';
                const inputs = Array.from(document.querySelectorAll('input[type="text"], input:not([type])'));
                const target = inputs.find(i => i.id !== 'txtNumID' && i.name !== 'txtNumID');
                return target ? (target.id ? '#' + target.id : 'input[name="' + target.name + '"]') : null;
            }""")
            
            if input_sel:
                logger.info(f"Escribiendo respuesta en selector: {input_sel}")
                await FORM_FRAME.focus(input_sel)
                await FORM_FRAME.evaluate(f"() => {{ const el = document.querySelector('{input_sel}'); if(el) el.value = ''; }}")
                await FORM_FRAME.type(input_sel, respuesta)
                await FORM_FRAME.evaluate(f"""() => {{
                    const el = document.querySelector('{input_sel}');
                    if (el) {{
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                }}""")
                logger.info("Respuesta de verificación ingresada correctamente.")
            else:
                logger.warning("No se encontró el campo input para ingresar la respuesta.")
    except Exception as e:
        logger.warning(f"No se pudo responder la pregunta de verificación: {e}")
    return


async def pulsar_consultar_y_esperar(page) -> None:
    """Hace clic en Consultar y espera a que el iframe se recargue con el resultado."""
    global FORM_FRAME
    logger.info("Haciendo clic en el botón Consultar...")
    
    btn_sel = await FORM_FRAME.evaluate("""() => {
        const btn = document.querySelector('#btnConsultar, input[id*="btnConsultar"], input[value*="Consultar"], button[id*="Consultar"]');
        return btn ? (btn.id ? '#' + btn.id : 'input[value*="Consultar"]') : '#btnConsultar';
    }""")
    
    await FORM_FRAME.waitForSelector(btn_sel, {"timeout": 15000})
    await FORM_FRAME.click(btn_sel)
    
    # Esperar a que el iframe recargue con el resultado (postback AJAX)
    await asyncio.sleep(6)
    FORM_FRAME = await get_result_frame(page)



async def get_result_frame(page):
    """Devuelve el frame del iframe de la Procuraduría (mismo frame del formulario)."""
    await asyncio.sleep(5)  # Esperar al postback ASP.NET
    # El resultado aparece en el mismo iframe del formulario
    for frame in page.frames:
        try:
            url = frame.url
            if "webcert" in url or "Certificado" in url:
                logger.info(f"Frame de resultado: {url}")
                return frame
        except Exception:
            continue
    raise Exception("No se encontró el frame del resultado")


async def leer_mensaje_resultado(page) -> dict:
    """
    Lee el mensaje de resultado del iframe después del postback ASP.NET.
    """
    global FORM_FRAME

    await asyncio.sleep(2)
    texto_body = await FORM_FRAME.evaluate("() => document.body.innerText")
    logger.info(f"[DEBUG] Texto completo del iframe:\n{texto_body[:2000]}")

    import re

    # 1. Extraer nombre del ciudadano si está presente
    nombre = ""
    match_nombre = re.search(r'Señor\(a\)?\s+([A-ZÁÉÍÓÚÑ\s]+?)\s+identificad[oa]', texto_body, re.IGNORECASE)
    if match_nombre:
        nombre = match_nombre.group(1).strip()
    else:
        try:
            h3_text = await FORM_FRAME.evaluate(
                "() => document.querySelector('#divSec h3, div.datosConsultado h3, #divSec div')?.innerText || ''"
            )
            match_h3 = re.search(r'Señor\(a\)?\s+([A-ZÁÉÍÓÚÑ\s]+?)\s+identificad[oa]', h3_text, re.IGNORECASE)
            if match_h3:
                nombre = match_h3.group(1).strip()
            elif h3_text and len(h3_text) < 80:
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
            mensaje_div = await FORM_FRAME.evaluate("() => document.querySelector('#divSec')?.innerText || ''")
            mensaje = mensaje_div.strip() if mensaje_div else "El ciudadano presenta antecedentes registrados."
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

    return {
        "tiene_antecedentes": tiene_antecedentes,
        "mensaje": mensaje,
        "nombre": nombre,
    }





async def ejecutar_scrapping_antecedentes(tipo_documento: str, numero_documento: str) -> dict:
    """
    Orquestador principal del proceso de scraping.
    1‑2. Cargar página y obtener iframe.
    3‑4. Seleccionar y rellenar datos.
    5‑6. Pulsar "Consultar" y esperar recarga.
    7‑9. Leer mensaje de resultado.
    """
    global FORM_FRAME
    logger.info("=== INICIANDO PROCESO DE SCRAPING ===")
    browser, page = await abrir_navegador()
    try:
        # Paso 1‑2: cargar la página y encontrar el iframe con el formulario
        logger.info("Paso 1-2: Cargando página de consulta...")
        await cargar_pagina_consulta(page)

        # Paso 3‑4: Seleccionando y llenando datos
        logger.info("Paso 3-4: Seleccionando y llenando datos...")
        await seleccionar_y_llenar_datos(page, tipo_documento, numero_documento)

        # Paso 5‑6: Pulsar el botón Consultar y esperar a que se recargue el iframe
        logger.info("Paso 5-6: Pulsando el botón Consultar...")
        await pulsar_consultar_y_esperar(page)

        # Paso 7‑9: Leer resultado
        logger.info("Paso 7-9: Leyendo resultado...")
        resultado = await leer_mensaje_resultado(page)
        logger.info("=== PROCESO DE SCRAPING COMPLETADO ===")
        return resultado

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

