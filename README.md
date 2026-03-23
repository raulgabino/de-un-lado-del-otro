# De Un Lado, Del Otro — Fronteras de Desigualdad ZM Tampico

Analisis de segregacion socioeconomica a escala de AGEB en la zona metropolitana Tampico-Madero-Altamira (Tamaulipas). Genera evidencia cuantitativa y mapas interactivos para sustentar la justificacion social del Sistema Integrado de Transporte (SIT/BRT) ante FONADIN/CAF.

Adapta la metodologia de [Viridiana Rios](https://github.com/Viri-Rios/DeUnLado_DelOtro) — originalmente en R — a un pipeline en Python.

## Zona de estudio

| Municipio | Clave | AGEBs | Poblacion | Puntaje promedio |
|-----------|-------|------:|----------:|-----------------:|
| Altamira | 28003 | 135 | 244,760 | 8.1 |
| Ciudad Madero | 28009 | 79 | 205,862 | 12.9 |
| Tampico | 28038 | 107 | 296,908 | 13.4 |
| **Total** | | **321** | **747,530** | **11.0** |

## Resultados principales

- **127 fronteras de desigualdad** identificadas (8 extremas, 33 altas, 86 moderadas)
- La frontera mas extrema: **17 puntos de diferencia** entre AGEBs adyacentes en Ciudad Madero
- **62,771 personas** viven en AGEBs de muy alta marginacion (puntaje <= 5 de 20)
- El corredor BRT (33 estaciones) cubre el **39%** de los comercios medianos/grandes de la ZM

## Estructura

```
src/
  utils.py                      # Constantes y funciones compartidas
  01_preparar_censo.py           # Limpieza de datos censales
  02_construir_indicadores.py    # Indice compuesto por AGEB (1-20)
  03_fronteras_desigualdad.py    # Deteccion de pares contrastantes adyacentes
  04_capa_denue.py               # Empleo y servicios (DENUE 05/2025)
  05_cruce_brt.py                # Cruce con estaciones del BRT
  06_mapa_interactivo.py         # Mapa Folium con todas las capas
  run_pipeline.py                # Ejecuta todo en orden

output/
  mapa_fronteras_desigualdad.html   # Mapa interactivo (autocontenido)
  indicadores_por_ageb.csv          # 321 AGEBs con puntaje compuesto
  fronteras_identificadas.csv       # 127 pares con diferencia >= 5
  fronteras_identificadas.gpkg      # Geometrias de lineas de frontera
  agebs_con_puntaje.gpkg            # Poligonos AGEB para GIS
  denue_ageb_resumen.csv            # Metricas de empleo por AGEB
  recomendacion_corredor_brt.csv    # Zonas prioritarias para BRT
```

## Datos necesarios

Los datos fuente no estan en el repositorio (~4 GB). Descargar de INEGI y colocar en `datos/`:

| Fuente | Descarga | Destino |
|--------|----------|---------|
| Censo 2020 (AGEB urbana) | [INEGI - Censo 2020](https://www.inegi.org.mx/programas/ccpv/2020/#microdatos) | `datos/censo2020/` |
| Marco Geoestadistico (AGEBs) | [INEGI - Marco Geo](https://www.inegi.org.mx/temas/mg/#Descargas) | `datos/marco_geo/` |
| DENUE 05/2025 (Tamaulipas) | [INEGI - DENUE](https://www.inegi.org.mx/app/descarga/?ti=6) | `datos/denue/` |
| Estaciones BRT (KMZ) | Proporcionado por el equipo SIT | `datos/trazo_brt/` |

## Instalacion y ejecucion

```bash
pip install -r requirements.txt
python src/run_pipeline.py
```

El mapa se genera en `output/mapa_fronteras_desigualdad.html` — abrir en cualquier navegador.

## Metodologia

Se construyen 15 indicadores del Censo 2020 (8 de riqueza, 7 de carencia), cada uno convertido a ventiles (1-20). El puntaje compuesto es el promedio. Se detectan pares de AGEBs geograficamente adyacentes con diferencias extremas en puntaje (>= 12 de 20 puntos). Esto se cruza con datos de empleo del DENUE y el trazo del corredor BRT para cuantificar el impacto del transporte en la conectividad social.

Ver [`CONTEXTO_PROYECTO.md`](CONTEXTO_PROYECTO.md) para la documentacion tecnica completa.

## Creditos

- Metodologia original: [Viridiana Rios](https://github.com/Viri-Rios/DeUnLado_DelOtro), codigo R por Lorenzo Leon Robles
- Datos: INEGI (Censo 2020, DENUE 05/2025, Marco Geoestadistico)
