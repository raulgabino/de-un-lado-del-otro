#!/usr/bin/env python3
"""
Script maestro: ejecuta todo el pipeline en orden.
Uso: python3 src/run_pipeline.py
"""

import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    "01_preparar_censo.py",
    "02_construir_indicadores.py",
    "03_fronteras_desigualdad.py",
    "04_capa_denue.py",
    "05_cruce_brt.py",
    "06_mapa_interactivo.py",
]

def main():
    src_dir = Path(__file__).resolve().parent

    for script in SCRIPTS:
        script_path = src_dir / script
        print(f"\n{'='*60}")
        print(f"  Ejecutando: {script}")
        print(f"{'='*60}")

        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(src_dir.parent),
        )

        if result.returncode != 0:
            print(f"\n  ✗ {script} falló con código {result.returncode}")
            sys.exit(result.returncode)

    print(f"\n{'='*60}")
    print("  PIPELINE COMPLETADO")
    print(f"{'='*60}")
    print("\n  Archivos generados en output/:")

    output_dir = src_dir.parent / "output"
    for f in sorted(output_dir.iterdir()):
        size = f.stat().st_size
        if size > 1_000_000:
            print(f"    {f.name} ({size/1024/1024:.1f} MB)")
        else:
            print(f"    {f.name} ({size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
