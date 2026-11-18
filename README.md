# RouteFlow V1.2 — Managua, Nicaragua (corrección de maniobras)

**Sistema web académico de búsqueda de rutas con menor tiempo estimado.**

Aplicación Flask + HTML/CSS + JavaScript/Leaflet. El cálculo lo realiza nuestro **grafo dirigido y ponderado implementado con listas de adyacencia enlazadas en Python** y un **Dijkstra propio**. OSMnx se utiliza para obtener la red vial de OpenStreetMap; NetworkX no calcula las rutas del usuario.

## 1. Instalación en tu computadora (Windows / CMD)

Descomprime **el contenido del ZIP directamente** dentro de la carpeta donde ya tienes `.venv`:

`C:\uam_c\sistemas\semestre_2\prog_estructurada\proyecto\RouteFlow`

No debe quedar `RouteFlow\RouteFlow\app.py`. Comprueba que exista `RouteFlow\app.py`.

Abre CMD en dicha carpeta y ejecuta:

```bat
.venv\Scripts\activate.bat
python --version
python -m pip install -r requirements.txt
python app.py
```

Abre `http://127.0.0.1:5000` si el navegador no lo hizo automáticamente. También puedes hacer doble clic en `iniciar_routeflow.bat` después de instalar las librerías.

Detén el servidor con **Ctrl+C**.

## 2. Primer uso

1. La web se abre enseguida. En segundo plano, se prepara la **red vial real** de Managua descargándola de OpenStreetMap. La descarga inicial requiere conexión y acceso al servicio Overpass. Puede ser lenta o fallar si el servicio está saturado.
2. Cuando aparezca **Calles de Managua listas**, señala origen y destino haciendo clic en el mapa o mediante búsqueda manual. Luego añade hasta 5 paradas.
3. Puedes optimizar el orden de las paradas o mantener el orden ingresado. El destino final siempre queda fijo.
4. Selecciona **Salir ahora** (hora de Managua), o una fecha/hora específica. Haz clic en **Encontrar mi mejor ruta**.
5. El mapa dibuja el recorrido basado en calles reales (azul) y permite comparar con la opción de menor distancia (naranja).
6. La red descargada se guarda en `datos/managua_urbana.graphml`. Se reutiliza en próximos inicios.

### Si falla la red real

La interfaz mostrará un error y el botón **Probar con red ficticia**. Ese modo construye un grafo sintético con calles imaginarias solamente para comprobar el funcionamiento del algoritmo. **Las líneas del modo demostración NO representan calles reales de Managua; no deben utilizarse para conducir.** Puedes regresar al modo real desde la interfaz.

## 3. Límites del prototipo

- **Cobertura:** núcleo urbano, no todo el municipio. BBOX en `config.py` con formato `(oeste, sur, este, norte)` = `(-86.345, 12.065, -86.175, 12.178)`. Para ampliar el área, cambia BBOX y borra/renombra el archivo `.graphml` guardado para forzar nueva descarga.
- **Velocidades:** supuestos por tipo de calle y límites OSM disponibles, modificables en `trafico.py`.
- **Congestión por horario:** factores supuestos para franjas horarias de Managua; NO hay tráfico, cierres ni semáforos medidos en tiempo real. La ruta **minimiza tiempo estimado según el modelo**, no garantiza ser la ruta más rápida en la realidad.
- **Intersecciones y maniobras (V1.2):** recargo en semáforos OSM y estimación de demoras por ángulo de giro (izquierda/derecha/retorno) con diferentes recargos en hora pico. Dijkstra conserva el estado de la arista de llegada; no depende solo del nodo. Se respetan únicamente restricciones de giro expresamente verificadas e incorporadas mediante `Graph.prohibirGiro(...)`. **La descarga estándar de OSMnx NO importa todas las relaciones OSM de prohibiciones de giro**: por tanto RouteFlow **no puede garantizar la legalidad de cada maniobra** ni conoce fases reales de semáforos.
- **Origen, destino y paradas (V1.2):** se proyectan sobre tramos viales cercanos, preservando sentidos de circulación y usando nodos virtuales por consulta (sin modificar el grafo principal). La geometría del recorrido se inicia/termina en el tramo, no en un cruce lejano. Se incluye un recargo estimativo por distancia desde la marca al eje de la calle, pero **el acceso real desde el marcador, entradas de estacionamientos y vías separadas por medianas no están verificados**. El límite de aceptación continúa siendo 1300 m, aunque conviene elegir puntos sobre calles.
- **Paradas:** hasta 5, origen y destino fijos. La optimización de orden utiliza programación dinámica Held–Karp, con tiempos modelados a una misma hora de salida (no actualiza factores horario durante el recorrido).
- **Mapa y búsqueda:** se obtienen online. Los mosaicos OpenStreetMap requieren conexión y atribución. Búsqueda Nominatim solo tras pulsar Buscar/Enter, con límite de 1 consulta/segundo a nivel de aplicación y caché en memoria; para servicio público/comercial debe sustituirse por una opción con capacidad y términos adecuados.
- **No es navegación GPS en tiempo real** y no sustituye indicaciones viales oficiales.

## 4. Archivos de interés académico

| Archivo | Responsabilidad / contenido de clase |
| --- | --- |
| `grafo.py` | `Vertex`, `Graph`, `NodoArista`, referencias `next`; lista enlazada de adyacencia y restricciones verificadas |
| `dijkstra.py` | Dijkstra propio con estado de arista, cola `heapq`, rutas por tiempo o distancia |
| `trafico.py` | Funciones, condicionales, vectores de orientación y demora por giro según horario |
| `paradas.py` | Programación dinámica, matrices, máscaras de bits y optimización del orden |
| `mapas.py` | Conversión de la red real OSMnx hacia nuestro grafo enlazado; pruebas sintéticas |
| `ajuste.py` | Índice espacial y conexión temporal de marcadores a tramos dirigidos |
| `app.py` | Controladores web Flask, excepciones, validación, coordinación de módulos |
| `geocodificacion.py` | Búsqueda bajo demanda, caché y control de frecuencia |
| `templates/index.html` | Interfaz web |
| `static/css/style.css` | Diseño responsive |
| `static/js/mapa.js` | Mapas, marcadores y comunicación HTTP con Flask |
| `tests/` | Pruebas unitarias/integración sin Internet |

### Temas adicionales al grafo incorporados

- **Lista enlazada:** adyacencia de aristas con `next`.
- **Cola de prioridad:** Dijkstra usa `heapq` (biblioteca estándar).
- **Programación dinámica:** optimización del orden de múltiples paradas (algoritmo Held–Karp).
- **Búsqueda y eficiencia:** Dijkstra con estado de la arista de llegada; índice espacial para hallar segmentos; complejidad en comentarios.
- **Archivos:** caché persistente en formato GraphML.
- **Validaciones y excepciones:** coordenadas, paradas y errores de red.
- **Pruebas automáticas:** `pytest`.

## 5. Pruebas

Con `.venv` activado:

```bat
python -m pytest -q
```

Las pruebas no descargan calles de Internet: usan grafos de prueba creados con `Graph`. La versión 1.2 agrega pruebas de ajuste a tramos, sentido único, penalización de retornos y restricciones verificadas.

## 6. Licencias y fuentes

- Datos geográficos © contribuyentes OpenStreetMap, licencia ODbL: https://www.openstreetmap.org/copyright
- Mosaicos OpenStreetMap: https://operations.osmfoundation.org/policies/tiles/
- Nominatim: https://operations.osmfoundation.org/policies/nominatim/
- OSMnx: https://osmnx.readthedocs.io/
- Leaflet: https://leafletjs.com/

**Uso académico local**. Para publicar un producto comercial es necesario evaluar cobertura, licencias, límites de servicios externos, calidad de datos y pruebas sobre viajes medidos.
