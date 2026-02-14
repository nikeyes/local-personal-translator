.PHONY: help install serve serve-4bit interactive

help:
	@echo "Personal Translator - Make commands"
	@echo ""
	@echo "  make install       Install dependencies"
	@echo "  make serve         Start web server (8-bit model)"
	@echo "  make serve-4bit    Start web server (4-bit model)"
	@echo "  make interactive   Start interactive mode"

install:
	uv sync

serve:
	uv run python main.py --serve

serve-4bit:
	uv run python main.py --serve --4bit

interactive:
	uv run python main.py
