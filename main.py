import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler

MODEL = "mlx-community/translategemma-12b-it-8bit"
PORT = 8785
STATIC_DIR = Path(__file__).parent

sampler = make_sampler(temp=0.0)


def build_prompt(tokenizer, src: str, tgt: str, text: str) -> str:
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "source_lang_code": src,
                    "target_lang_code": tgt,
                    "text": text,
                }
            ],
        }
    ]
    return tokenizer.apply_chat_template(messages, add_generation_prompt=True)


def translate(model, tokenizer, src: str, tgt: str, text: str) -> str:
    prompt = build_prompt(tokenizer, src, tgt, text)
    return generate(model, tokenizer, prompt=prompt, max_tokens=512, sampler=sampler)


def load_model():
    print("Loading model...", file=sys.stderr)
    model, tokenizer = load(MODEL)
    end_of_turn_id = tokenizer.encode("<end_of_turn>", add_special_tokens=False)[-1]
    tokenizer._eos_token_ids.add(end_of_turn_id)  # MLX community model misses this stop token
    print("Model ready.", file=sys.stderr)
    return model, tokenizer


def serve(model, tokenizer):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # Serve static files
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/" or path == "/index.html":
                file_path = STATIC_DIR / "index.html"
            elif path == "/styles.css":
                file_path = STATIC_DIR / "styles.css"
            elif path == "/app.js":
                file_path = STATIC_DIR / "app.js"
            else:
                self.send_response(404)
                self.end_headers()
                return

            try:
                content = file_path.read_bytes()
                self.send_response(200)
                if file_path.suffix == ".html":
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                elif file_path.suffix == ".css":
                    self.send_header("Content-Type", "text/css; charset=utf-8")
                elif file_path.suffix == ".js":
                    self.send_header("Content-Type", "application/javascript; charset=utf-8")
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            # Translation API
            if "src" not in params or "tgt" not in params:
                self.send_response(400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"Missing src/tgt query params. Use: POST /?src=es&tgt=en")
                return
            src = params["src"][0]
            tgt = params["tgt"][0]
            text = self.rfile.read(int(self.headers["Content-Length"])).decode()
            print(f"[{src}->{tgt}] {text}", file=sys.stderr)
            result = translate(model, tokenizer, src, tgt, text)
            print(f"       -> {result}", file=sys.stderr)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(result.encode())

        def do_OPTIONS(self):
            # Handle CORS preflight
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def log_message(self, _format, *_args):
            pass

    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Serving on http://127.0.0.1:{PORT}", file=sys.stderr)
    server.serve_forever()


def repl(model, tokenizer):
    print("Type text to translate (es->en). /swap to switch. /q to quit.\n", file=sys.stderr)
    src, tgt = "es", "en"

    while True:
        try:
            line = input(f"[{src}->{tgt}] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line.lower() in ("/q", "/quit"):
            break
        if line.lower() == "/swap":
            src, tgt = tgt, src
            continue

        print(translate(model, tokenizer, src, tgt, line))
        print()


def main():
    model, tokenizer = load_model()

    if "--serve" in sys.argv:
        serve(model, tokenizer)
    else:
        repl(model, tokenizer)


if __name__ == "__main__":
    main()
