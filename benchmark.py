#!/usr/bin/env python3
"""Benchmark translation performance between 8-bit and 4-bit models"""

import time
from main import load_model, translate

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


def main():
    print("\n🚀 TranslateGemma Performance Benchmark")
    print("Testing ES→EN translation\n")

    # Benchmark both models
    results_8bit = benchmark_model("8bit")
    results_4bit = benchmark_model("4bit")

    # Summary comparison
    print(f"\n{'='*60}")
    print("SUMMARY COMPARISON")
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
    print()


if __name__ == "__main__":
    main()
