// Constants
const TRANSLATE_DEBOUNCE_MS = 500;
const SUCCESS_MESSAGE_DURATION_MS = 3000;
const COPY_CONFIRMATION_DURATION_MS = 2000;
const API_BASE_URL = 'http://127.0.0.1:8785';
const MODE_TRANSLATE = 'translate';
const MODE_IMPROVE = 'improve';

// Error IDs for structured logging
const ERROR_IDS = {
    INIT_DOM_ERROR: 'INIT_DOM_001',
    TRANSLATION_NETWORK_ERROR: 'TRANS_NET_001',
    TRANSLATION_SERVER_ERROR: 'TRANS_SRV_002',
    TRANSLATION_VALIDATION_ERROR: 'TRANS_VAL_003',
    CLIPBOARD_ERROR: 'CLIP_ERR_001',
    URL_DECODE_ERROR: 'URL_DEC_001',
    ALTERNATIVES_FETCH_ERROR: 'ALT_FETCH_001',
    ALTERNATIVES_PARSE_ERROR: 'ALT_PARSE_002'
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

function validateTranslationRequest(text, src, tgt, mode) {
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

    if (mode === MODE_TRANSLATE && src === tgt) {
        errors.push('Source and target languages must be different');
    }

    return errors;
}

let sourceText, targetText, sourceLang, targetLang, swapBtn, swapBtnContainer, copyBtn, charCount, status, modelSelect;
let translateTab, improveTab, outputHeader, temperatureSlider, temperatureValue;

try {
    sourceText = getRequiredElement('sourceText');
    targetText = getRequiredElement('targetText');
    sourceLang = getRequiredElement('sourceLang');
    targetLang = getRequiredElement('targetLang');
    swapBtn = getRequiredElement('swapBtn');
    swapBtnContainer = getRequiredElement('swapBtnContainer');
    copyBtn = getRequiredElement('copyBtn');
    charCount = getRequiredElement('charCount');
    status = getRequiredElement('status');
    modelSelect = getRequiredElement('modelSelect');
    translateTab = getRequiredElement('translateTab');
    improveTab = getRequiredElement('improveTab');
    outputHeader = getRequiredElement('outputHeader');
    temperatureSlider = getRequiredElement('temperatureSlider');
    temperatureValue = getRequiredElement('temperatureValue');
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
let currentMode = MODE_TRANSLATE;

// Alternatives popup state
let alternativesPopup = null;
let currentWord = null;
let currentWordStart = null;
let currentWordEnd = null;

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
    let src = sourceLang.value;
    let tgt = targetLang.value;

    // In improve mode, set src and tgt to the same language
    if (currentMode === MODE_IMPROVE) {
        tgt = src;
    }

    // Validate input before making request
    const validationErrors = validateTranslationRequest(text, src, tgt, currentMode);
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
    const actionVerb = currentMode === MODE_IMPROVE ? 'Improving' : 'Translating';
    showStatus(`${actionVerb}...`, 'info');
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

        // Get server-side timing if available
        const serverTime = response.headers.get('X-Translation-Time');
        const actionPastTense = currentMode === MODE_IMPROVE ? 'Improved' : 'Translated';
        let timeMessage;
        if (serverTime) {
            const serverSeconds = parseFloat(serverTime);
            const totalSeconds = ((Date.now() - translateStartTime) / 1000).toFixed(1);
            timeMessage = `${actionPastTense} in ${serverSeconds.toFixed(2)}s (total: ${totalSeconds}s)`;
        } else {
            const duration = ((Date.now() - translateStartTime) / 1000).toFixed(1);
            timeMessage = `${actionPastTense} in ${duration}s`;
        }

        targetText.value = translation;
        copyBtn.disabled = false;
        showStatus(timeMessage, 'success');

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

        const actionName = currentMode === MODE_IMPROVE ? 'Improvement' : 'Translation';
        logError(errorId, `${actionName} failed`, {
            error: error.message,
            name: error.name,
            src: src,
            tgt: tgt,
            textLength: text.length,
            mode: currentMode
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

// Model selection
modelSelect.addEventListener('change', async () => {
    const newModel = modelSelect.value;
    const previousModel = modelSelect.value;

    try {
        showStatus('Loading model...', 'info');
        modelSelect.disabled = true;

        const response = await fetch(`${API_BASE_URL}/api/model`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ model: newModel })
        });

        if (!response.ok) {
            throw new Error(`Failed to load model: HTTP ${response.status}`);
        }

        const result = await response.json();

        if (result.status === 'loaded') {
            showStatus(`Switched to ${newModel} model`, 'success');
            // Re-translate if there's text
            if (sourceText.value.trim()) {
                setTimeout(translate, 500);
            } else {
                setTimeout(hideStatus, 2000);
            }
        } else if (result.status === 'already_loaded') {
            hideStatus();
        }

        modelSelect.disabled = false;

    } catch (error) {
        console.error('Failed to change model:', error);
        showStatus(`Error loading model: ${error.message}`, 'error');
        modelSelect.value = previousModel; // Revert selection
        modelSelect.disabled = false;
    }
});

// Fetch current model on load
async function loadCurrentModel() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/model`);
        if (response.ok) {
            const data = await response.json();
            modelSelect.value = data.model;
        }
    } catch (error) {
        console.error('Failed to fetch current model:', error);
    }
}

// Mode switching
function setMode(mode) {
    currentMode = mode;

    // Update tab active state
    if (mode === MODE_TRANSLATE) {
        translateTab.classList.add('active');
        improveTab.classList.remove('active');
        swapBtnContainer.classList.remove('hidden');
        targetLang.parentElement.classList.remove('hidden');
        sourceText.placeholder = 'Type or paste text here...';
        targetText.placeholder = 'Translation will appear here...';
    } else {
        improveTab.classList.add('active');
        translateTab.classList.remove('active');
        swapBtnContainer.classList.add('hidden');
        targetLang.parentElement.classList.add('hidden');
        sourceText.placeholder = 'Type or paste text to improve...';
        targetText.placeholder = 'Improved text will appear here...';
    }

    // Clear output, preserve input
    targetText.value = '';
    copyBtn.disabled = true;
    hideStatus();

    // Re-translate if there's text
    if (sourceText.value.trim()) {
        translate();
    }
}

translateTab.addEventListener('click', () => setMode(MODE_TRANSLATE));
improveTab.addEventListener('click', () => setMode(MODE_IMPROVE));

// Temperature slider
temperatureSlider.addEventListener('input', () => {
    temperatureValue.textContent = temperatureSlider.value;
});

// Word alternatives functionality

function getWordAtPosition(text, position) {
    if (!text || position < 0 || position >= text.length) return null;

    let start = position;
    let end = position;

    // Expand to word boundaries (alphanumeric + accented chars)
    const wordChar = /[a-zA-ZáéíóúñÁÉÍÓÚÑ]/;

    while (start > 0 && wordChar.test(text[start - 1])) {
        start--;
    }

    while (end < text.length && wordChar.test(text[end])) {
        end++;
    }

    const word = text.substring(start, end);

    // Validate: must be alphabetic, min 2 chars
    if (!word || word.length < 2 || !/^[a-zA-ZáéíóúñÁÉÍÓÚÑ]+$/.test(word)) {
        return null;
    }

    return { word, start, end };
}

async function handleTargetTextClick(event) {
    const textarea = event.target;
    const clickPosition = textarea.selectionStart;
    const text = textarea.value;

    const wordInfo = getWordAtPosition(text, clickPosition);
    if (!wordInfo) {
        hideAlternativesPopup();
        return;
    }

    currentWord = wordInfo.word;
    currentWordStart = wordInfo.start;
    currentWordEnd = wordInfo.end;

    // Show loading popup immediately
    showAlternativesPopup(event.clientX, event.clientY, 'loading');

    try {
        // Get current language (target language)
        const language = targetLang.value;

        const alternatives = await fetchAlternatives(text, wordInfo.word, language);

        if (alternatives.length === 0) {
            showAlternativesPopup(event.clientX, event.clientY, 'empty');
            setTimeout(hideAlternativesPopup, 2000);
        } else {
            showAlternativesPopup(event.clientX, event.clientY, 'loaded', alternatives);
        }
    } catch (error) {
        logError(ERROR_IDS.ALTERNATIVES_FETCH_ERROR, 'Failed to fetch alternatives', {
            error: error.message,
            word: wordInfo.word
        });
        showAlternativesPopup(event.clientX, event.clientY, 'error');
        setTimeout(hideAlternativesPopup, 2000);
    }
}

async function fetchAlternatives(text, word, language) {
    const temperature = parseFloat(temperatureSlider.value);

    const response = await fetch(`${API_BASE_URL}/api/alternatives`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text, word, language, temperature })
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    return data.alternatives || [];
}

function showAlternativesPopup(x, y, state, alternatives = []) {
    hideAlternativesPopup(); // Close any existing popup

    const popup = document.createElement('div');
    popup.id = 'alternativesPopup';
    popup.className = 'alternatives-popup';

    // Position popup near click, with boundary checks
    let left = x + 10;
    let top = y + 10;
    const popupWidth = 250;
    const popupHeight = 200;

    if (left + popupWidth > window.innerWidth) {
        left = x - popupWidth - 10;
    }
    if (top + popupHeight > window.innerHeight) {
        top = y - popupHeight - 10;
    }

    popup.style.left = `${left}px`;
    popup.style.top = `${top}px`;

    // Set content based on state
    if (state === 'loading') {
        popup.innerHTML = '<div class="alternatives-loading">Loading alternatives...</div>';
    } else if (state === 'loaded') {
        const header = `<div class="alternatives-header">Alternatives for "<span class="word">${currentWord}</span>"</div>`;
        const items = alternatives.map(alt => `
            <button class="alternative-item" data-word="${alt}">
                <span class="alternative-word">${alt}</span>
            </button>
        `).join('');
        popup.innerHTML = header + `<div class="alternatives-list">${items}</div>`;

        // Add click handlers for each alternative
        popup.querySelectorAll('.alternative-item').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                replaceWord(btn.dataset.word);
            });
        });
    } else if (state === 'empty') {
        popup.innerHTML = '<div class="alternatives-empty">No alternatives found</div>';
    } else if (state === 'error') {
        popup.innerHTML = '<div class="alternatives-error">Error loading alternatives</div>';
    }

    document.body.appendChild(popup);
    alternativesPopup = popup;

    // Close on click outside or ESC
    setTimeout(() => {
        document.addEventListener('click', handleDocumentClick);
    }, 100);
}

function hideAlternativesPopup() {
    if (alternativesPopup) {
        alternativesPopup.remove();
        alternativesPopup = null;
    }
    document.removeEventListener('click', handleDocumentClick);
}

function handleDocumentClick(event) {
    if (alternativesPopup && !alternativesPopup.contains(event.target)) {
        hideAlternativesPopup();
    }
}

function handleEscKey(event) {
    if (event.key === 'Escape' && alternativesPopup) {
        hideAlternativesPopup();
    }
}

function replaceWord(alternative) {
    const text = targetText.value;
    const before = text.substring(0, currentWordStart);
    const after = text.substring(currentWordEnd);

    targetText.value = before + alternative + after;
    hideAlternativesPopup();

    showStatus(`Replaced "${currentWord}" with "${alternative}"`, 'success');
    setTimeout(hideStatus, 2000);
}

// Initialize
copyBtn.disabled = true;
loadCurrentModel();
setMode(MODE_TRANSLATE);

// Add event listeners for alternatives
targetText.addEventListener('click', handleTargetTextClick);
document.addEventListener('keydown', handleEscKey);

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
