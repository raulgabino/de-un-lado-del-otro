#!/usr/bin/env python3
"""
Paso 03: Identificación de fronteras de desigualdad.
Detecta pares de AGEBs adyacentes con niveles socioeconómicos contrastantes.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils


def validar_geometrias(gdf, indicadores):
    """Valida geometrías y join con indicadores."""
    print("\n  Validando geometrías...")

    # Geometrías tipo Polygon/MultiPolygon
    geom_types = gdf.geometry.geom_type.unique()
    assert all(t in ["Polygon", "MultiPolygon"] for t in geom_types), \
        f"Geometrías inesperadas: {geom_types}"
    print(f"  ✓ {len(gdf)} polígonos de AGEB")

    # Join censo-geo
    claves_indicadores = set(indicadores["CVEGEO"].astype(str))
    claves_geo = set(gdf["CVEGEO"].astype(str))
    matched = claves_indicadores & claves_geo
    pct_match = len(matched) / len(claves_indicadores) * 100 if claves_indicadores else 0

    assert pct_match > 80, \
        f"Solo {pct_match:.1f}% match. Ejemplo censo: {list(claves_indicadores)[:3]}, geo: {list(claves_geo)[:3]}"
    print(f"  ✓ Join censo-geo: {len(matched)}/{len(claves_indicadores)} ({pct_match:.1f}%)")

    return matched


def construir_adyacencia(gdf):
    """
    Construye grafo de adyacencia entre AGEBs.
    Intenta libpysal primero, fallback a shapely.
    Retorna lista de pares (idx_a, idx_b).
    """
    try:
        from libpysal.weights import Queen
        print("  Usando libpysal Queen para adyacencia...")
        w = Queen.from_dataframe(gdf, silence_warnings=True)
        pares = set()
        for i, vecinos in w.neighbors.items():
            for j in vecinos:
                par = (min(i, j), max(i, j))
                pares.add(par)
        print(f"    {len(pares)} pares adyacentes encontrados")
        return list(pares)

    except ImportError:
        print("  libpysal no disponible, usando shapely touches...")
        return _adyacencia_shapely(gdf)


def _adyacencia_shapely(gdf):
    """Fallback: detectar adyacencia con shapely buffer + touches."""
    from shapely.strtree import STRtree

    # Pequeño buffer para manejar imprecisión geométrica
    gdf_buf = gdf.copy()
    gdf_buf["geometry"] = gdf.geometry.buffer(1e-6)  # ~0.1m en grados

    tree = STRtree(gdf_buf.geometry.values)
    pares = set()

    for i in range(len(gdf)):
        geom_i = gdf_buf.geometry.iloc[i]
        candidatos = tree.query(geom_i)
        for j in candidatos:
            if j > i:  # Evitar duplicados y auto-comparación
                if gdf.geometry.iloc[i].touches(gdf.geometry.iloc[j]) or \
                   gdf.geometry.iloc[i].intersects(gdf.geometry.iloc[j]):
                    # Verificar que no se sobreponen completamente
                    inter = gdf.geometry.iloc[i].intersection(gdf.geometry.iloc[j])
                    if not inter.is_empty and inter.geom_type != "Point":
                        pares.add((i, j))

    print(f"    {len(pares)} pares adyacentes encontrados (shapely)")
    return list(pares)


def extraer_frontera(geom_a, geom_b):
    """Extrae la línea de frontera compartida entre dos geometrías."""
    from shapely.geometry import LineString, MultiLineString

    inter = geom_a.intersection(geom_b)

    if inter.is_empty:
        return None

    # Filtrar solo componentes lineales
    if inter.geom_type in ("LineString", "MultiLineString"):
        return inter
    elif inter.geom_type == "GeometryCollection":
        lines = [g for g in inter.geoms
                 if g.geom_type in ("LineString", "MultiLineString")]
        if lines:
            if len(lines) == 1:
                return lines[0]
            return MultiLineString(lines)
    elif inter.geom_type == "Point":
        return None  # Solo se tocan en un punto

    return None


def main():
    print("=" * 60)
    print("PASO 03: Identificación de fronteras de desigualdad")
    print("=" * 60)

    import geopandas as gpd
    from shapely.geometry import mapping

    # 1. Cargar indicadores
    input_path = utils.OUTPUT_DIR / "indicadores_por_ageb.csv"
    print(f"\n  Cargando indicadores: {input_path.name}")
    indicadores = pd.read_csv(input_path, dtype={"CVEGEO": str})
    print(f"  {len(indicadores)} AGEBs con indicadores")

    # 2. Cargar geometrías (concatena shapefiles de 3 municipios)
    print(f"  Cargando geometrías AGEB...")
    gdf = utils.cargar_geometrias_ageb()
    print(f"  {len(gdf)} polígonos cargados (CRS: {gdf.crs})")

    # Reproyectar a UTM 14N para cálculos en metros
    gdf = gdf.to_crs(utils.CRS_PROJ)

    # 3. Validaciones
    matched = validar_geometrias(gdf, indicadores)

    # 4. Join: agregar puntaje a geometrías
    gdf["CVEGEO"] = gdf["CVEGEO"].astype(str)
    indicadores["CVEGEO"] = indicadores["CVEGEO"].astype(str)

    gdf = gdf.merge(
        indicadores[["CVEGEO", "puntaje_compuesto", "POBTOT"]],
        on="CVEGEO",
        how="inner"
    )
    print(f"\n  {len(gdf)} AGEBs con geometría + puntaje")

    # 5. Construir adyacencia
    print("\n  Construyendo grafo de adyacencia...")
    pares = construir_adyacencia(gdf)

    # 6. Calcular diferencias y clasificar
    print("\n  Calculando fronteras de desigualdad...")
    fronteras = []

    for idx_a, idx_b in pares:
        row_a = gdf.iloc[idx_a]
        row_b = gdf.iloc[idx_b]

        score_a = row_a["puntaje_compuesto"]
        score_b = row_b["puntaje_compuesto"]

        if pd.isna(score_a) or pd.isna(score_b):
            continue

        diff = abs(score_a - score_b)
        clasificacion = utils.clasificar_frontera(diff)

        if diff < utils.UMBRAL_MODERADA:
            continue  # No registrar fronteras bajas

        # Extraer línea de frontera
        linea = extraer_frontera(row_a.geometry, row_b.geometry)

        # Distancia entre centroides (metros, ya en UTM)
        centroid_a = row_a.geometry.centroid
        centroid_b = row_b.geometry.centroid
        dist_m = centroid_a.distance(centroid_b)

        fronteras.append({
            "CVEGEO_A": row_a["CVEGEO"],
            "CVEGEO_B": row_b["CVEGEO"],
            "puntaje_A": round(score_a, 2),
            "puntaje_B": round(score_b, 2),
            "diferencia": round(diff, 2),
            "clasificacion": clasificacion,
            "distancia_m": round(dist_m, 1),
            "pobtot_A": row_a.get("POBTOT", np.nan),
            "pobtot_B": row_b.get("POBTOT", np.nan),
            "geometry": linea,
        })

    print(f"\n  Fronteras identificadas:")
    df_fronteras = pd.DataFrame(fronteras)

    for clasif in ["extrema", "alta", "moderada"]:
        n = (df_fronteras["clasificacion"] == clasif).sum()
        print(f"    {clasif.capitalize()}: {n}")

    # 7. Guardar CSV (sin geometría)
    utils.asegurar_output_dir()

    csv_path = utils.OUTPUT_DIR / "fronteras_identificadas.csv"
    df_csv = df_fronteras.drop(columns=["geometry"])
    df_csv.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"\n  ✓ CSV: {csv_path}")

    # 8. Guardar GeoPackage (con geometría de líneas de frontera)
    # Solo fronteras que tienen geometría lineal
    df_con_geom = df_fronteras[df_fronteras["geometry"].notna()].copy()
    if len(df_con_geom) > 0:
        gdf_fronteras = gpd.GeoDataFrame(df_con_geom, geometry="geometry", crs=utils.CRS_PROJ)
        # Reproyectar a WGS84 para exportar
        gdf_fronteras = gdf_fronteras.to_crs(utils.CRS_GEO)
        gpkg_path = utils.OUTPUT_DIR / "fronteras_identificadas.gpkg"
        gdf_fronteras.to_file(gpkg_path, driver="GPKG")
        print(f"  ✓ GPKG: {gpkg_path} ({len(gdf_fronteras)} fronteras con geometría)")
    else:
        print("  ⚠ No se obtuvieron geometrías de frontera para el GPKG")

    # 9. Top 10 fronteras más contrastantes
    print("\n  Top 10 fronteras con mayor contraste:")
    top10 = df_fronteras.nlargest(10, "diferencia")
    for _, row in top10.iterrows():
        print(f"    {row['CVEGEO_A']} ({row['puntaje_A']:.1f}) ↔ "
              f"{row['CVEGEO_B']} ({row['puntaje_B']:.1f}) | "
              f"Δ={row['diferencia']:.1f} [{row['clasificacion']}]")

    # 10. Guardar GeoDataFrame de AGEBs con puntaje (para el mapa)
    ageb_path = utils.OUTPUT_DIR / "agebs_con_puntaje.gpkg"
    gdf_export = gdf.to_crs(utils.CRS_GEO)
    gdf_export.to_file(ageb_path, driver="GPKG")
    print(f"\n  ✓ AGEBs con puntaje: {ageb_path}")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, FileNotFoundError) as e:
        print(f"\n  ✗ {e}")
        sys.exit(1)
    except ImportError as e:
        print(f"\n  ✗ Dependencia faltante: {e}")
        print("  → Instale: pip3 install geopandas libpysal shapely")
        sys.exit(1)
