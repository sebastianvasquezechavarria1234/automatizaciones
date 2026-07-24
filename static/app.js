const form = document.getElementById('antecedentesForm');
const btnSubmit = document.getElementById('btnSubmit');
const btnText = document.getElementById('btnText');
const spinner = document.getElementById('spinner');
const loadingText = document.getElementById('loadingText');
const result = document.getElementById('result');
const resultTitle = document.getElementById('resultTitle');
const resultDesc = document.getElementById('resultDesc');
const jsonBox = document.getElementById('jsonBox');

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const tipo = document.getElementById('tipo_documento').value;
    const numero = document.getElementById('numero_documento').value.trim();

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
                numero_documento: numero
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
            result.className = 'result error';
            resultTitle.textContent = 'Error en la consulta';
            resultDesc.textContent = data.mensaje;
        } else if (data.tiene_antecedentes) {
            result.className = 'result error';
            resultTitle.textContent = 'Registra antecedentes';
            resultDesc.textContent = data.mensaje;
        } else {
            result.className = 'result success';
            resultTitle.textContent = 'No registra antecedentes';
            resultDesc.textContent = data.mensaje;
        }

        result.style.display = 'block';

    } catch (err) {
        result.className = 'result error';
        resultTitle.textContent = 'Error de conexión';
        resultDesc.textContent = 'No se pudo establecer conexión con el servidor.';
        jsonBox.textContent = JSON.stringify({ error: true, detalle: err.message }, null, 2);
        result.style.display = 'block';
    } finally {
        btnSubmit.disabled = false;
        spinner.style.display = 'none';
        btnText.textContent = 'Consultar';
        loadingText.style.display = 'none';
    }
});
