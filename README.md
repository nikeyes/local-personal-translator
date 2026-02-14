# Personal Translator

Local ES↔EN translator using [TranslateGemma 12B](https://huggingface.co/mlx-community/translategemma-12b-it-8bit) with MLX on Apple Silicon.

## Setup

```bash
uv sync
```

The first run downloads the model. Subsequent runs start in seconds.

## Model Selection

Choose between two quantization levels:

- **8-bit** (default): ~12.5 GB, highest quality
- **4-bit**: ~6.6 GB, faster inference, minimal quality loss

```bash
# Use 8-bit model (default)
uv run python main.py --serve

# Use 4-bit model (faster, less memory)
uv run python main.py --serve --4bit
```

## Usage

### Web Interface (Recommended)

```bash
uv run python main.py --serve [--4bit]
```

Open `http://127.0.0.1:8785` in your browser for a DeepL-style interface:
- Two-panel layout (input | output)
- Language selectors (ES/EN)
- **Model selector** (switch between 8-bit/4-bit on the fly)
- Auto-translation as you type
- Copy button for translated text
- Translation time display (server + total roundtrip)

**Note**: You can change models directly from the web interface. The initial model can be set with `--4bit` or `--8bit` flags.

### API Server

The server also provides a REST API. Translate with curl:

```bash
curl -s -X POST 'http://127.0.0.1:8785?src=es&tgt=en' -d 'Hola mundo'
```

### Keyboard shortcuts (macOS)

Install Automator Quick Actions for CMD+SHIFT+E (ES→EN) and CMD+SHIFT+I (EN→ES):

```bash
bash install_shortcuts.sh
```

Flow: select text → CMD+SHIFT+E → web interface opens with translation.

Features:
- Auto-starts server if not running
- Supports long texts via base64 encoding
- Shows translation time
- Visual feedback (translating/success/error states)
- Copy button and CMD+C support
- Clean URL after loading

To remove:

```bash
bash uninstall_shortcuts.sh
```

### Interactive mode

```bash
uv run python main.py [--4bit]
```

Commands: `/swap` switches direction, `/q` exits.

## Performance

Translation timing is displayed in:
- Web interface: server processing time + total roundtrip time
- Interactive mode: printed after each translation
- HTTP API: `X-Translation-Time` response header (seconds)

On M3 Pro with 36GB RAM:
- **8-bit model**: ~2-4s per translation, higher quality
- **4-bit model**: ~1-3s per translation, 50% less memory
