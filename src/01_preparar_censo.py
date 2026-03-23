#!/usr/bin/env python3
"""
Paso 01: Preparación de datos censales.
Carga CSV del Censo 2020, filtra ZM Tampico-Madero-Altamira,
ejecuta validaciones (Gates 1-5), limpia y guarda.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils


def ejecutar_validaciones(df: pd.DataFrame, df_zm: pd.DataFrame):
    """Ejecuta validaciones sobre los datos censales."""

    print("\n  Ejecutando validaciones...")

    # 1: CSV es de Tamaulipas
    entidades = df["ENTIDAD"].unique()
    assert utils.ENTIDAD_INT in entidades, \
        f"Archivo NO es de Tamaulipas (28). Entidades: {entidades}"
    print("  ✓ Entidad correcta: Tamaulipas (28)")

    # 2: Los 3 municipios presentes en ZM
    muns_encontrados = set(df_zm["MUN"].unique())
    faltantes = set(utils.MUNICIPIOS_INT.keys()) - muns_encontrados
    assert len(faltantes) == 0, \
        f"Faltan municipios: {faltantes}. Encontrados: {sorted(muns_encontrados)}"
    print("  ✓ Los 3 municipios presentes")

    # 3: Claves coinciden con nombres
    for cve, nombre_esperado in utils.MUNICIPIOS_INT.items():
        mask = df_zm["MUN"] == cve
        if mask.any() and "NOM_MUN" in df_zm.columns:
            nombre_real = df_zm.loc[mask, "NOM_MUN"].iloc[0]
            assert nombre_esperado.lower() in str(nombre_real).lower(), \
                f"Clave {cve} = '{nombre_real}', esperado '{nombre_esperado}'"
            print(f"  ✓ Clave {cve} = {nombre_real}")

    # 4: Variables requeridas existen
    faltantes_vars = [v for v in utils.VARS_REQUERIDAS if v not in df.columns]
    assert len(faltantes_vars) == 0, \
        f"Variables faltantes: {faltantes_vars}"
    print(f"  ✓ {len(utils.VARS_REQUERIDAS)} variables requeridas presentes")

    # 5: Número de AGEBs razonable
    n_agebs = len(df_zm)
    assert 100 < n_agebs < 1000, \
        f"Se encontraron {n_agebs} AGEBs, fuera del rango esperado (100-1000)"
    print(f"  ✓ {n_agebs} AGEBs en la zona metropolitana")

    for cve, nombre in utils.MUNICIPIOS_INT.items():
        n = len(df_zm[df_zm["MUN"] == cve])
        print(f"    - {nombre}: {n} AGEBs")


def main():
    print("=" * 60)
    print("PASO 01: Preparación de datos censales")
    print("=" * 60)

    # 1. Cargar CSV del censo AGEB
    csv_path = utils.CENSO_CSV
    print(f"\n  Cargando: {csv_path.name}")
    df = utils.cargar_csv_censo(csv_path)
    print(f"  Registros totales: {len(df):,}")

    # 2. Filtrar ZM Tampico
    print("\n  Filtrando zona metropolitana Tampico-Madero-Altamira...")
    df_zm = utils.filtrar_zm_tampico(df)
    print(f"  Registros a nivel AGEB en ZM: {len(df_zm):,}")

    # 3. Ejecutar validaciones
    ejecutar_validaciones(df, df_zm)

    # 4. Filtrar POBTOT >= 150
    df_zm["POBTOT"] = pd.to_numeric(df_zm["POBTOT"], errors="coerce")
    n_antes = len(df_zm)
    df_zm = df_zm[df_zm["POBTOT"] >= 150].copy()
    print(f"\n  Filtro POBTOT >= 150: {n_antes} → {len(df_zm)} AGEBs")

    # 5. Excluir AGEBs con >4 indicadores faltantes
    all_vars = [v[1] for v in utils.INDICADORES_UP + utils.INDICADORES_DOWN]
    # Incluir denominadores
    all_vars += [v[2] for v in utils.INDICADORES_UP + utils.INDICADORES_DOWN if v[2] is not None]
    all_vars = list(set(all_vars))  # Eliminar duplicados
    cols_presentes = [c for c in all_vars if c in df_zm.columns]

    n_faltantes = df_zm[cols_presentes].isna().sum(axis=1)
    n_antes = len(df_zm)
    df_zm = df_zm[n_faltantes <= 4].copy()
    print(f"  Filtro max 4 indicadores faltantes: {n_antes} → {len(df_zm)} AGEBs")

    # 6. Construir CVEGEO
    df_zm["CVEGEO"] = utils.construir_cvegeo(df_zm)
    print(f"  CVEGEO construido (ejemplo: {df_zm['CVEGEO'].iloc[0]})")

    # 7. Guardar
    utils.asegurar_output_dir()
    output_path = utils.OUTPUT_DIR / "censo_ageb_limpio.csv"
    df_zm.to_csv(output_path, index=False, encoding="utf-8")
    print(f"\n  ✓ Guardado: {output_path}")
    print(f"    {len(df_zm)} AGEBs, {len(df_zm.columns)} columnas")

    # Resumen de NaN en variables clave
    print("\n  NaN en variables clave:")
    for var in utils.VARS_REQUERIDAS:
        if var in df_zm.columns:
            n_na = df_zm[var].isna().sum()
            if n_na > 0:
                pct = n_na / len(df_zm) * 100
                print(f"    {var}: {n_na} ({pct:.1f}%)")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, FileNotFoundError) as e:
        print(f"\n  ✗ {e}")
        sys.exit(1)
