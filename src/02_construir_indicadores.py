#!/usr/bin/env python3
"""
Paso 02: Construcción de indicadores socioeconómicos por AGEB.
Calcula tasas, asigna ventiles, y genera puntaje compuesto.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils


def calcular_tasas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula las tasas para todos los indicadores UP y DOWN.
    Retorna DataFrame con columnas de tasas.
    """
    result = df[["CVEGEO"]].copy()

    for nombre, numerador, denominador in utils.INDICADORES_UP + utils.INDICADORES_DOWN:
        if denominador is None:
            # Variable directa (GRAPROES, PRO_OCUP_C)
            result[nombre] = pd.to_numeric(df[numerador], errors="coerce")
        else:
            num = pd.to_numeric(df[numerador], errors="coerce")
            den = pd.to_numeric(df[denominador], errors="coerce")
            # Evitar división por cero
            result[nombre] = np.where(den > 0, num / den, np.nan)

    return result


def calcular_ventiles(tasas: pd.DataFrame) -> pd.DataFrame:
    """
    Asigna ventiles (1-20) a cada indicador.
    UP: ventil 20 = mejor
    DOWN: invertir con 21 - ventil para que 20 = menos carenciado
    """
    result = tasas[["CVEGEO"]].copy()

    for nombre, _, _ in utils.INDICADORES_UP:
        col_ventil = f"V_{nombre}"
        result[col_ventil] = utils.asignar_ventiles(tasas[nombre], invertir=False)

    for nombre, _, _ in utils.INDICADORES_DOWN:
        col_ventil = f"V_{nombre}"
        result[col_ventil] = utils.asignar_ventiles(tasas[nombre], invertir=True)

    return result


def calcular_puntaje_compuesto(ventiles: pd.DataFrame) -> pd.Series:
    """
    Calcula el puntaje compuesto como promedio de todos los ventiles.
    Rango: 1 (más carenciado) a 20 (más privilegiado).
    """
    cols_ventil = [c for c in ventiles.columns if c.startswith("V_")]
    return ventiles[cols_ventil].mean(axis=1)


def main():
    print("=" * 60)
    print("PASO 02: Construcción de indicadores socioeconómicos")
    print("=" * 60)

    # 1. Cargar censo limpio
    input_path = utils.OUTPUT_DIR / "censo_ageb_limpio.csv"
    print(f"\n  Cargando: {input_path.name}")
    df = pd.read_csv(input_path, dtype={"CVEGEO": str})
    print(f"  {len(df)} AGEBs")

    # 2. Calcular tasas
    print("\n  Calculando tasas...")
    tasas = calcular_tasas(df)

    # Resumen de tasas
    print("\n  Estadísticas de tasas:")
    for nombre, _, _ in utils.INDICADORES_UP + utils.INDICADORES_DOWN:
        serie = tasas[nombre]
        n_valid = serie.notna().sum()
        if n_valid > 0:
            print(f"    {nombre}: media={serie.mean():.3f}, "
                  f"min={serie.min():.3f}, max={serie.max():.3f}, "
                  f"n_valid={n_valid}")

    # 3. Calcular ventiles
    print("\n  Asignando ventiles (1-20)...")
    ventiles = calcular_ventiles(tasas)

    # 4. Calcular puntaje compuesto
    print("  Calculando puntaje compuesto...")
    puntaje = calcular_puntaje_compuesto(ventiles)

    # 5. Ensamblar resultado
    resultado = tasas.copy()
    # Agregar columnas de ventiles
    cols_ventil = [c for c in ventiles.columns if c.startswith("V_")]
    for col in cols_ventil:
        resultado[col] = ventiles[col]

    resultado["puntaje_compuesto"] = puntaje

    # Agregar datos de contexto del censo
    cols_contexto = ["POBTOT", "NOM_MUN", "MUN"]
    for col in cols_contexto:
        if col in df.columns:
            resultado[col] = df[col].values

    # Resumen del puntaje
    print(f"\n  Puntaje compuesto:")
    print(f"    Rango: {puntaje.min():.1f} - {puntaje.max():.1f}")
    print(f"    Media: {puntaje.mean():.1f}")
    print(f"    Mediana: {puntaje.median():.1f}")

    # Distribución por quintiles
    print("\n  Distribución por rangos de puntaje:")
    bins = [(1, 4, "Muy alta marginación"),
            (4, 8, "Alta marginación"),
            (8, 12, "Marginación media"),
            (12, 16, "Bajo marginación"),
            (16, 20.1, "Muy bajo marginación")]
    for low, high, label in bins:
        n = ((puntaje >= low) & (puntaje < high)).sum()
        pct = n / len(puntaje) * 100
        print(f"    {label} ({low:.0f}-{high:.0f}): {n} AGEBs ({pct:.1f}%)")

    # Por municipio
    if "NOM_MUN" in resultado.columns:
        print("\n  Puntaje promedio por municipio:")
        for mun in resultado["NOM_MUN"].dropna().unique():
            mask = resultado["NOM_MUN"] == mun
            media = resultado.loc[mask, "puntaje_compuesto"].mean()
            print(f"    {mun}: {media:.1f}")

    # 6. Guardar
    utils.asegurar_output_dir()
    output_path = utils.OUTPUT_DIR / "indicadores_por_ageb.csv"
    resultado.to_csv(output_path, index=False, encoding="utf-8")
    print(f"\n  ✓ Guardado: {output_path}")
    print(f"    {len(resultado)} AGEBs, {len(resultado.columns)} columnas")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as e:
        print(f"\n  ✗ {e}")
        print("  → Ejecute primero 01_preparar_censo.py")
        sys.exit(1)
