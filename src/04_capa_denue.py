#!/usr/bin/env python3
"""
Paso 04: Análisis de la capa DENUE (empleo y servicios por AGEB).
Carga DENUE 05/2025, clasifica establecimientos, y genera métricas por AGEB.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils


# Clasificación SCIAN (2 primeros dígitos del código de actividad)
SECTORES = {
    "salud": ["62"],
    "educacion": ["61"],
    "comercio": ["46"],
    "manufactura": ["31", "32", "33"],
    "gobierno": ["93"],
}


def cargar_denue() -> pd.DataFrame:
    """Carga DENUE de Tamaulipas. Encoding latin-1, delimiter coma."""
    path = utils.DENUE_CSV
    df = pd.read_csv(path, encoding="latin-1", low_memory=False)
    return df


def clasificar_sector(codigo_act_series: pd.Series) -> pd.Series:
    """Clasifica establecimientos por código SCIAN (vectorizado).
    codigo_act es int de 6 dígitos, se pasa como str Series."""
    s = codigo_act_series.astype(str)
    result = pd.Series("otros", index=s.index)
    for sector, prefijos in SECTORES.items():
        for pref in prefijos:
            result[s.str.startswith(pref)] = sector
    return result


def main():
    print("=" * 60)
    print("PASO 04: Capa DENUE — empleo y servicios por AGEB")
    print("=" * 60)

    # 1. Cargar DENUE
    print(f"\n  Cargando DENUE...")
    df = cargar_denue()
    print(f"  {len(df):,} establecimientos totales en Tamaulipas")

    # 2. Filtrar a ZM Tampico (cve_mun es int)
    df_zm = df[df["cve_mun"].isin(list(utils.MUNICIPIOS_INT.keys()))].copy()
    print(f"  {len(df_zm):,} establecimientos en ZM Tampico")
    for cve, nom in utils.MUNICIPIOS_INT.items():
        n = (df_zm["cve_mun"] == cve).sum()
        print(f"    {nom}: {n:,}")

    # 3. Clasificar sector (codigo_act es int de 6 dígitos)
    print("\n  Clasificando sectores SCIAN...")
    df_zm["sector"] = clasificar_sector(df_zm["codigo_act"].astype(str))
    for sector in ["salud", "educacion", "comercio", "manufactura", "gobierno", "otros"]:
        n = (df_zm["sector"] == sector).sum()
        print(f"    {sector}: {n:,}")

    # 4. Parsear personal ocupado
    df_zm["empleados_est"] = utils.parsear_per_ocu(df_zm["per_ocu"])
    print(f"\n  Empleados estimados (total ZM): {df_zm['empleados_est'].sum():,.0f}")

    # 5. Construir CVEGEO para join directo (sin spatial join)
    df_zm["CVEGEO"] = utils.construir_cvegeo_denue(df_zm)

    # 6. Métricas por AGEB
    print("\n  Calculando métricas por AGEB...")
    resumen_list = []

    for cvegeo, grupo in df_zm.groupby("CVEGEO"):
        fila = {"CVEGEO": cvegeo}
        for sector in ["salud", "educacion", "comercio", "manufactura", "gobierno"]:
            fila[f"n_{sector}"] = (grupo["sector"] == sector).sum()
        fila["n_total"] = len(grupo)
        fila["empleos_grandes"] = (grupo["empleados_est"] >= 51).sum()
        fila["empleo_total_est"] = grupo["empleados_est"].sum()
        resumen_list.append(fila)

    df_resumen = pd.DataFrame(resumen_list)

    # Índice de atracción de viajes (ponderado)
    df_resumen["indice_atraccion"] = (
        df_resumen["n_salud"] * 3
        + df_resumen["n_educacion"] * 3
        + df_resumen["n_gobierno"] * 2
        + df_resumen["n_comercio"] * 1
        + df_resumen["n_manufactura"] * 1
    )
    max_atr = df_resumen["indice_atraccion"].max()
    if max_atr > 0:
        df_resumen["indice_atraccion_norm"] = (
            df_resumen["indice_atraccion"] / max_atr * 100
        ).round(1)

    # 7. Guardar resumen
    utils.asegurar_output_dir()
    resumen_path = utils.OUTPUT_DIR / "denue_ageb_resumen.csv"
    df_resumen.to_csv(resumen_path, index=False, encoding="utf-8")
    print(f"\n  ✓ Resumen: {resumen_path} ({len(df_resumen)} AGEBs con establecimientos)")

    # 8. Guardar puntos DENUE para el mapa (solo sectores clave)
    df_puntos = df_zm[df_zm["sector"] != "otros"][
        ["CVEGEO", "sector", "latitud", "longitud", "empleados_est", "nom_estab", "nombre_act"]
    ].copy()
    puntos_path = utils.OUTPUT_DIR / "denue_puntos.csv"
    df_puntos.to_csv(puntos_path, index=False, encoding="utf-8")
    print(f"  ✓ Puntos DENUE: {puntos_path} ({len(df_puntos)} establecimientos clave)")

    # Resumen
    print("\n  Top 10 AGEBs por índice de atracción:")
    top10 = df_resumen.nlargest(10, "indice_atraccion")
    for _, row in top10.iterrows():
        print(f"    {row['CVEGEO']}: atracción={row['indice_atraccion']:.0f}, "
              f"total={row['n_total']}, empleo_est={row['empleo_total_est']:,.0f}")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, FileNotFoundError) as e:
        print(f"\n  ✗ {e}")
        sys.exit(1)
