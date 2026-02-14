const sourceText = document.getElementById('sourceText');
const targetText = document.getElementById('targetText');
const sourceLang = document.getElementById('sourceLang');
const targetLang = document.getElementById('targetLang');
const swapBtn = document.getElementById('swapBtn');
const copyBtn = document.getElementById('copyBtn');
const charCount = document.getElementById('charCount');
const status = document.getElementById('status');

let translateTimeout = null;
let translateStartTime = null;

// Update character count
sourceText.addEventListener('input', () => {
    const length = sourceText.value.length;
    charCount.textContent = `${length} caractere${length !== 1 ? 's' : ''}`;

    // Auto-translate with debounce
    clearTimeout(translateTimeout);
    if (sourceText.value.trim()) {
        translateTimeout = setTimeout(translate, 500);
    } else {
        targetText.value = '';
        copyBtn.disabled = true;
    }
});

// Translate function
async function translate() {
    const text = sourceText.value.trim();
    if (!text) {
        hideStatus();
        return;
    }

    const src = sourceLang.value;
    const tgt = targetLang.value;

    if (src === tgt) {
        showStatus('Los idiomas de origen y destino deben ser diferentes', 'error');
        return;
    }

    translateStartTime = Date.now();
    showStatus('Traduciendo...', 'info');
    targetText.value = '';
    copyBtn.disabled = true;

    try {
        const response = await fetch(`http://127.0.0.1:8785?src=${src}&tgt=${tgt}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'text/plain; charset=utf-8'
            },
            body: text
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const translation = await response.text();
        const duration = ((Date.now() - translateStartTime) / 1000).toFixed(1);

        targetText.value = translation;
        copyBtn.disabled = false;
        showStatus(`Traducido en ${duration}s`, 'success');

        // Hide success message after 3 seconds
        setTimeout(hideStatus, 3000);
    } catch (error) {
        showStatus(`Error: ${error.message}. ¿Está el servidor corriendo?`, 'error');
        console.error('Translation error:', error);
    }
}

// Swap languages
swapBtn.addEventListener('click', () => {
    const tempLang = sourceLang.value;
    sourceLang.value = targetLang.value;
    targetLang.value = tempLang;

    const tempText = sourceText.value;
    sourceText.value = targetText.value;
    targetText.value = tempText;

    if (sourceText.value.trim()) {
        translate();
    }
});

// Language selector changes
sourceLang.addEventListener('change', () => {
    if (targetLang.value === sourceLang.value) {
        targetLang.value = sourceLang.value === 'es' ? 'en' : 'es';
    }
    if (sourceText.value.trim()) {
        translate();
    }
});

targetLang.addEventListener('change', () => {
    if (targetLang.value === sourceLang.value) {
        sourceLang.value = targetLang.value === 'es' ? 'en' : 'es';
    }
    if (sourceText.value.trim()) {
        translate();
    }
});

// Copy to clipboard
copyBtn.addEventListener('click', async () => {
    try {
        await navigator.clipboard.writeText(targetText.value);
        const originalText = copyBtn.querySelector('.copy-text').textContent;
        copyBtn.querySelector('.copy-text').textContent = '¡Copiado!';
        setTimeout(() => {
            copyBtn.querySelector('.copy-text').textContent = originalText;
        }, 2000);
    } catch (error) {
        showStatus('Error al copiar al portapapeles', 'error');
    }
});

// Status messages
function showStatus(message, type = 'info') {
    status.textContent = message;
    status.className = `status visible ${type}`;
}

function hideStatus() {
    status.classList.remove('visible');
}

// Initialize
copyBtn.disabled = true;

// Check URL parameters (from shortcuts - text is base64 encoded)
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.has('text')) {
    try {
        // Decode base64 text
        const encodedText = urlParams.get('text');
        const decodedText = atob(encodedText.replace(/-/g, '+').replace(/_/g, '/'));
        const text = decodeURIComponent(escape(decodedText)); // Handle UTF-8

        const src = urlParams.get('src') || 'es';
        const tgt = urlParams.get('tgt') || 'en';

        // Set values
        sourceLang.value = src;
        targetLang.value = tgt;
        sourceText.value = text;

        // Update char count
        const length = text.length;
        charCount.textContent = `${length} caractere${length !== 1 ? 's' : ''}`;

        // Clear URL params (clean URL bar)
        window.history.replaceState({}, document.title, '/');

        // Trigger translation
        translate();
    } catch (e) {
        showStatus('Error al decodificar el texto de la URL', 'error');
    }
}
