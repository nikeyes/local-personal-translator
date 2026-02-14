#!/usr/bin/env python3
"""Benchmark translation performance between 8-bit and 4-bit models"""

import time

import mlx.core as mx
from mlx_lm import generate

from main import build_prompt, load_model, sampler, translate

TEST_TEXTS = [
    "Hola mundo",
    "Este es un texto más largo para probar el rendimiento del sistema de traducción automática.",
    "La inteligencia artificial está transformando la forma en que trabajamos y nos comunicamos. Los modelos de lenguaje grandes como este pueden procesar y traducir texto de manera eficiente, manteniendo el significado y el contexto original.",
]


def benchmark_model(model_name: str):
    """Benchmark a specific model"""
    print(f"\n{'='*60}")
    print(f"Benchmarking {model_name} model")
    print(f"{'='*60}\n")

    model, tokenizer = load_model(model_name)

    results = []
    for i, text in enumerate(TEST_TEXTS, 1):
        chars = len(text)
        print(f"Test {i} ({chars} chars): {text[:50]}...")

        # Run translation 3 times to get average
        times = []
        for run in range(3):
            result, elapsed = translate(model, tokenizer, "es", "en", text)
            times.append(elapsed)
            if run == 0:
                # Show first result only
                print(f"  Result: {result[:80]}...")

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"  Times: avg={avg_time:.3f}s, min={min_time:.3f}s, max={max_time:.3f}s")
        print(f"  Speed: {chars/avg_time:.1f} chars/sec\n")

        results.append({
            "chars": chars,
            "avg_time": avg_time,
            "min_time": min_time,
            "max_time": max_time,
        })

    return results


def to_mb(bytes_val):
    return bytes_val / (1024 * 1024)


def benchmark_kv_cache(model_name: str):
    """Compare peak GPU memory with and without max_kv_size"""
    print(f"\n{'='*60}")
    print(f"KV Cache Memory Benchmark ({model_name})")
    print(f"{'='*60}\n")

    model, tokenizer = load_model(model_name)

    results = []
    for i, text in enumerate(TEST_TEXTS, 1):
        chars = len(text)
        prompt = build_prompt(tokenizer, "es", "en", text)
        print(f"Test {i} ({chars} chars): {text[:50]}...")

        # Without max_kv_size (unlimited)
        mx.reset_peak_memory()
        mem_before = mx.get_active_memory()
        start = time.perf_counter()
        generate(model, tokenizer, prompt=prompt, max_tokens=512, sampler=sampler)
        elapsed_unlimited = time.perf_counter() - start
        peak_unlimited = mx.get_peak_memory() - mem_before

        # With max_kv_size=4096
        mx.reset_peak_memory()
        mem_before = mx.get_active_memory()
        start = time.perf_counter()
        generate(model, tokenizer, prompt=prompt, max_tokens=512, sampler=sampler, max_kv_size=4096)
        elapsed_capped = time.perf_counter() - start
        peak_capped = mx.get_peak_memory() - mem_before

        saving = peak_unlimited - peak_capped
        saving_pct = (saving / peak_unlimited * 100) if peak_unlimited > 0 else 0

        print(f"  No limit:       {to_mb(peak_unlimited):>8.1f} MB  ({elapsed_unlimited:.3f}s)")
        print(f"  max_kv=4096:    {to_mb(peak_capped):>8.1f} MB  ({elapsed_capped:.3f}s)")
        print(f"  Memory saved:   {to_mb(saving):>8.1f} MB  ({saving_pct:.1f}%)\n")

        results.append({
            "chars": chars,
            "peak_unlimited_mb": to_mb(peak_unlimited),
            "peak_capped_mb": to_mb(peak_capped),
            "saving_mb": to_mb(saving),
            "saving_pct": saving_pct,
            "time_unlimited": elapsed_unlimited,
            "time_capped": elapsed_capped,
        })

    return results


def main():
    print("\nTranslateGemma Performance Benchmark")
    print("Testing ES->EN translation\n")

    # Benchmark both models
    results_8bit = benchmark_model("8bit")
    results_4bit = benchmark_model("4bit")

    # Summary comparison
    print(f"\n{'='*60}")
    print("SPEED COMPARISON")
    print(f"{'='*60}\n")

    print(f"{'Test':<10} {'Chars':<8} {'8-bit (s)':<12} {'4-bit (s)':<12} {'Speedup':<10}")
    print("-" * 60)

    for i, (r8, r4) in enumerate(zip(results_8bit, results_4bit), 1):
        speedup = r8["avg_time"] / r4["avg_time"]
        print(
            f"Test {i:<5} {r8['chars']:<8} "
            f"{r8['avg_time']:<12.3f} {r4['avg_time']:<12.3f} "
            f"{speedup:.2f}x"
        )

    # Overall averages
    avg_8bit = sum(r["avg_time"] for r in results_8bit) / len(results_8bit)
    avg_4bit = sum(r["avg_time"] for r in results_4bit) / len(results_4bit)
    overall_speedup = avg_8bit / avg_4bit

    print("-" * 60)
    print(
        f"{'Average':<10} {'':<8} "
        f"{avg_8bit:<12.3f} {avg_4bit:<12.3f} "
        f"{overall_speedup:.2f}x"
    )

    # KV cache memory benchmark
    kv_8bit = benchmark_kv_cache("8bit")
    kv_4bit = benchmark_kv_cache("4bit")

    print(f"\n{'='*60}")
    print("KV CACHE MEMORY COMPARISON")
    print(f"{'='*60}\n")

    print(f"{'Test':<6} {'Chars':<7} {'8bit no limit':<15} {'8bit kv=4096':<15} "
          f"{'4bit no limit':<15} {'4bit kv=4096':<15} {'8bit saved':<12} {'4bit saved':<12}")
    print("-" * 97)

    for i, (r8, r4) in enumerate(zip(kv_8bit, kv_4bit), 1):
        print(
            f"Test {i} {r8['chars']:<7} "
            f"{r8['peak_unlimited_mb']:<15.1f} {r8['peak_capped_mb']:<15.1f} "
            f"{r4['peak_unlimited_mb']:<15.1f} {r4['peak_capped_mb']:<15.1f} "
            f"{r8['saving_pct']:<12.1f}% {r4['saving_pct']:<12.1f}%"
        )

    print()


if __name__ == "__main__":
    main()
