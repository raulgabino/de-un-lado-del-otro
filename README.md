# Cobertura Social del Sistema Integrado de Transporte — Tampico

Analisis de la cobertura socioeconomica del corredor BRT del SIT en la zona metropolitana Tampico-Madero-Altamira (Tamaulipas). Evalua como las estaciones del corredor conectan zonas de distinto nivel de marginacion con centros de empleo, salud, educacion y comercio, usando datos censales a nivel de AGEB.

Desarrollado por **Raul Gabino**.

## Zona de estudio

| Municipio | Clave | AGEBs | Poblacion | Puntaje promedio |
|-----------|-------|------:|----------:|-----------------:|
| Altamira | 28003 | 135 | 244,760 | 8.1 |
| Ciudad Madero | 28009 | 79 | 205,862 | 12.9 |
| Tampico | 28038 | 107 | 296,908 | 13.4 |
| **Total** | | **321** | **747,530** | **11.0** |

## Resultados principales

- **127 contrastes socioeconomicos** detectados entre AGEBs adyacentes (8 extremos, 33 altos, 86 moderados)
- El contraste mas extremo: **17 puntos de diferencia** (de 20) entre dos AGEBs vecinas en Ciudad Madero
- **62,771 personas** en AGEBs de muy alta marginacion (puntaje <= 5)
- El corredor BRT (33 estaciones) cubre el **39%** de los comercios medianos/grandes de la ZM
- **804 establecimientos** con 11+ empleados dentro del area de influencia de 400m (~33,000 empleos)

## Metodologia

### Indice compuesto de nivel socioeconomico (1-20)

Se construyen 15 indicadores a partir del Censo 2020 de INEGI, agrupados en dos categorias:

**Indicadores de nivel alto** (mayor valor = mayor nivel socioeconomico):
- Porcentaje de jovenes 18-24 que estudian, grado promedio de escolaridad, afiliacion a salud privada
- Viviendas con automovil, computadora, internet, TV de paga, videojuegos

**Indicadores de carencia** (mayor valor = mayor marginacion):
- Ocupantes por cuarto, analfabetismo, primaria incompleta
- Viviendas sin agua entubada, sin drenaje, con piso de tierra, sin electricidad

Cada indicador se convierte a ventiles (1-20) usando ranking estadistico. Los indicadores de carencia se invierten para que el puntaje 20 siempre represente mejor condicion. El puntaje compuesto es el promedio de los 15 ventiles.

### Deteccion de contrastes

Se construye un grafo de adyacencia entre AGEBs y se calcula la diferencia de puntaje entre cada par vecino. Los pares con diferencia >= 5 se clasifican como contrastes moderados, >= 8 como altos, y >= 12 como extremos.

### Cruce con DENUE y BRT

Los 31,711 establecimientos del DENUE 05/2025 en la ZM se clasifican por sector economico y se cruzan espacialmente con los buffers de 400m alrededor de cada estacion BRT para cuantificar la cobertura de empleo y servicios del corredor.

## Estructura

```
src/
  utils.py                      # Constantes y funciones compartidas
  01_preparar_censo.py           # Limpieza de datos censales
  02_construir_indicadores.py    # Indice compuesto por AGEB (1-20)
  03_fronteras_desigualdad.py    # Deteccion de contrastes entre AGEBs adyacentes
  04_capa_denue.py               # Empleo y servicios (DENUE 05/2025)
  05_cruce_brt.py                # Cruce con estaciones del BRT
  06_mapa_interactivo.py         # Mapa Folium con todas las capas
  run_pipeline.py                # Ejecuta todo en orden

output/
  mapa_fronteras_desigualdad.html   # Mapa interactivo (autocontenido)
  indicadores_por_ageb.csv          # 321 AGEBs con puntaje compuesto
  fronteras_identificadas.csv       # 127 pares con diferencia >= 5
  fronteras_identificadas.gpkg      # Geometrias de lineas de contraste
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

El mapa se genera en `output/mapa_fronteras_desigualdad.html`.

## Deploy

El proyecto incluye configuracion para Vercel (`vercel.json` + `public/`). Al importar el repo en Vercel se despliega automaticamente como sitio estatico con landing page y mapa interactivo.
