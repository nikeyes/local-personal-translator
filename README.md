# Personal Translator

Local ES↔EN translator using [TranslateGemma 12B 8-bit](https://huggingface.co/mlx-community/translategemma-12b-it-8bit) with MLX on Apple Silicon.

## Setup

```bash
uv sync
```

The first run downloads the model (~12.5 GB). Subsequent runs start in seconds.

## Usage

### Server mode

```bash
uv run python main.py --serve
```

Listens on `http://127.0.0.1:8785`. Translate with curl:

```bash
curl -s -X POST 'http://127.0.0.1:8785?src=es&tgt=en' -d 'Hola mundo'
```

### Keyboard shortcuts (macOS)

Install Automator Quick Actions and assign CMD+SHIFT+E (ES→EN) and CMD+SHIFT+I (EN→ES):

```bash
bash install_shortcuts.sh
```

Flow: select text → CMD+SHIFT+E → CMD+V to paste.

To remove:

```bash
bash uninstall_shortcuts.sh
```

### Interactive mode

```bash
uv run python main.py
```

Commands: `/swap` switches direction, `/q` exits.
