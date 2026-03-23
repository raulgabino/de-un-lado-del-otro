#!/usr/bin/env python3
"""
Paso 05: Cruce con trazo del corredor BRT.
Modo A: Analiza impacto del corredor existente.
Modo B: Recomienda zonas prioritarias para un corredor.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils


def buscar_trazo_brt() -> Path | None:
    """Busca archivo de trazo BRT en datos/trazo_brt/."""
    brt_dir = utils.DATOS_DIR / "trazo_brt"
    if not brt_dir.exists():
        return None

    for ext in ["*.geojson", "*.shp", "*.kml", "*.gpkg"]:
        archivos = list(brt_dir.glob(ext))
        if archivos:
            return archivos[0]

    return None


def modo_a_con_trazo(trazo_path: Path):
    """Analiza impacto del corredor BRT existente."""
    import geopandas as gpd

    print("\n  === MODO A: Análisis de corredor BRT existente ===")

    # Cargar trazo
    print(f"  Cargando trazo: {trazo_path.name}")
    gdf_brt = gpd.read_file(trazo_path)
    if gdf_brt.crs != utils.CRS_GEO:
        gdf_brt = gdf_brt.to_crs(utils.CRS_GEO)

    # Reproyectar a UTM para buffers en metros
    gdf_brt_proj = gdf_brt.to_crs(utils.CRS_PROJ)

    # Generar buffers
    buffer_400 = gdf_brt_proj.geometry.union_all().buffer(400)
    buffer_800 = gdf_brt_proj.geometry.union_all().buffer(800)

    # Cargar AGEBs con puntaje
    ageb_path = utils.OUTPUT_DIR / "agebs_con_puntaje.gpkg"
    gdf_agebs = gpd.read_file(ageb_path)
    gdf_agebs_proj = gdf_agebs.to_crs(utils.CRS_PROJ)

    # AGEBs en área de influencia
    mask_400 = gdf_agebs_proj.intersects(buffer_400)
    mask_800 = gdf_agebs_proj.intersects(buffer_800)

    agebs_400 = gdf_agebs[mask_400]
    agebs_800 = gdf_agebs[mask_800]

    print(f"\n  AGEBs en buffer 400m: {len(agebs_400)}")
    print(f"  AGEBs en buffer 800m: {len(agebs_800)}")

    # Métricas
    metricas = {}
    pobtot_col = "POBTOT" if "POBTOT" in agebs_800.columns else None

    if pobtot_col:
        pop_800 = pd.to_numeric(agebs_800[pobtot_col], errors="coerce").sum()
        metricas["poblacion_800m"] = pop_800
        print(f"\n  Población en buffer 800m: {pop_800:,.0f}")

        # Población carenciada (puntaje <= 5)
        mask_carencia = agebs_800["puntaje_compuesto"] <= 5
        pop_carencia = pd.to_numeric(
            agebs_800.loc[mask_carencia, pobtot_col], errors="coerce"
        ).sum()
        metricas["poblacion_carenciada_800m"] = pop_carencia
        print(f"  Población carenciada (puntaje ≤ 5): {pop_carencia:,.0f}")

    metricas["puntaje_medio_800m"] = agebs_800["puntaje_compuesto"].mean()
    print(f"  Puntaje medio en buffer 800m: {metricas['puntaje_medio_800m']:.1f}")

    # Fronteras cruzadas por el corredor
    fronteras_path = utils.OUTPUT_DIR / "fronteras_identificadas.gpkg"
    if fronteras_path.exists():
        gdf_fronteras = gpd.read_file(fronteras_path)
        gdf_fronteras_proj = gdf_fronteras.to_crs(utils.CRS_PROJ)
        fronteras_cruzadas = gdf_fronteras_proj[gdf_fronteras_proj.intersects(buffer_800)]
        metricas["fronteras_cruzadas_total"] = len(fronteras_cruzadas)
        for clasif in ["extrema", "alta", "moderada"]:
            n = (fronteras_cruzadas["clasificacion"] == clasif).sum()
            metricas[f"fronteras_{clasif}_cruzadas"] = n
            print(f"  Fronteras {clasif} cruzadas: {n}")

    # DENUE en área de influencia
    denue_path = utils.OUTPUT_DIR / "denue_ageb_resumen.csv"
    if denue_path.exists():
        df_denue = pd.read_csv(denue_path, dtype={"CVEGEO": str})
        cvegeos_800 = set(agebs_800["CVEGEO"].astype(str))
        denue_800 = df_denue[df_denue["CVEGEO"].isin(cvegeos_800)]
        if "empleo_total_est" in denue_800.columns:
            metricas["empleo_total_800m"] = denue_800["empleo_total_est"].sum()
            print(f"  Empleo estimado en buffer 800m: {metricas['empleo_total_800m']:,.0f}")

    # Índice de equidad: ratio carenciadas vs privilegiadas
    n_carenciadas = (agebs_800["puntaje_compuesto"] <= 8).sum()
    n_privilegiadas = (agebs_800["puntaje_compuesto"] >= 13).sum()
    if n_privilegiadas > 0:
        metricas["indice_equidad"] = round(n_carenciadas / n_privilegiadas, 2)
    else:
        metricas["indice_equidad"] = np.nan

    return metricas, agebs_800


def modo_b_sin_trazo():
    """Recomienda zonas prioritarias para un corredor BRT."""
    import geopandas as gpd

    print("\n  === MODO B: Recomendación de zonas prioritarias ===")

    # Cargar fronteras
    fronteras_path = utils.OUTPUT_DIR / "fronteras_identificadas.csv"
    df_fronteras = pd.read_csv(fronteras_path, dtype={"CVEGEO_A": str, "CVEGEO_B": str})

    # Cargar indicadores
    indicadores = pd.read_csv(
        utils.OUTPUT_DIR / "indicadores_por_ageb.csv",
        dtype={"CVEGEO": str}
    )

    # Cargar DENUE resumen
    denue_path = utils.OUTPUT_DIR / "denue_ageb_resumen.csv"
    df_denue = None
    if denue_path.exists():
        df_denue = pd.read_csv(denue_path, dtype={"CVEGEO": str})

    # Para cada frontera, calcular prioridad
    fronteras_extremas = df_fronteras[
        df_fronteras["clasificacion"].isin(["extrema", "alta"])
    ].copy()

    print(f"  Fronteras extremas/altas: {len(fronteras_extremas)}")

    # Score de prioridad: diferencia * (pob_A + pob_B) * atracción
    prioridad = []
    for _, row in fronteras_extremas.iterrows():
        pop_a = row.get("pobtot_A", 0) or 0
        pop_b = row.get("pobtot_B", 0) or 0
        diff = row["diferencia"]

        atraccion = 1
        if df_denue is not None:
            for cvegeo in [row["CVEGEO_A"], row["CVEGEO_B"]]:
                match = df_denue[df_denue["CVEGEO"] == cvegeo]
                if len(match) > 0 and "indice_atraccion" in match.columns:
                    atraccion += match["indice_atraccion"].iloc[0]

        score = diff * (pop_a + pop_b) * (1 + atraccion / 100)
        prioridad.append({
            "CVEGEO_A": row["CVEGEO_A"],
            "CVEGEO_B": row["CVEGEO_B"],
            "diferencia": diff,
            "clasificacion": row["clasificacion"],
            "poblacion_total": pop_a + pop_b,
            "prioridad_brt": round(score, 0),
        })

    df_prioridad = pd.DataFrame(prioridad)
    df_prioridad = df_prioridad.sort_values("prioridad_brt", ascending=False)

    print("\n  Top 15 zonas prioritarias para corredor BRT:")
    for i, (_, row) in enumerate(df_prioridad.head(15).iterrows(), 1):
        print(f"    {i}. {row['CVEGEO_A']} ↔ {row['CVEGEO_B']} | "
              f"Δ={row['diferencia']:.1f}, pob={row['poblacion_total']:,.0f}, "
              f"prioridad={row['prioridad_brt']:,.0f}")

    # Identificar AGEBs más carenciadas sin acceso a servicios
    if df_denue is not None:
        merged = indicadores.merge(df_denue[["CVEGEO", "indice_atraccion_norm"]],
                                    on="CVEGEO", how="left")
        merged["indice_atraccion_norm"] = merged["indice_atraccion_norm"].fillna(0)

        # AGEBs carenciadas (puntaje <= 5) con baja atracción
        carenciadas = merged[
            (merged["puntaje_compuesto"] <= 5) &
            (merged["indice_atraccion_norm"] < 10)
        ]
        print(f"\n  AGEBs de alta marginación con bajo acceso a servicios: {len(carenciadas)}")
        for _, row in carenciadas.head(10).iterrows():
            print(f"    {row['CVEGEO']}: puntaje={row['puntaje_compuesto']:.1f}, "
                  f"atracción={row['indice_atraccion_norm']:.1f}")

    return df_prioridad


def main():
    print("=" * 60)
    print("PASO 05: Cruce con corredor BRT")
    print("=" * 60)

    trazo_path = buscar_trazo_brt()

    if trazo_path:
        print(f"\n  Trazo BRT encontrado: {trazo_path.name}")
        metricas, agebs_impactadas = modo_a_con_trazo(trazo_path)

        # Guardar resumen
        utils.asegurar_output_dir()
        resumen = pd.DataFrame([metricas])
        resumen_path = utils.OUTPUT_DIR / "resumen_impacto_brt.csv"
        resumen.to_csv(resumen_path, index=False)
        print(f"\n  ✓ Resumen BRT: {resumen_path}")
    else:
        print("\n  No se encontró trazo BRT en datos/trazo_brt/")
        print("  Ejecutando en modo recomendación...")
        df_prioridad = modo_b_sin_trazo()

        # Guardar recomendaciones
        utils.asegurar_output_dir()
        prioridad_path = utils.OUTPUT_DIR / "recomendacion_corredor_brt.csv"
        df_prioridad.to_csv(prioridad_path, index=False)
        print(f"\n  ✓ Recomendaciones: {prioridad_path}")

        resumen = {
            "modo": "recomendacion",
            "fronteras_analizadas": len(df_prioridad),
            "zona_prioridad_1_A": df_prioridad.iloc[0]["CVEGEO_A"] if len(df_prioridad) > 0 else "",
            "zona_prioridad_1_B": df_prioridad.iloc[0]["CVEGEO_B"] if len(df_prioridad) > 0 else "",
        }
        resumen_path = utils.OUTPUT_DIR / "resumen_impacto_brt.csv"
        pd.DataFrame([resumen]).to_csv(resumen_path, index=False)
        print(f"  ✓ Resumen: {resumen_path}")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as e:
        print(f"\n  ✗ {e}")
        print("  → Ejecute primero los pasos 02, 03 y 04")
        sys.exit(1)
    except ImportError as e:
        print(f"\n  ✗ Dependencia faltante: {e}")
        sys.exit(1)
