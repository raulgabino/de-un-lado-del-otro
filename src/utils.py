"""
Funciones compartidas para el pipeline De Un Lado, Del Otro.
Análisis de fronteras de desigualdad para la ZM Tampico-Madero-Altamira.
"""

import sys
from pathlib import Path
from math import ceil

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATOS_DIR = PROJECT_ROOT / "datos"
OUTPUT_DIR = PROJECT_ROOT / "output"

# ---------------------------------------------------------------------------
# Constantes geográficas
# ---------------------------------------------------------------------------
ENTIDAD_INT = 28  # Tamaulipas
ENTIDAD_STR = "28"
MUNICIPIOS_INT = {3: "Altamira", 9: "Ciudad Madero", 38: "Tampico"}
MUNICIPIOS_STR = {"003": "Altamira", "009": "Ciudad Madero", "038": "Tampico"}
CRS_GEO = "EPSG:4326"      # WGS84 para visualización / Folium
CRS_PROJ = "EPSG:32614"    # UTM zona 14N para cálculos en metros
CRS_INEGI = "EPSG:6372"    # ITRF2008 / LCC México (shapefiles INEGI)

# Rutas a datos validados
CENSO_CSV = DATOS_DIR / "censo2020" / "ageb_mza_urbana_28_cpv2020" / "conjunto_de_datos" / "conjunto_de_datos_ageb_urbana_28_cpv2020.csv"
DENUE_CSV = DATOS_DIR / "denue" / "conjunto_de_datos" / "denue_inegi_28_.csv"
MUN_DIR_PREFIXES = ["28003", "28009", "28038"]

# ---------------------------------------------------------------------------
# Definición de indicadores
# ---------------------------------------------------------------------------
# Cada indicador es (nombre, numerador, denominador)
# Si denominador es None, el numerador ya es un promedio/tasa directa.

INDICADORES_UP = [
    ("UP_escolaridad_18_24", "P18A24A",    "P_18A24"),
    ("UP_grado_escolaridad", "GRAPROES",   None),
    ("UP_salud_privada",     "PAFIL_IPRIV","POBTOT"),
    ("UP_auto",              "VPH_AUTOM",  "VIVPARH_CV"),
    ("UP_pc",                "VPH_PC",     "VIVPARH_CV"),
    ("UP_internet",          "VPH_INTER",  "VIVPARH_CV"),
    ("UP_tv_paga",           "VPH_SPMVPI", "VIVPARH_CV"),
    ("UP_videojuegos",       "VPH_CVJ",    "VIVPARH_CV"),
]

INDICADORES_DOWN = [
    ("DOWN_ocupantes_cuarto",     "PRO_OCUP_C", None),
    ("DOWN_analfabetismo",        "P15YM_AN",   "P_15YMAS"),
    ("DOWN_primaria_incompleta",  "P15PRI_IN",  "P_15YMAS"),
    ("DOWN_sin_agua",             "VPH_AGUAFV", "VIVPARH_CV"),
    ("DOWN_sin_drenaje",          "VPH_NODREN", "VIVPARH_CV"),
    ("DOWN_piso_tierra",          "VPH_PISOTI", "VIVPARH_CV"),
    ("DOWN_sin_electricidad",     "VPH_S_ELEC", "VIVPARH_CV"),
]

# Variables censales requeridas (para Gate 4)
VARS_REQUERIDAS = [
    "POBTOT", "P18A24A", "P_18A24", "GRAPROES", "PAFIL_IPRIV",
    "PRO_OCUP_C", "VPH_AUTOM", "VPH_PC", "VPH_INTER", "VPH_SPMVPI",
    "VPH_CVJ", "P15YM_AN", "P15PRI_IN", "P_15YMAS", "VPH_AGUAFV",
    "VPH_NODREN", "VPH_PISOTI", "VPH_S_ELEC", "VIVPARH_CV",
]

# Columnas que deben ser numéricas
COLS_NUMERICAS = VARS_REQUERIDAS + ["VIVPAR_HAB"]

# Umbrales de clasificación de fronteras
UMBRAL_EXTREMA = 12
UMBRAL_ALTA = 8
UMBRAL_MODERADA = 5

# DENUE: mapeo de rangos de personal ocupado a valores centrales
PER_OCU_MAP = {
    "0 a 5 personas": 2.5,
    "6 a 10 personas": 8.0,
    "11 a 30 personas": 20.0,
    "31 a 50 personas": 40.0,
    "51 a 100 personas": 75.0,
    "101 a 250 personas": 175.0,
    "251 y más personas": 350.0,
}

# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Error de validación en un gate del pipeline."""
    def __init__(self, gate: int, message: str):
        self.gate = gate
        self.message = message
        super().__init__(f"[GATE {gate} FALLO] {message}")


# ---------------------------------------------------------------------------
# Funciones de validación
# ---------------------------------------------------------------------------

def validar_gate(condition: bool, gate: int, message: str):
    """Valida una condición. Si falla, lanza ValidationError."""
    if condition:
        print(f"  ✓ Gate {gate}: OK")
    else:
        raise ValidationError(gate, message)


# ---------------------------------------------------------------------------
# Carga y filtrado de datos censales
# ---------------------------------------------------------------------------

def cargar_csv_censo(path: Path = None) -> pd.DataFrame:
    """
    Carga el CSV del Censo 2020 AGEB urbana.
    Encoding: utf-8-sig (BOM en columna ENTIDAD).
    Reemplaza '*' (dato confidencial) y 'N/D' (no disponible) con NaN.
    Convierte columnas numéricas conocidas.

    Nota: MUN y MZA son int, AGEB es str.
    """
    path = path or CENSO_CSV
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)

    # Reemplazar valores especiales con NaN
    df = df.replace({"*": np.nan, "N/D": np.nan})

    # Convertir columnas numéricas
    for col in COLS_NUMERICAS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def filtrar_zm_tampico(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra el DataFrame del censo a la zona metropolitana Tampico-Madero-Altamira.
    Solo registros a nivel AGEB: AGEB != '0000', MZA == 0.

    Nota: MUN y MZA son int en este CSV. AGEB es str.
    NO filtra por NOM_LOC (contiene 'Total AGEB urbana' que es válido).
    """
    mask = (
        df["MUN"].isin(list(MUNICIPIOS_INT.keys()))
        & (df["AGEB"].astype(str) != "0000")
        & (df["MZA"] == 0)
    )
    return df[mask].copy().reset_index(drop=True)


# ---------------------------------------------------------------------------
# Construcción de CVEGEO
# ---------------------------------------------------------------------------

def construir_cvegeo(df: pd.DataFrame) -> pd.Series:
    """
    Construye la clave CVEGEO de 13 caracteres:
    ENTIDAD(2) + MUN(3) + LOC(4) + AGEB(4)
    """
    return (
        df["ENTIDAD"].astype(str).str.zfill(2)
        + df["MUN"].astype(str).str.zfill(3)
        + df["LOC"].astype(str).str.zfill(4)
        + df["AGEB"].astype(str).str.zfill(4)
    )


# ---------------------------------------------------------------------------
# Asignación de ventiles
# ---------------------------------------------------------------------------

def asignar_ventiles(series: pd.Series, invertir: bool = False) -> pd.Series:
    """
    Asigna ventiles (1-20) a una serie numérica.

    Usa scipy.stats.rankdata con method='min' para manejar empates.
    NO usa pd.qcut porque falla con muchos empates.

    Para indicadores DOWN, invertir=True hace que valores altos
    reciban ventiles bajos (peor condición = ventil bajo).

    Returns: Series con ventiles 1-20 (NaN donde el input era NaN).
    """
    from scipy.stats import rankdata

    result = pd.Series(np.nan, index=series.index)
    valid_mask = series.notna()
    valid_values = series[valid_mask].values

    if len(valid_values) == 0:
        return result

    # Rankear valores
    ranks = rankdata(valid_values, method="min")
    n = len(valid_values)

    # Convertir ranks a ventiles 1-20
    ventiles = np.ceil(ranks / n * 20).astype(int)

    # Asegurar rango [1, 20]
    ventiles = np.clip(ventiles, 1, 20)

    if invertir:
        ventiles = 21 - ventiles

    result.loc[valid_mask] = ventiles
    return result


# ---------------------------------------------------------------------------
# Carga de geometrías
# ---------------------------------------------------------------------------

def cargar_geometrias_ageb():
    """
    Lee y concatena todos los shapefiles *a.shp de los 3 municipios.
    Los shapefiles están fragmentados por localidad en:
      datos/marco_geo/{28003,28009,28038}_vla_ne_mg_2022/*/conjunto_de_datos/*a.shp

    Columnas de los shapefiles: IDENTIFICA, CVEGEO (13 dígitos), geometry.
    CRS original: EPSG:6372 (ITRF2008 / LCC México).

    Returns: GeoDataFrame con CVEGEO y geometry, CRS EPSG:6372.
    """
    import geopandas as gpd

    all_gdfs = []
    for prefix in MUN_DIR_PREFIXES:
        mun_dirs = list(DATOS_DIR.joinpath("marco_geo").glob(f"{prefix}_*"))
        if not mun_dirs:
            raise FileNotFoundError(
                f"No se encontró directorio para municipio {prefix} en {DATOS_DIR / 'marco_geo'}"
            )
        mun_dir = mun_dirs[0]
        for loc_dir in sorted(mun_dir.iterdir()):
            if not loc_dir.is_dir():
                continue
            shp_dir = loc_dir / "conjunto_de_datos"
            if not shp_dir.is_dir():
                continue
            for shp_file in shp_dir.glob("*a.shp"):
                gdf = gpd.read_file(shp_file)
                all_gdfs.append(gdf)

    if not all_gdfs:
        raise FileNotFoundError("No se encontraron shapefiles de AGEBs (*a.shp)")

    gdf_all = pd.concat(all_gdfs, ignore_index=True)
    gdf_all = gpd.GeoDataFrame(gdf_all, geometry="geometry", crs=all_gdfs[0].crs)

    # Reparar geometrías inválidas
    invalid_count = (~gdf_all.geometry.is_valid).sum()
    if invalid_count > 0:
        print(f"  ⚠ Reparando {invalid_count} geometrías inválidas")
        gdf_all["geometry"] = gdf_all.geometry.make_valid()

    return gdf_all


# ---------------------------------------------------------------------------
# Clasificación de fronteras
# ---------------------------------------------------------------------------

def clasificar_frontera(diff: float) -> str:
    """Clasifica una frontera de desigualdad por diferencia de puntaje."""
    if diff >= UMBRAL_EXTREMA:
        return "extrema"
    elif diff >= UMBRAL_ALTA:
        return "alta"
    elif diff >= UMBRAL_MODERADA:
        return "moderada"
    else:
        return "baja"


# ---------------------------------------------------------------------------
# DENUE: parseo de personal ocupado
# ---------------------------------------------------------------------------

def parsear_per_ocu(series: pd.Series) -> pd.Series:
    """Convierte rangos de texto de personal ocupado a valores centrales numéricos."""
    return series.map(PER_OCU_MAP)


def construir_cvegeo_denue(df: pd.DataFrame) -> pd.Series:
    """Construye CVEGEO de 13 dígitos desde columnas DENUE (todas int)."""
    return (
        df["cve_ent"].astype(str).str.zfill(2)
        + df["cve_mun"].astype(str).str.zfill(3)
        + df["cve_loc"].astype(str).str.zfill(4)
        + df["ageb"].astype(str).str.zfill(4)
    )


# ---------------------------------------------------------------------------
# Utilidades de I/O
# ---------------------------------------------------------------------------

def asegurar_output_dir():
    """Crea el directorio de output si no existe."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
