const form = document.getElementById('antecedentesForm');
const btnSubmit = document.getElementById('btnSubmit');
const btnText = document.getElementById('btnText');
const spinner = document.getElementById('spinner');
const loadingText = document.getElementById('loadingText');
const result = document.getElementById('result');
const resultTitle = document.getElementById('resultTitle');
const resultDesc = document.getElementById('resultDesc');
const jsonBox = document.getElementById('jsonBox');

const baseResult = result.dataset.base.split(' ');

function setResult(type, title, desc, nombre) {
    result.className = '';
    result.classList.add(...baseResult);
    if (type) result.classList.add(type);
    if (title) {
        resultTitle.textContent = title;
        resultTitle.style.display = '';
    } else {
        resultTitle.style.display = 'none';
    }
    if (nombre) {
        resultDesc.innerHTML = '<div class="font-medium" style="color:inherit">' + nombre + '</div><i>' + desc + '</i>';
    } else {
        resultDesc.innerHTML = '<i>' + desc + '</i>';
    }
    result.style.display = 'block';
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const tipo = document.getElementById('tipo_documento').value;
    const numero = document.getElementById('numero_documento').value.trim();
    const primerNombre = document.getElementById('primer_nombre').value.trim();

    if (!numero) return;

    btnSubmit.disabled = true;
    spinner.style.display = 'inline-block';
    btnText.textContent = 'Consultando';
    loadingText.style.display = 'block';
    result.style.display = 'none';

    try {
        const response = await fetch('/consultar-antecedentes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tipo_documento: tipo,
                numero_documento: numero,
                primer_nombre: primerNombre
            })
        });

        let data;
        try {
            data = await response.json();
        } catch (jsonErr) {
            data = {
                error: true,
                mensaje: "El servidor devolvió una respuesta inesperada.",
                detalle: "Status HTTP: " + response.status
            };
        }

        jsonBox.textContent = JSON.stringify(data, null, 2);

        if (data.error) {
            setResult('error', 'Error en la consulta', data.mensaje);
        } else if (data.tiene_antecedentes) {
            setResult('error', 'Registra antecedentes', data.mensaje, data.nombre);
        } else {
            setResult('success', null, data.mensaje, data.nombre);
        }

    } catch (err) {
        setResult('error', 'Error de conexión', 'No se pudo establecer conexión con el servidor.');
        jsonBox.textContent = JSON.stringify({ error: true, detalle: err.message }, null, 2);
    } finally {
        btnSubmit.disabled = false;
        spinner.style.display = 'none';
        btnText.textContent = 'Consultar';
        loadingText.style.display = 'none';
    }
});
