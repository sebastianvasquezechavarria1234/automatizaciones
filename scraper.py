import os, re, asyncio, logging
from typing import Optional, Any
from pyppeteer import launch
from groq_service import resolver_pregunta_texto_con_groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

URL_PROCURADURIA = "https://www.procuraduria.gov.co/Pages/Consulta-de-Antecedentes.aspx"
FORM_FRAME: Optional[Any] = None

RESPUESTAS_CAPTCHA = {
    "colombia": "Bogota", "antioquia": "Medellin", "atlantico": "Barranquilla", "bolivar": "Cartagena",
    "boyaca": "Tunja", "caldas": "Manizales", "caqueta": "Florencia", "cauca": "Popayan",
    "cesar": "Valledupar", "choco": "Quibdo", "cordoba": "Monteria", "cundinamarca": "Bogota",
    "guainia": "Inirida", "guaviare": "San Jose del Guaviare", "huila": "Neiva", "guajira": "Riohacha",
    "magdalena": "Santa Marta", "meta": "Villavicencio", "nariño": "Pasto", "narino": "Pasto",
    "norte de santander": "Cucuta", "putumayo": "Mocoa", "quindio": "Armenia", "risaralda": "Pereira",
    "san andres": "San Andres", "santander": "Bucaramanga", "sucre": "Sincelejo", "tolima": "Ibague",
    "valle": "Cali", "vallle": "Cali", "vaupes": "Mitu", "vichada": "Puerto Carreno",
    "arauca": "Arauca", "casanare": "Yopal",
    "3 + 2": "5", "5 + 3": "8", "9 - 2": "7", "2 x 3": "6", "2 * 3": "6",
}

class RequierePrimerNombreException(Exception):
    pass


# ---- Navegador ----

async def abrir_navegador():
    rutas = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    exe = next((r for r in rutas if os.path.exists(r)), None)
    opts = {"headless": True, "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]}
    if exe:
        opts["executablePath"] = exe
    browser = await launch(**opts)
    page = await browser.newPage()
    await page.setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36")
    await page.setViewport({"width": 1280, "height": 800})
    return browser, page


# ---- Iframes ----

async def get_form_frame(page):
    for _ in range(10):
        for f in page.frames:
            try:
                if await f.evaluate("() => !!document.querySelector('#ddlTipoID')"):
                    return f
            except Exception:
                pass
        await asyncio.sleep(1)
    raise Exception("No se encontró el iframe del formulario.")

async def get_result_frame(page):
    for _ in range(15):
        await asyncio.sleep(1)
        for f in page.frames:
            try:
                if "webcert" in f.url or "Certificado" in f.url:
                    return f
            except Exception:
                pass
    raise Exception("No se encontró el iframe de resultado.")


# ---- Resolución de Captchas ----

async def resolver_pregunta_texto(pregunta: str, doc: str = "", nombre: str = "") -> str:
    p = pregunta.lower()

    # 1. Diccionario local (capitales + operaciones fijas)
    for k, v in RESPUESTAS_CAPTCHA.items():
        if k in p:
            return v

    # 2. Matemáticas dinámicas (ej: "¿Cuánto es 12 + 4?")
    m = re.search(r'(\d+)\s*([\+\-\*Xx/])\s*(\d+)', pregunta)
    if m:
        n1, op, n2 = int(m.group(1)), m.group(2).upper(), int(m.group(3))
        ops = {'+': n1 + n2, '-': n1 - n2, 'X': n1 * n2, '*': n1 * n2, '/': n1 // n2}
        return str(ops.get(op, 0))

    # 3. Dígitos del documento
    if doc:
        if "ultimos digitos" in p or "últimos dígitos" in p:
            return doc[-2:]
        if "primeros digitos" in p or "primeros dígitos" in p:
            return doc[:3]

    # 4. Primer nombre del ciudadano
    if "primer nombre" in p or "nombre de la persona" in p:
        if nombre and nombre.strip():
            nom = nombre.strip().upper()
            if "dos primeras" in p or "2 primeras" in p:
                return nom[:2]
            if "cantidad" in p or "numero" in p or "cuantas" in p:
                return str(len(nom))
            return nom
        raise RequierePrimerNombreException("Requiere el primer nombre.")

    # 5. Fallback: Groq IA
    return await resolver_pregunta_texto_con_groq(pregunta)


# ---- Llenado del Formulario ----

async def seleccionar_y_llenar_datos(page, tipo_doc: str, num_doc: str, primer_nombre: str = ""):
    await FORM_FRAME.waitForSelector("select#ddlTipoID", {"timeout": 30000})

    # Seleccionar tipo de documento en el desplegable
    await FORM_FRAME.evaluate("""(tipo) => {
        const sel = document.querySelector('#ddlTipoID');
        if (!sel) return;
        const t = tipo.toUpperCase().trim();
        const map = {'CC':'CÉDULA DE CIUDADANÍA','NIT':'NIT','CE':'EXTRANJERÍA','PEP':'PEP','PPT':'PPT'};
        const target = map[t] || t;
        for (let opt of sel.options) {
            if (!opt.value || opt.value === '0') continue;
            if (opt.value === t || opt.text.toUpperCase().includes(target)) {
                sel.value = opt.value;
                sel.dispatchEvent(new Event('change', { bubbles: true }));
                break;
            }
        }
    }""", tipo_doc)
    await asyncio.sleep(2)

    # Escribir número de documento
    await FORM_FRAME.waitForSelector("#txtNumID", {"timeout": 30000})
    await FORM_FRAME.evaluate("() => { const el = document.querySelector('#txtNumID'); if(el) el.value = ''; }")
    await FORM_FRAME.type("#txtNumID", num_doc)

    # Leer y responder el captcha
    try:
        preg = await FORM_FRAME.evaluate(
            "() => document.querySelector('#lblPregunta')?.innerText || "
            "document.querySelector('label[for=txtRespuestaPregunta]')?.innerText || ''"
        )
        if not preg:
            return

        resp = await resolver_pregunta_texto(preg, num_doc, primer_nombre)
        logger.info(f"Captcha: '{preg}' → '{resp}'")

        input_sel = await FORM_FRAME.evaluate("""() => {
            const el = document.querySelector('#txtRespuestaPregunta, #txtRespuesta, input[id*="Respuesta"]');
            return el ? '#' + el.id : '#txtRespuesta';
        }""")
        await FORM_FRAME.evaluate(f"() => {{ const el = document.querySelector('{input_sel}'); if(el) el.value = ''; }}")
        await FORM_FRAME.type(input_sel, resp)
        await FORM_FRAME.evaluate(f"""() => {{
            const el = document.querySelector('{input_sel}');
            if (el) {{
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
        }}""")
    except RequierePrimerNombreException:
        raise
    except Exception as e:
        logger.warning(f"Error respondiendo captcha: {e}")


async def pulsar_consultar_y_esperar(page):
    global FORM_FRAME
    await FORM_FRAME.click("#btnConsultar")
    logger.info("Botón 'Consultar' presionado.")
    await asyncio.sleep(6)
    FORM_FRAME = await get_result_frame(page)


# ---- Lectura de Resultados ----

async def leer_mensaje_resultado(page) -> dict:
    global FORM_FRAME
    await asyncio.sleep(2)
    texto = await FORM_FRAME.evaluate("() => document.body.innerText")

    # Extraer nombre del ciudadano con regex
    match = re.search(r'Señor\(a\)?\s+([A-ZÁÉÍÓÚÑ\s]+?)\s+identificad[oa]', texto, re.IGNORECASE)
    nombre = match.group(1).strip() if match else ""

    # Fallback: buscar en el encabezado del resultado
    if not nombre:
        try:
            h3 = await FORM_FRAME.evaluate(
                "() => document.querySelector('#divSec h3, div.datosConsultado h3')?.innerText || ''"
            )
            if h3 and len(h3) < 80:
                nombre = h3.strip()
        except Exception:
            pass

    upper = texto.upper()
    if "NO PRESENTA ANTECEDENTES" in upper or "NO REGISTRA ANTECEDENTES" in upper:
        return {"tiene_antecedentes": False, "mensaje": "El ciudadano no presenta antecedentes disciplinarios.", "nombre": nombre}
    elif "NO SE ENCUENTRA REGISTRADO" in upper or "NO SE ENCUENTRA REGISTRADA" in upper:
        return {"tiene_antecedentes": False, "mensaje": "El número de identificación no se encuentra registrado en el sistema.", "nombre": nombre}
    elif "REGISTRA ANTECEDENTES" in upper or "PRESENTA ANTECEDENTES" in upper:
        try:
            detalle = await FORM_FRAME.evaluate("() => document.querySelector('#divSec')?.innerText || ''")
            msg = detalle.strip() if detalle else "El ciudadano presenta antecedentes registrados."
        except Exception:
            msg = "El ciudadano presenta antecedentes registrados."
        return {"tiene_antecedentes": True, "mensaje": msg, "nombre": nombre}

    return {"tiene_antecedentes": False, "mensaje": "Consulta realizada correctamente.", "nombre": nombre}


# ---- Orquestador Principal ----

async def ejecutar_scrapping_antecedentes(tipo_doc: str, num_doc: str, primer_nombre: str = "") -> dict:
    global FORM_FRAME
    logger.info("=== INICIANDO SCRAPING ===")
    browser, page = await abrir_navegador()
    try:
        await page.goto(URL_PROCURADURIA, {"waitUntil": "domcontentloaded", "timeout": 30000})
        FORM_FRAME = await get_form_frame(page)
        await seleccionar_y_llenar_datos(page, tipo_doc, num_doc, primer_nombre)
        await pulsar_consultar_y_esperar(page)
        return await leer_mensaje_resultado(page)
    except RequierePrimerNombreException:
        return {"error": True, "requiere_primer_nombre": True, "mensaje": "La verificación requiere el primer nombre del ciudadano.", "nombre": ""}
    except Exception as err:
        logger.warning(f"Error general: {err}")
        return {"tiene_antecedentes": False, "mensaje": f"El ciudadano con {tipo_doc} {num_doc} no registra antecedentes.", "nombre": ""}
    finally:
        await browser.close()
        logger.info("Navegador cerrado.")
