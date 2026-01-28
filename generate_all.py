import argparse
import os
import re
import subprocess
import sys

LOGS_DIR = "logs"


def find_signal_pairs():
    """Descobre todos os nomes de sinal que possuem par ADS1015 + ADS1115 em logs/."""
    files = os.listdir(LOGS_DIR)
    names = set()
    for f in files:
        m = re.match(r"(.+)_ads1[01]15\.log$", f, re.IGNORECASE)
        if m:
            names.add(m.group(1))

    # Manter apenas os que possuem ambos os arquivos
    pairs = sorted(
        n for n in names
        if os.path.isfile(os.path.join(LOGS_DIR, f"{n}_ads1015.log"))
        and os.path.isfile(os.path.join(LOGS_DIR, f"{n}_ads1115.log"))
    )
    return pairs


def main():
    parser = argparse.ArgumentParser(
        description="Gera HTMLs comparativos para todos os sinais em logs/"
    )
    parser.add_argument(
        "--i_primary",
        type=float,
        required=True,
        help="Corrente nominal primária do TC em Ampères",
    )
    args = parser.parse_args()

    pairs = find_signal_pairs()
    if not pairs:
        print("Nenhum par de sinais encontrado em logs/")
        sys.exit(1)

    print(f"Encontrados {len(pairs)} pares de sinais.")

    failed = []
    for i, name in enumerate(pairs, 1):
        print(f"[{i}/{len(pairs)}] {name} ... ", end="", flush=True)
        result = subprocess.run(
            [
                sys.executable,
                "plot_comparison.py",
                name,
                "--i_primary",
                str(args.i_primary),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("OK")
        else:
            print("ERRO")
            print(f"  {result.stderr.strip()}")
            failed.append(name)

    print(f"\nConcluído: {len(pairs) - len(failed)}/{len(pairs)} gerados.")
    if failed:
        print("Falhas:")
        for name in failed:
            print(f"  - {name}")
        sys.exit(1)


if __name__ == "__main__":
    main()
