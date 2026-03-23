#!/usr/bin/env python3
"""
Paso 06: Generación de mapa interactivo con Folium.
Produce un HTML autocontenido con capas de AGEBs, fronteras, DENUE y BRT.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils


# Paleta de colores: rojo (carenciado) → amarillo → verde (privilegiado)
def color_puntaje(puntaje: float) -> str:
    """Retorna color hex según puntaje compuesto (1-20)."""
    if pd.isna(puntaje):
        return "#808080"  # gris para sin datos

    if puntaje <= 5:
        # Rojo oscuro a rojo
        t = (puntaje - 1) / 4
        r = int(139 + t * (255 - 139))
        return f"#{r:02x}0000"
    elif puntaje <= 10:
        # Rojo a naranja-amarillo
        t = (puntaje - 5) / 5
        r = 255
        g = int(t * 200)
        return f"#{r:02x}{g:02x}00"
    elif puntaje <= 15:
        # Amarillo a verde claro
        t = (puntaje - 10) / 5
        r = int(255 * (1 - t))
        g = int(200 + t * 55)
        return f"#{r:02x}{g:02x}00"
    else:
        # Verde claro a verde oscuro
        t = (puntaje - 15) / 5
        g = int(255 - t * (255 - 100))
        return f"#00{g:02x}00"


def cargar_estaciones_brt():
    """Carga estaciones BRT desde KMZ/KML en datos/trazo_brt/.
    Returns: lista de (nombre, lat, lon) ordenada por nombre, o None si no hay archivo.
    """
    import zipfile
    import xml.etree.ElementTree as ET

    brt_dir = utils.DATOS_DIR / "trazo_brt"
    if not brt_dir.exists():
        return None

    # Buscar KMZ o KML
    kml_content = None
    for kmz in brt_dir.glob("*.kmz"):
        with zipfile.ZipFile(kmz, "r") as z:
            for name in z.namelist():
                if name.endswith(".kml"):
                    kml_content = z.read(name)
                    break
        if kml_content:
            break

    if not kml_content:
        for kml_file in brt_dir.glob("*.kml"):
            kml_content = kml_file.read_bytes()
            break

    if not kml_content:
        return None

    # Parsear KML
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    tree = ET.fromstring(kml_content)
    estaciones = []
    for pm in tree.findall(".//kml:Placemark", ns):
        name_el = pm.find("kml:name", ns)
        coords_el = pm.find(".//kml:coordinates", ns)
        if name_el is None or coords_el is None:
            continue
        nombre = name_el.text.strip()
        parts = coords_el.text.strip().split(",")
        lon, lat = float(parts[0]), float(parts[1])
        estaciones.append((nombre, lat, lon))

    # Ordenar por nombre numérico
    estaciones.sort(key=lambda x: int(x[0]) if x[0].isdigit() else 99)
    return estaciones if estaciones else None


def grosor_frontera(clasificacion: str) -> int:
    """Retorna grosor de línea según clasificación de frontera."""
    return {"extrema": 5, "alta": 3, "moderada": 1}.get(clasificacion, 1)


def crear_leyenda_html() -> str:
    """Genera HTML para la leyenda del mapa."""
    return """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000;
                background: white; padding: 12px; border-radius: 5px;
                border: 2px solid grey; font-family: Arial; font-size: 12px;
                max-width: 220px;">
        <b>Puntaje Socioeconómico</b><br>
        <i style="background: #8B0000; width: 18px; height: 12px; display: inline-block;"></i> 1-5: Muy alta marginación<br>
        <i style="background: #FF6400; width: 18px; height: 12px; display: inline-block;"></i> 6-10: Alta marginación<br>
        <i style="background: #C8FF00; width: 18px; height: 12px; display: inline-block;"></i> 11-15: Media-baja<br>
        <i style="background: #006400; width: 18px; height: 12px; display: inline-block;"></i> 16-20: Baja marginación<br>
        <br>
        <b>Fronteras de Desigualdad</b><br>
        <i style="background: red; width: 18px; height: 5px; display: inline-block;"></i> Extrema (Δ≥12)<br>
        <i style="background: red; width: 18px; height: 3px; display: inline-block;"></i> Alta (Δ≥8)<br>
        <i style="background: red; width: 18px; height: 1px; display: inline-block;"></i> Moderada (Δ≥5)<br>
    </div>
    """


def main():
    print("=" * 60)
    print("PASO 06: Generación de mapa interactivo")
    print("=" * 60)

    import folium
    from folium.plugins import MarkerCluster
    import geopandas as gpd
    import branca

    # 1. Cargar AGEBs con puntaje
    ageb_path = utils.OUTPUT_DIR / "agebs_con_puntaje.gpkg"
    print(f"\n  Cargando AGEBs: {ageb_path.name}")
    gdf_agebs = gpd.read_file(ageb_path)
    gdf_agebs = gdf_agebs.to_crs(utils.CRS_GEO)
    print(f"  {len(gdf_agebs)} AGEBs")

    # Simplificar geometrías para reducir tamaño del HTML
    gdf_agebs["geometry"] = gdf_agebs.geometry.simplify(0.0001, preserve_topology=True)

    # 2. Calcular centro del mapa
    bounds = gdf_agebs.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2
    print(f"  Centro: [{center_lat:.4f}, {center_lon:.4f}]")

    # 3. Crear mapa base
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles="CartoDB positron",
    )

    # 4. Capa 1: Coropleta de AGEBs
    print("  Agregando capa de AGEBs...")
    fg_agebs = folium.FeatureGroup(name="AGEBs - Puntaje Socioeconómico", show=True)

    for _, row in gdf_agebs.iterrows():
        puntaje = row.get("puntaje_compuesto", np.nan)
        pobtot = row.get("POBTOT", "N/D")
        cvegeo = row.get("CVEGEO", "N/D")

        color = color_puntaje(puntaje)
        puntaje_str = f"{puntaje:.1f}" if not pd.isna(puntaje) else "N/D"

        popup_html = (
            f"<b>AGEB:</b> {cvegeo}<br>"
            f"<b>Puntaje:</b> {puntaje_str}<br>"
            f"<b>Población:</b> {pobtot}<br>"
        )

        tooltip = f"AGEB {cvegeo} | Puntaje: {puntaje_str}"

        folium.GeoJson(
            row.geometry.__geo_interface__,
            style_function=lambda x, c=color: {
                "fillColor": c,
                "color": "#333",
                "weight": 0.5,
                "fillOpacity": 0.6,
            },
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=tooltip,
        ).add_to(fg_agebs)

    fg_agebs.add_to(m)

    # 5. Capa 2: Fronteras de desigualdad
    fronteras_gpkg = utils.OUTPUT_DIR / "fronteras_identificadas.gpkg"
    if fronteras_gpkg.exists():
        print("  Agregando fronteras de desigualdad...")
        gdf_fronteras = gpd.read_file(fronteras_gpkg)
        fg_fronteras = folium.FeatureGroup(name="Fronteras de Desigualdad", show=True)

        for _, row in gdf_fronteras.iterrows():
            clasif = row.get("clasificacion", "moderada")
            diff = row.get("diferencia", 0)
            weight = grosor_frontera(clasif)

            popup = f"""
            <b>Frontera {clasif}</b><br>
            AGEB A: {row.get('CVEGEO_A', 'N/D')} (puntaje: {row.get('puntaje_A', 'N/D')})<br>
            AGEB B: {row.get('CVEGEO_B', 'N/D')} (puntaje: {row.get('puntaje_B', 'N/D')})<br>
            Diferencia: {diff:.1f}
            """

            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda x, w=weight: {
                    "color": "red",
                    "weight": w,
                    "opacity": 0.8,
                },
                popup=folium.Popup(popup, max_width=300),
                tooltip=f"Frontera {clasif} (Δ={diff:.1f})",
            ).add_to(fg_fronteras)

        fg_fronteras.add_to(m)
        print(f"    {len(gdf_fronteras)} fronteras agregadas")

    # 6. Capa 3: Puntos DENUE
    # Salud, educación, gobierno: todos. Comercio/manufactura: solo 6+ empleados.
    denue_csv = utils.OUTPUT_DIR / "denue_puntos.csv"
    if denue_csv.exists():
        print("  Agregando puntos DENUE...")
        df_denue = pd.read_csv(denue_csv)

        # Umbrales de filtrado por sector (para no sobrecargar)
        umbral_empleados = {
            "salud": 0,        # todos
            "educacion": 0,    # todos
            "gobierno": 0,     # todos
            "manufactura": 6,  # 6+ empleados
            "comercio": 11,    # 11+ empleados (son muchos)
        }

        colores_sector = {
            "salud": "red",
            "educacion": "blue",
            "comercio": "green",
            "manufactura": "purple",
            "gobierno": "orange",
        }

        for sector, color in colores_sector.items():
            umbral = umbral_empleados.get(sector, 6)
            df_sector = df_denue[
                (df_denue["sector"] == sector) &
                (df_denue["empleados_est"] >= umbral)
            ]
            if len(df_sector) == 0:
                continue

            fg_sector = folium.FeatureGroup(
                name=f"DENUE - {sector.capitalize()}", show=False
            )
            mc = MarkerCluster()

            for _, row in df_sector.iterrows():
                nombre = str(row.get("nom_estab", ""))
                actividad = str(row.get("nombre_act", ""))
                popup_html = (
                    f"<b>{nombre}</b><br>"
                    f"{actividad}<br>"
                    f"<b>Empleados est.:</b> {row['empleados_est']:.0f}"
                )
                folium.Marker(
                    location=[row["latitud"], row["longitud"]],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"{sector.capitalize()}: {nombre[:30]}",
                    icon=folium.Icon(color=color, icon="info-sign", prefix="glyphicon"),
                ).add_to(mc)

            mc.add_to(fg_sector)
            fg_sector.add_to(m)
            print(f"    {sector}: {len(df_sector)} establecimientos")

    # 7. Puntos de referencia (aeropuerto)
    fg_ref = folium.FeatureGroup(name="Puntos de referencia", show=True)
    folium.Marker(
        location=[22.2839, -97.8649],
        tooltip="Aeropuerto Int. Gral. Francisco Javier Mina",
        icon=folium.DivIcon(
            html='<div style="font-size:11px;font-weight:bold;color:#333;'
                 'background:rgba(255,255,255,0.85);padding:2px 6px;'
                 'border-radius:3px;border:1px solid #666;'
                 'white-space:nowrap;">&#9992; Aeropuerto TAM</div>',
            icon_size=(130, 24),
            icon_anchor=(65, 12),
        ),
    ).add_to(fg_ref)
    fg_ref.add_to(m)

    # 8. Capa BRT: estaciones + línea del corredor
    estaciones_brt = cargar_estaciones_brt()
    if estaciones_brt:
        print(f"  Agregando BRT: {len(estaciones_brt)} estaciones...")

        # Capa: Línea del corredor (conectando estaciones en orden)
        fg_linea = folium.FeatureGroup(name="BRT - Corredor troncal", show=True)
        coords_linea = [[lat, lon] for _, lat, lon in estaciones_brt]
        folium.PolyLine(
            coords_linea,
            color="#0055CC",
            weight=4,
            opacity=0.85,
            tooltip="Corredor troncal BRT",
        ).add_to(fg_linea)
        fg_linea.add_to(m)

        # Capa: Estaciones con labels
        fg_estaciones = folium.FeatureGroup(name="BRT - Estaciones", show=True)
        for nombre, lat, lon in estaciones_brt:
            # Label permanente con número
            folium.Marker(
                location=[lat, lon],
                tooltip=f"Estación {nombre}",
                icon=folium.DivIcon(
                    html=f'<div style="font-size:10px;font-weight:bold;color:white;'
                         f'background:#0055CC;padding:1px 4px;border-radius:10px;'
                         f'text-align:center;border:1px solid white;'
                         f'min-width:18px;">{nombre}</div>',
                    icon_size=(24, 18),
                    icon_anchor=(12, 9),
                ),
            ).add_to(fg_estaciones)
        fg_estaciones.add_to(m)

        # Capa: Buffer de influencia 400m
        from shapely.geometry import Point as ShapelyPoint
        fg_buffer = folium.FeatureGroup(name="BRT - Área influencia 400m", show=False)
        for nombre, lat, lon in estaciones_brt:
            # Buffer 400m (~0.0036 grados aprox)
            punto_utm = gpd.GeoSeries([ShapelyPoint(lon, lat)], crs=utils.CRS_GEO).to_crs(utils.CRS_PROJ)
            buffer_utm = punto_utm.buffer(400)
            buffer_wgs = buffer_utm.to_crs(utils.CRS_GEO)
            folium.GeoJson(
                buffer_wgs.iloc[0].__geo_interface__,
                style_function=lambda x: {
                    "color": "#0055CC",
                    "weight": 1,
                    "fillColor": "#0055CC",
                    "fillOpacity": 0.08,
                },
            ).add_to(fg_buffer)
        fg_buffer.add_to(m)

    # 8. Leyenda
    m.get_root().html.add_child(folium.Element(crear_leyenda_html()))

    # 9. Layer control
    folium.LayerControl(collapsed=False).add_to(m)

    # 10. Guardar
    utils.asegurar_output_dir()
    output_path = utils.OUTPUT_DIR / "mapa_fronteras_desigualdad.html"
    m.save(str(output_path))
    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"\n  ✓ Mapa guardado: {output_path} ({size_mb:.1f} MB)")

    if size_mb > 10:
        print("  ⚠ El archivo es grande. Considere simplificar geometrías.")

    print("\n  Pipeline completado exitosamente.")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as e:
        print(f"\n  ✗ {e}")
        print("  → Ejecute primero los pasos anteriores")
        sys.exit(1)
    except ImportError as e:
        print(f"\n  ✗ Dependencia faltante: {e}")
        print("  → pip3 install folium geopandas branca")
        sys.exit(1)
