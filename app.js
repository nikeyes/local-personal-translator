// Constants
const TRANSLATE_DEBOUNCE_MS = 500;
const SUCCESS_MESSAGE_DURATION_MS = 3000;
const COPY_CONFIRMATION_DURATION_MS = 2000;
const API_BASE_URL = 'http://127.0.0.1:8785';

// Error IDs for structured logging
const ERROR_IDS = {
    INIT_DOM_ERROR: 'INIT_DOM_001',
    TRANSLATION_NETWORK_ERROR: 'TRANS_NET_001',
    TRANSLATION_SERVER_ERROR: 'TRANS_SRV_002',
    TRANSLATION_VALIDATION_ERROR: 'TRANS_VAL_003',
    CLIPBOARD_ERROR: 'CLIP_ERR_001',
    URL_DECODE_ERROR: 'URL_DEC_001'
};

// Helper functions
function getRequiredElement(id) {
    const element = document.getElementById(id);
    if (!element) {
        throw new Error(`Required element missing: #${id}`);
    }
    return element;
}

function formatCharacterCount(length) {
    const plural = length !== 1 ? 's' : '';
    return `${length} character${plural}`;
}

function logError(errorId, message, context = {}) {
    const errorData = {
        id: errorId,
        message: message,
        context: context,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent
    };
    console.error(`[${errorId}]`, message, errorData);
}

function validateTranslationRequest(text, src, tgt) {
    const errors = [];
    // IMPORTANT: These values must match server-side validation in main.py
    const MAX_TEXT_LENGTH = 5000;
    const VALID_LANGS = ['en', 'es'];

    if (!text || text.trim().length === 0) {
        errors.push('Text cannot be empty');
    }

    if (text.length > MAX_TEXT_LENGTH) {
        errors.push(`Text too long (max ${MAX_TEXT_LENGTH} characters)`);
    }

    if (!VALID_LANGS.includes(src)) {
        errors.push(`Invalid source language: ${src}`);
    }

    if (!VALID_LANGS.includes(tgt)) {
        errors.push(`Invalid target language: ${tgt}`);
    }

    if (src === tgt) {
        errors.push('Source and target languages must be different');
    }

    return errors;
}

let sourceText, targetText, sourceLang, targetLang, swapBtn, copyBtn, charCount, status;

try {
    sourceText = getRequiredElement('sourceText');
    targetText = getRequiredElement('targetText');
    sourceLang = getRequiredElement('sourceLang');
    targetLang = getRequiredElement('targetLang');
    swapBtn = getRequiredElement('swapBtn');
    copyBtn = getRequiredElement('copyBtn');
    charCount = getRequiredElement('charCount');
    status = getRequiredElement('status');
} catch (error) {
    logError(ERROR_IDS.INIT_DOM_ERROR, 'Initialization failed', { error: error.message });
    document.body.innerHTML = `
        <div style="color: red; padding: 20px; font-family: sans-serif;">
            <h2>Initialization Error</h2>
            <p>${error.message}</p>
            <p>Please reload the page or contact support.</p>
            <p style="color: #666; font-size: 0.9em;">Error ID: ${ERROR_IDS.INIT_DOM_ERROR}</p>
        </div>
    `;
    throw error;
}

let translateTimeout = null;
let translateStartTime = null;
let currentRequestId = 0;
let statusTimeout = null;

// Update character count
sourceText.addEventListener('input', () => {
    charCount.textContent = formatCharacterCount(sourceText.value.length);

    // Auto-translate with debounce
    clearTimeout(translateTimeout);
    if (sourceText.value.trim()) {
        translateTimeout = setTimeout(translate, TRANSLATE_DEBOUNCE_MS);
    } else {
        targetText.value = '';
        copyBtn.disabled = true;
    }
});

// Translate function
async function translate() {
    const text = sourceText.value.trim();
    const src = sourceLang.value;
    const tgt = targetLang.value;

    // Validate input before making request
    const validationErrors = validateTranslationRequest(text, src, tgt);
    if (validationErrors.length > 0) {
        if (!text) {
            hideStatus();
            return;
        }
        showStatus(validationErrors[0], 'error');
        return;
    }

    // Create unique request ID to prevent race conditions
    const requestId = ++currentRequestId;

    translateStartTime = Date.now();
    showStatus('Translating...', 'info');
    targetText.value = '';
    copyBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE_URL}?src=${src}&tgt=${tgt}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'text/plain; charset=utf-8'
            },
            body: text
        });

        // Ignore response if a newer request was made
        if (requestId !== currentRequestId) {
            console.log('Ignoring stale response for request', requestId);
            return;
        }

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const translation = await response.text();
        const duration = ((Date.now() - translateStartTime) / 1000).toFixed(1);

        targetText.value = translation;
        copyBtn.disabled = false;
        showStatus(`Translated in ${duration}s`, 'success');

        // Hide success message after delay
        statusTimeout = setTimeout(hideStatus, SUCCESS_MESSAGE_DURATION_MS);
    } catch (error) {
        // Only show error if this is still the current request
        if (requestId !== currentRequestId) {
            return;
        }

        // Determine error type and ID
        let errorId, userMessage;
        if (error instanceof TypeError && error.message.includes('fetch')) {
            errorId = ERROR_IDS.TRANSLATION_NETWORK_ERROR;
            userMessage = `Cannot connect to server. Is it running on ${API_BASE_URL}?`;
        } else if (error.message.includes('HTTP 400')) {
            errorId = ERROR_IDS.TRANSLATION_VALIDATION_ERROR;
            userMessage = 'Invalid request to server';
        } else if (error.message.includes('HTTP 500')) {
            errorId = ERROR_IDS.TRANSLATION_SERVER_ERROR;
            userMessage = 'Internal server error';
        } else if (error.message.includes('HTTP')) {
            errorId = ERROR_IDS.TRANSLATION_SERVER_ERROR;
            userMessage = `Server error: ${error.message}`;
        } else {
            errorId = ERROR_IDS.TRANSLATION_SERVER_ERROR;
            userMessage = `Error: ${error.message}`;
        }

        logError(errorId, 'Translation failed', {
            error: error.message,
            name: error.name,
            src: src,
            tgt: tgt,
            textLength: text.length
        });

        showStatus(`${userMessage} (${errorId})`, 'error');
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

// Handle language selector changes (prevent same source/target)
function handleLanguageChange(changedSelector) {
    if (sourceLang.value === targetLang.value) {
        // Swap the other selector to opposite language
        const currentValue = sourceLang.value;
        const oppositeValue = currentValue === 'es' ? 'en' : 'es';

        if (changedSelector === 'source') {
            targetLang.value = oppositeValue;
        } else {
            sourceLang.value = oppositeValue;
        }
    }

    if (sourceText.value.trim()) {
        translate();
    }
}

sourceLang.addEventListener('change', () => handleLanguageChange('source'));
targetLang.addEventListener('change', () => handleLanguageChange('target'));

// Copy to clipboard
copyBtn.addEventListener('click', async () => {
    try {
        await navigator.clipboard.writeText(targetText.value);
        const copyTextElement = copyBtn.querySelector('.copy-text');
        const originalText = copyTextElement.textContent;
        copyTextElement.textContent = 'Copied!';
        setTimeout(() => {
            copyTextElement.textContent = originalText;
        }, COPY_CONFIRMATION_DURATION_MS);
    } catch (error) {
        logError(ERROR_IDS.CLIPBOARD_ERROR, 'Clipboard copy failed', {
            error: error.message,
            name: error.name
        });

        let message = 'Error copying to clipboard';
        if (error.name === 'NotAllowedError') {
            message += ': please allow clipboard access';
        } else if (error.name === 'SecurityError') {
            message += ': requires HTTPS';
        }

        showStatus(`${message} (${ERROR_IDS.CLIPBOARD_ERROR})`, 'error');
    }
});

// Status messages
function showStatus(message, type = 'info') {
    // Clear any pending hide operation to prevent race conditions
    if (statusTimeout) {
        clearTimeout(statusTimeout);
        statusTimeout = null;
    }
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
        charCount.textContent = formatCharacterCount(text.length);

        // Clear URL params (clean URL bar)
        window.history.replaceState({}, document.title, '/');

        // Trigger translation
        translate();
    } catch (e) {
        logError(ERROR_IDS.URL_DECODE_ERROR, 'URL decoding failed', {
            error: e.message,
            stack: e.stack,
            encodedText: encodedText ? encodedText.substring(0, 50) + '...' : 'undefined'
        });
        showStatus(`Error decoding URL text: ${e.message} (${ERROR_IDS.URL_DECODE_ERROR})`, 'error');
    }
}
