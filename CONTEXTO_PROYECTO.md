# De Un Lado, Del Otro — Fronteras de Desigualdad en la ZM Tampico

## Propósito

Análisis cuantitativo de segregación socioeconómica a escala de AGEB en la zona metropolitana de Tampico-Madero-Altamira, Tamaulipas. Genera evidencia visual y estadística para sustentar la justificación social del Sistema Integrado de Transporte (SIT/BRT) ante FONADIN/CAF.

Adapta la metodología de Viridiana Ríos ("De Un Lado, Del Otro") — originalmente en R — a un pipeline en Python focalizado en los tres municipios tamaulipecos del SIT.

## Zona de estudio

| Municipio | Clave | AGEBs analizadas | Población | Puntaje promedio |
|-----------|-------|----------------:|----------:|-----------------:|
| Altamira | 28003 | 135 | 244,760 | 8.1 (mayor marginación) |
| Ciudad Madero | 28009 | 79 | 205,862 | 12.9 |
| Tampico | 28038 | 107 | 296,908 | 13.4 (menor marginación) |
| **Total ZM** | | **321** | **747,530** | **11.0** |

## Metodología

### Índice compuesto de nivel socioeconómico (1-20)

Se construyen 15 indicadores a partir del Censo 2020, divididos en dos categorías:

**Indicadores UP** (mayor valor = mayor nivel socioeconómico):
- Escolaridad 18-24, grado promedio de escolaridad, salud privada
- Viviendas con automóvil, PC, internet, TV de paga, videojuegos

**Indicadores DOWN** (mayor valor = mayor carencia):
- Ocupantes por cuarto, analfabetismo, primaria incompleta
- Viviendas sin agua entubada, sin drenaje, con piso de tierra, sin electricidad

Cada indicador se convierte a ventiles (1-20) usando `rankdata(method='min')` de SciPy. Los indicadores DOWN se invierten (21 - ventil). El puntaje compuesto es el promedio de los 15 ventiles:
- **1-5**: Muy alta marginación (47 AGEBs, 62,771 hab.)
- **6-10**: Alta marginación
- **11-15**: Marginación media-baja
- **16-20**: Baja marginación (70 AGEBs, 147,014 hab.)

### Fronteras de desigualdad

Se identifican pares de AGEBs geográficamente adyacentes con diferencia extrema en puntaje:

| Clasificación | Umbral | Fronteras encontradas |
|---------------|--------|---------:|
| Extrema | diferencia >= 12 | 8 |
| Alta | diferencia >= 8 | 33 |
| Moderada | diferencia >= 5 | 86 |
| **Total** | | **127** |

La frontera más extrema: **17 puntos de diferencia** entre dos AGEBs adyacentes en Ciudad Madero (puntaje 1.5 vs 18.5).

### Capa DENUE (empleo y servicios)

Datos del DENUE 05/2025 (Censos Económicos 2024): 31,711 establecimientos en la ZM clasificados por sector SCIAN. Se estiman 208,374 empleos totales y se calcula un índice de atracción de viajes por AGEB.

### Corredor BRT

33 estaciones del corredor troncal del SIT cargadas desde KMZ. Se genera un buffer de 400m por estación como área de influencia peatonal.

## Fuentes de datos

| Fuente | Archivo | Descripción |
|--------|---------|-------------|
| Censo 2020 | `datos/censo2020/.../conjunto_de_datos_ageb_urbana_28_cpv2020.csv` | Principales resultados por AGEB urbana, Tamaulipas |
| Marco Geoestadístico | `datos/marco_geo/2800{3,9,38}_vla_ne_mg_2022/` | Shapefiles de AGEBs por localidad (EPSG:6372) |
| DENUE 05/2025 | `datos/denue/.../denue_inegi_28_.csv` | 148,560 establecimientos en Tamaulipas |
| Estaciones BRT | `datos/trazo_brt/33 Estac. BRT_Tampico COMPLET.kmz` | 33 estaciones del corredor troncal |

## Pipeline

```
src/01_preparar_censo.py      → output/censo_ageb_limpio.csv
src/02_construir_indicadores.py → output/indicadores_por_ageb.csv
src/03_fronteras_desigualdad.py → output/fronteras_identificadas.csv + .gpkg
src/04_capa_denue.py            → output/denue_ageb_resumen.csv
src/05_cruce_brt.py             → output/recomendacion_corredor_brt.csv
src/06_mapa_interactivo.py      → output/mapa_fronteras_desigualdad.html
```

Ejecutar todo: `python3 src/run_pipeline.py`

## Productos

| Archivo | Descripción |
|---------|-------------|
| `output/mapa_fronteras_desigualdad.html` | Mapa interactivo Folium (7 MB, autocontenido) con capas de AGEBs, fronteras, DENUE, estaciones BRT y aeropuerto |
| `output/indicadores_por_ageb.csv` | 321 AGEBs con 15 indicadores, ventiles y puntaje compuesto |
| `output/fronteras_identificadas.csv` | 127 pares de AGEBs adyacentes con diferencia >= 5 |
| `output/fronteras_identificadas.gpkg` | Geometrías de las líneas de frontera |
| `output/agebs_con_puntaje.gpkg` | Polígonos AGEB con puntaje (para GIS) |
| `output/denue_ageb_resumen.csv` | Métricas de empleo y servicios por AGEB |
| `output/recomendacion_corredor_brt.csv` | Zonas prioritarias para conectividad BRT |

## Hallazgos clave

- Altamira concentra la mayor marginación (puntaje promedio 8.1) mientras que Tampico y Cd. Madero promedian 13+
- Las 8 fronteras extremas se concentran en Ciudad Madero, en la transición entre colonias populares y zonas residenciales
- 62,771 personas viven en AGEBs de muy alta marginación (puntaje <= 5)
- 45 AGEBs de alta marginación tienen bajo acceso a empleo y servicios (índice de atracción < 10)

## Notas técnicas

- Censo: encoding `utf-8-sig`, MUN/MZA son `int`, AGEB es `str`
- NOM_LOC a nivel AGEB = "Total AGEB urbana" — no filtrar
- Shapefiles fragmentados por localidad; se concatenan los `*a.shp` de cada municipio
- DENUE: `per_ocu` es texto ("0 a 5 personas"), `codigo_act` es int de 6 dígitos, `ageb` es int de 3 dígitos (necesita zfill a 4)
- Adyacencia calculada con `libpysal.weights.Queen` en EPSG:32614 (UTM 14N)
- Dependencias: pandas, geopandas, shapely, folium, scipy, pyproj, libpysal, branca
