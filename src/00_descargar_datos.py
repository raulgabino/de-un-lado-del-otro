#!/usr/bin/env python3
"""
Paso 00: Descarga automática de datos del INEGI.
Intenta descargar AGEBs (GeoJSON), Censo 2020 y DENUE.
Si falla, imprime instrucciones para descarga manual.
"""

import io
import json
import sys
import zipfile
from pathlib import Path

import requests

# Agregar src/ al path para importar utils
sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils

TIMEOUT = 60  # segundos por request


def descargar_agebs_geojson():
    """
    Descarga AGEBs urbanas de los 3 municipios vía API GeoJSON del INEGI.
    URL: https://gaia.inegi.org.mx/wscatgeo/v2/mgeau/28/{mun}
    """
    print("\n--- Descargando AGEBs urbanas (GeoJSON API) ---")

    import geopandas as gpd
    from shapely.geometry import shape

    all_features = []
    api_ok = True

    for cve_mun, nombre in utils.MUNICIPIOS.items():
        url = f"https://gaia.inegi.org.mx/wscatgeo/v2/mgeau/{utils.ENTIDAD}/{cve_mun}"
        print(f"  Descargando {nombre} ({cve_mun})... ", end="", flush=True)

        try:
            resp = requests.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            # La API puede devolver diferentes estructuras
            features = None
            if isinstance(data, dict):
                if "type" in data and data["type"] == "FeatureCollection":
                    features = data.get("features", [])
                elif "datos" in data:
                    # Formato anidado del INEGI
                    datos = data["datos"]
                    if isinstance(datos, list):
                        features = datos
                    elif isinstance(datos, dict) and "features" in datos:
                        features = datos["features"]

            if features is None:
                print(f"FORMATO INESPERADO")
                print(f"    Claves en respuesta: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                api_ok = False
                continue

            print(f"{len(features)} AGEBs")
            all_features.extend(features)

        except requests.RequestException as e:
            print(f"ERROR: {e}")
            api_ok = False
        except (json.JSONDecodeError, KeyError) as e:
            print(f"ERROR parseando respuesta: {e}")
            api_ok = False

    if not all_features:
        print("\n  ✗ No se pudieron descargar AGEBs vía API.")
        _instrucciones_manual_geo()
        return False

    # Construir GeoDataFrame
    try:
        geojson = {"type": "FeatureCollection", "features": all_features}
        gdf = gpd.GeoDataFrame.from_features(geojson, crs=utils.CRS_GEO)

        output_path = utils.DATOS_DIR / "marco_geo" / "agebs_zm_tampico.geojson"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(output_path, driver="GeoJSON")
        print(f"\n  ✓ Guardado: {output_path} ({len(gdf)} AGEBs)")
        return True

    except Exception as e:
        print(f"\n  ✗ Error guardando GeoJSON: {e}")
        _instrucciones_manual_geo()
        return False


def descargar_censo():
    """
    Intenta descargar el CSV del Censo 2020 para Tamaulipas.
    """
    print("\n--- Descargando Censo 2020 (AGEB urbana, Tamaulipas) ---")

    urls = [
        "https://www.inegi.org.mx/contenidos/programas/ccpv/2020/datosabiertos/ageb_manzana/RESAGEBURB_28CSV20.zip",
        "https://www.inegi.org.mx/contenidos/programas/ccpv/2020/datosabiertos/ageb_manzana/conjunto_de_datos/conjunto_de_datos_ageb_urbana_28_cpv2020.csv.zip",
    ]

    for url in urls:
        print(f"  Intentando: {url.split('/')[-1]}... ", end="", flush=True)
        try:
            resp = requests.get(url, timeout=TIMEOUT * 3, stream=True)
            resp.raise_for_status()

            content = resp.content
            if len(content) < 1000:
                print("respuesta muy pequeña, probablemente no es el archivo")
                continue

            # Intentar descomprimir
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    csv_files = [f for f in zf.namelist() if f.endswith(".csv")]
                    if not csv_files:
                        print("ZIP sin archivos CSV")
                        continue

                    # Extraer el CSV más grande (probablemente el de AGEBs)
                    csv_files.sort(key=lambda f: zf.getinfo(f).file_size, reverse=True)
                    target = csv_files[0]

                    output_dir = utils.DATOS_DIR / "censo2020"
                    output_dir.mkdir(parents=True, exist_ok=True)
                    zf.extract(target, output_dir)
                    print(f"OK → {output_dir / target}")
                    return True

            except zipfile.BadZipFile:
                # Quizás es un CSV directo, no un ZIP
                output_path = utils.DATOS_DIR / "censo2020" / "conjunto_de_datos_ageb_urbana_28_cpv2020.csv"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(content)
                print(f"OK (CSV directo) → {output_path}")
                return True

        except requests.RequestException as e:
            print(f"ERROR: {e}")

    print("\n  ✗ No se pudo descargar el Censo automáticamente.")
    _instrucciones_manual_censo()
    return False


def descargar_denue():
    """
    Intenta descargar el DENUE de Tamaulipas.
    """
    print("\n--- Descargando DENUE (Tamaulipas) ---")

    urls = [
        "https://www.inegi.org.mx/contenidos/masiva/denue/denue_28_csv.zip",
    ]

    for url in urls:
        print(f"  Intentando: {url.split('/')[-1]}... ", end="", flush=True)
        try:
            resp = requests.get(url, timeout=TIMEOUT * 3, stream=True)
            resp.raise_for_status()

            content = resp.content
            if len(content) < 1000:
                print("respuesta muy pequeña")
                continue

            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    csv_files = [f for f in zf.namelist() if f.endswith(".csv")]
                    if not csv_files:
                        print("ZIP sin CSV")
                        continue

                    csv_files.sort(key=lambda f: zf.getinfo(f).file_size, reverse=True)
                    target = csv_files[0]

                    output_dir = utils.DATOS_DIR / "denue"
                    output_dir.mkdir(parents=True, exist_ok=True)
                    zf.extract(target, output_dir)
                    print(f"OK → {output_dir / target}")
                    return True

            except zipfile.BadZipFile:
                print("archivo no es un ZIP válido")

        except requests.RequestException as e:
            print(f"ERROR: {e}")

    print("\n  ✗ No se pudo descargar el DENUE automáticamente.")
    _instrucciones_manual_denue()
    return False


# ---------------------------------------------------------------------------
# Instrucciones de descarga manual
# ---------------------------------------------------------------------------

def _instrucciones_manual_geo():
    print("""
  DESCARGA MANUAL DE AGEBs:
  1. Ir a: https://www.inegi.org.mx/temas/mg/#Descargas
  2. Seleccionar la versión más reciente → Tamaulipas
  3. Descargar la capa de AGEB urbanas
  4. Colocar los archivos (.shp, .shx, .dbf, .prj) en:
     datos/marco_geo/
""")


def _instrucciones_manual_censo():
    print("""
  DESCARGA MANUAL DEL CENSO 2020:
  1. Ir a: https://www.inegi.org.mx/programas/ccpv/2020/#microdatos
  2. Sección "Datos abiertos" → "Principales resultados por AGEB y manzana urbana"
  3. Seleccionar Tamaulipas → Descargar CSV
  4. Descomprimir y colocar el CSV en:
     datos/censo2020/
""")


def _instrucciones_manual_denue():
    print("""
  DESCARGA MANUAL DEL DENUE:
  1. Ir a: https://www.inegi.org.mx/app/descarga/?ti=6
  2. Seleccionar DENUE → Tamaulipas → CSV
  3. Descomprimir y colocar el CSV en:
     datos/denue/
""")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("PASO 00: Descarga de datos del INEGI")
    print("=" * 60)

    resultados = {}

    resultados["AGEBs GeoJSON"] = descargar_agebs_geojson()
    resultados["Censo 2020"] = descargar_censo()
    resultados["DENUE"] = descargar_denue()

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE DESCARGA")
    print("=" * 60)
    for nombre, ok in resultados.items():
        status = "✓ Descargado" if ok else "✗ Requiere descarga manual"
        print(f"  {nombre}: {status}")

    faltantes = [k for k, v in resultados.items() if not v]
    if faltantes:
        print(f"\n  ⚠ {len(faltantes)} archivo(s) requieren descarga manual.")
        print("  Siga las instrucciones impresas arriba.")
        return 1

    print("\n  ✓ Todos los datos descargados exitosamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
