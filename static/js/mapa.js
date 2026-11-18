/* RouteFlow V1.2 · Interfaz Leaflet.
 * El navegador NO calcula rutas: solicita a Python y dibuja su respuesta.
 * Solo se consulta el buscador Nominatim al presionar Buscar/Enter.
 */
(() => {
  "use strict";
  const config = window.ROUTEFLOW_CONFIG;
  const $ = (id) => document.getElementById(id);
  const estado = {origen: null, destino: null, paradas: [], modo: "origen",
                  estadoRed: "sin_iniciar", red: null, ruta: null};
  let mapa = null;
  let marcadores = [];
  let capasRuta = [];
  let timerToast = null;
  let consultaEnMarcha = false;
  let ultimaCarga = "";

  function aviso(texto, error = false) {
    const nodo = $("toast");
    nodo.textContent = texto;
    nodo.classList.toggle("error", error);
    nodo.hidden = false;
    clearTimeout(timerToast);
    timerToast = setTimeout(() => { nodo.hidden = true; }, 5600);
  }

  async function api(url, opciones = {}) {
    let respuesta;
    try {
      respuesta = await fetch(url, {cache: "no-store", ...opciones});
    } catch (_) {
      throw new Error("No se pudo conectar con Python. Verifica que app.py esté ejecutándose.");
    }
    let datos;
    try { datos = await respuesta.json(); }
    catch (_) { throw new Error("La respuesta del servidor no fue válida."); }
    if (!respuesta.ok) throw new Error(datos.error || "Ocurrió un problema inesperado.");
    return datos;
  }

  function post(url, datos) {
    return api(url, {method: "POST", headers: {"Content-Type": "application/json"},
                     body: JSON.stringify(datos)});
  }

  function resumirNombre(nombre, max = 42) {
    const corto = String(nombre || "Punto seleccionado").split(",")[0].trim();
    return corto.length > max ? corto.slice(0, max - 1) + "…" : corto;
  }

  function etiquetaCoordenada(lat, lon) {
    return `${Number(lat).toFixed(5)}, ${Number(lon).toFixed(5)}`;
  }

  function cambiarModo(modo) {
    estado.modo = modo;
    $("btn-origen").classList.toggle("active", modo === "origen");
    $("btn-destino").classList.toggle("active", modo === "destino");
    const titulos = {
      origen: ["Para tu origen", "Haz clic en el mapa para colocar tu origen"],
      destino: ["Para tu destino", "Haz clic en el mapa para marcar tu destino"],
      parada: ["Para una nueva parada", "Haz clic en el mapa para añadir una parada"],
      idle: ["Para la próxima parada", "Modifica un punto o añade una parada cuando quieras"]
    };
    $("objetivo-busqueda").textContent = titulos[modo][0];
    $("tip-texto").textContent = titulos[modo][1];
    $("busqueda").placeholder = modo === "idle" ? "Busca tu próxima parada" : "Busca una calle o un lugar";
  }

  function limpiarRuta() {
    estado.ruta = null;
    $("resultado-ruta").hidden = true;
    $("mostrar-corta").checked = false;
    capasRuta.forEach((capa) => { if (mapa) mapa.removeLayer(capa); });
    capasRuta = [];
    $("leyenda-corta").hidden = true;
  }

  function ponerPunto(lat, lon, nombre) {
    const punto = {lat: Number(lat), lon: Number(lon), nombre: nombre || etiquetaCoordenada(lat, lon)};
    if (estado.modo === "origen") {
      estado.origen = punto;
      cambiarModo("destino");
    } else if (estado.modo === "destino") {
      estado.destino = punto;
      cambiarModo("idle");
    } else if (estado.modo === "parada" || estado.modo === "idle") {
      if (estado.paradas.length >= config.maxParadas) {
        aviso(`El máximo permitido es ${config.maxParadas} paradas.`, true);
        return;
      }
      estado.paradas.push(punto);
      cambiarModo("idle");
    }
    limpiarRuta();
    mostrarPuntos();
    $("resultados-busqueda").hidden = true;
    $("busqueda").value = "";
  }

  function icono(tipo, numero) {
    const texto = tipo === "origin" ? "A" : tipo === "dest" ? "B" : numero;
    return L.divIcon({className: "", iconSize: [32, 38], iconAnchor: [16, 36],
      html: `<div class="route-pin ${tipo}"><span>${texto}</span></div>`});
  }

  function marcador(punto, tipo, indice) {
    const marca = L.marker([punto.lat, punto.lon], {icon: icono(tipo, indice + 1), draggable: true})
      .addTo(mapa).bindTooltip(punto.nombre, {direction: "top", offset: [0, -28]});
    marca.on("dragend", () => {
      const posicion = marca.getLatLng();
      const nuevo = {lat: posicion.lat, lon: posicion.lng,
                     nombre: etiquetaCoordenada(posicion.lat, posicion.lng)};
      if (tipo === "origin") estado.origen = nuevo;
      else if (tipo === "dest") estado.destino = nuevo;
      else estado.paradas[indice] = nuevo;
      limpiarRuta();
      mostrarPuntos();
    });
    marcadores.push(marca);
  }

  function mostrarPuntos() {
    $("texto-origen").textContent = estado.origen ? resumirNombre(estado.origen.nombre) : "¿Desde dónde sales?";
    $("texto-destino").textContent = estado.destino ? resumirNombre(estado.destino.nombre) : "¿A dónde quieres llegar?";
    $("contador-paradas").textContent = `${estado.paradas.length}/${config.maxParadas}`;
    $("btn-agregar").disabled = estado.paradas.length >= config.maxParadas;
    const contenedor = $("lista-paradas");
    contenedor.replaceChildren();
    if (!estado.paradas.length) {
      const vacio = document.createElement("p");
      vacio.className = "empty-stops";
      vacio.textContent = "Sin paradas intermedias por ahora.";
      contenedor.appendChild(vacio);
    }
    estado.paradas.forEach((parada, indice) => {
      const fila = document.createElement("div"); fila.className = "stop-row";
      const numero = document.createElement("span"); numero.className = "stop-number";
      numero.textContent = String(indice + 1);
      const titulo = document.createElement("span"); titulo.className = "stop-title";
      titulo.textContent = resumirNombre(parada.nombre);
      titulo.title = parada.nombre;
      const quitar = document.createElement("button");
      quitar.type = "button"; quitar.textContent = "×";
      quitar.title = "Quitar parada";
      quitar.setAttribute("aria-label", `Quitar parada ${indice + 1}`);
      quitar.addEventListener("click", () => {
        estado.paradas.splice(indice, 1);
        limpiarRuta(); mostrarPuntos();
      });
      fila.append(numero, titulo, quitar);
      contenedor.appendChild(fila);
    });
    if (mapa) {
      marcadores.forEach((m) => mapa.removeLayer(m)); marcadores = [];
      if (estado.origen) marcador(estado.origen, "origin", 0);
      estado.paradas.forEach((p, i) => marcador(p, "stop", i));
      if (estado.destino) marcador(estado.destino, "dest", 0);
    }
    $("btn-calcular").disabled = !estado.origen || !estado.destino || estado.estadoRed !== "listo";
  }

  function estadoVisual(datos) {
    estado.estadoRed = datos.estado;
    estado.red = datos.modo;
    const caja = $("estado-red");
    caja.classList.toggle("loading", datos.estado === "cargando");
    caja.classList.toggle("error", datos.estado === "error");
    caja.classList.toggle("demo", datos.estado === "listo" && datos.modo === "demo");
    $("texto-estado").textContent = datos.mensaje || "Esperando estado de la red.";
    const icono = caja.querySelector(".status-icon");
    if (datos.estado === "cargando") icono.innerHTML = '<span class="status-spinner"></span>';
    else if (datos.estado === "listo") icono.textContent = datos.modo === "demo" ? "!" : "✓";
    else if (datos.estado === "error") icono.textContent = "!";
    else icono.textContent = "…";
    $("titulo-estado").textContent = datos.estado === "listo"
      ? (datos.modo === "demo" ? "Simulación lista" : "Calles de Managua listas")
      : datos.estado === "error" ? "No se pudieron cargar las calles"
      : "Preparando Managua";
    $("btn-reintentar").hidden = datos.estado !== "error";
    $("red-actions").hidden = datos.estado !== "error" && datos.estado !== "listo";
    $("btn-demo").hidden = datos.modo === "demo" && datos.estado === "listo";
    $("btn-real").hidden = !(datos.modo === "demo" && datos.estado === "listo");
    $("demo-banner").hidden = !(datos.estado === "listo" && datos.modo === "demo");
    $("map-red-label").textContent = datos.estado === "listo"
      ? (datos.modo === "demo" ? "Red ficticia para pruebas" : `${(datos.nodos || 0).toLocaleString("es-NI")} nodos reales`)
      : datos.estado === "error" ? "Red no disponible" : "Preparando red vial";
    document.querySelector(".tiny-live").classList.toggle("ready", datos.estado === "listo");
    document.querySelector(".tiny-live").classList.toggle("problem", datos.estado === "error");
    const hayCambio = estado.estadoRed === "listo" && ultimaCarga !== datos.modo;
    if (hayCambio) {
      limpiarRuta();
      ultimaCarga = datos.modo;
      if (mapa && datos.modo === "demo") mapa.fitBounds([[12.096, -86.313], [12.138, -86.250]], {padding: [25,25]});
      else if (mapa) mapa.setView(config.centro, 12);
    }
    mostrarPuntos();
  }

  async function consultarEstado() {
    try { estadoVisual(await api("/api/estado")); }
    catch (error) { $("texto-estado").textContent = error.message; }
  }

  async function preparar(modo = "real", forzar = false) {
    try {
      estadoVisual(await post("/api/preparar", {modo, forzar}));
    } catch (error) { aviso(error.message, true); }
  }

  async function buscarLugar() {
    const q = $("busqueda").value.trim();
    if (consultaEnMarcha) return;
    if (q.length < 3) { aviso("Escribe al menos 3 caracteres para buscar.", true); return; }
    consultaEnMarcha = true;
    $("btn-buscar").disabled = true;
    $("btn-buscar").textContent = "…";
    try {
      const datos = await api(`/api/buscar?q=${encodeURIComponent(q)}`);
      const contenedor = $("resultados-busqueda");
      contenedor.replaceChildren();
      if (!datos.lugares.length) {
        const vacio = document.createElement("p");
        vacio.className = "search-empty";
        vacio.textContent = "No hubo resultados dentro del área. Prueba otro nombre o haz clic en el mapa.";
        contenedor.appendChild(vacio);
      }
      datos.lugares.forEach((lugar) => {
        const boton = document.createElement("button");
        boton.type = "button"; boton.className = "search-result-item";
        const icono = document.createElement("i"); icono.textContent = "⌖";
        const nombre = document.createElement("span"); nombre.textContent = lugar.nombre;
        boton.append(icono, nombre);
        boton.addEventListener("click", () => {
          if (estado.modo === "idle") cambiarModo("parada");
          ponerPunto(lugar.lat, lugar.lon, lugar.nombre);
          if (mapa) mapa.setView([lugar.lat, lugar.lon], 15);
        });
        contenedor.appendChild(boton);
      });
      contenedor.hidden = false;
    } catch (error) { aviso(error.message, true); }
    finally { consultaEnMarcha = false; $("btn-buscar").disabled = false; $("btn-buscar").textContent = "Buscar"; }
  }

  function dibujarRutas(datos) {
    capasRuta.forEach((capa) => mapa.removeLayer(capa)); capasRuta = [];
    const verCorta = $("mostrar-corta").checked;
    if (verCorta) {
      datos.referencia_distancia.tramos.forEach((coordenadas) => {
        const capa = L.polyline(coordenadas, {color: "#f2a534", weight: 5,
                opacity: .95, dashArray: "8 9", lineCap: "round"}).addTo(mapa);
        capasRuta.push(capa);
      });
    }
    datos.tramos.forEach((tramo) => {
      const sombra = L.polyline(tramo.coordenadas, {color: "#fff", weight: 10,
                                                     opacity: .95, lineJoin: "round"}).addTo(mapa);
      const camino = L.polyline(tramo.coordenadas, {color: "#3868f0", weight: 6,
                          opacity: .94, lineCap: "round", lineJoin: "round"}).addTo(mapa);
      capasRuta.push(sombra, camino);
    });
    $("leyenda-corta").hidden = !verCorta;
    const puntos = datos.tramos.flatMap((tramo) => tramo.coordenadas);
    if (puntos.length > 1) mapa.fitBounds(L.latLngBounds(puntos), {padding: [70, 70], maxZoom: 15});
  }

  function presentarRuta(datos) {
    estado.ruta = datos;
    $("resultado-ruta").hidden = false;
    $("tiempo-principal").textContent = datos.minutos.toLocaleString("es-NI", {maximumFractionDigits: 1});
    $("distancia-principal").textContent = datos.km.toLocaleString("es-NI", {maximumFractionDigits: 2});
    $("semaforos-principal").textContent = datos.semaforos;
    const horaManagua = new Date(datos.salida).toLocaleTimeString("es-NI", {hour: "2-digit", minute: "2-digit", timeZone: "America/Managua"});
    $("perfil-trafico").textContent = `${datos.franja} · ${horaManagua}`;
    $("advertencia-ruta").textContent = datos.advertencia + " Los puntos se ajustan a tramos viales cercanos (el acceso exacto no se verifica); los semáforos dependen de las etiquetas de OSM.";
    const ol = $("orden-final"); ol.replaceChildren();
    datos.puntos.forEach((p, i) => {
      const li = document.createElement("li");
      const num = document.createElement("span"); num.textContent = String(i + 1);
      const texto = document.createElement("div"); texto.textContent = resumirNombre(p.nombre, 55);
      li.append(num, texto); ol.appendChild(li);
    });
    const dif = datos.referencia_distancia.minutos - datos.minutos;
    $("comparacion").replaceChildren();
    const comparacion = document.createElement("span");
    comparacion.textContent = `Ruta más corta: ${datos.referencia_distancia.km} km · ${datos.referencia_distancia.minutos} min`;
    const diferencia = document.createElement("strong");
    diferencia.textContent = dif > 0.05 ? ` · Ahorras ≈ ${dif.toFixed(1)} min al priorizar el tiempo.`
      : " · Coinciden aproximadamente en tiempo.";
    $("comparacion").append(comparacion, diferencia);
    dibujarRutas(datos);
    $("resultado-ruta").scrollIntoView({behavior: "smooth", block: "nearest"});
  }

  async function calcularRuta() {
    if (!estado.origen || !estado.destino) {
      aviso("Selecciona origen y destino para continuar.", true); return;
    }
    if (estado.estadoRed !== "listo") {
      aviso("La red vial aún no está lista.", true); return;
    }
    const ahora = $("salir-ahora").checked;
    const salida = ahora ? "ahora" : $("hora-personalizada").value;
    if (!ahora && !salida) { aviso("Selecciona una hora de salida válida.", true); return; }
    $("loading-overlay").hidden = false;
    $("btn-calcular").disabled = true;
    try {
      const datos = await post("/api/ruta", {
        origen: estado.origen, destino: estado.destino, paradas: estado.paradas,
        ordenar: $("orden-optimo").checked, salida
      });
      presentarRuta(datos);
    } catch (error) { aviso(error.message, true); }
    finally { $("loading-overlay").hidden = true; mostrarPuntos(); }
  }

  function inicializarMapa() {
    if (typeof window.L === "undefined") {
      $("map").innerHTML = '<div style="padding:100px 25px;color:#496277;text-align:center;line-height:1.6"><h3>El mapa necesita conexión a Internet</h3><p>No se pudo cargar Leaflet. Comprueba tu conexión y actualiza la página.</p></div>';
      aviso("No se pudo cargar Leaflet desde Internet.", true);
      return;
    }
    mapa = L.map("map", {zoomControl: true, preferCanvas: true}).setView(config.centro, 12);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'
    }).addTo(mapa);
    const b = config.bbox;
    L.rectangle([[b[1], b[0]], [b[3], b[2]]], {color: "#7192dd", fillOpacity: .015,
      dashArray: "6 6", weight: 1.2, opacity: .55, interactive: false}).addTo(mapa);
    mapa.on("click", (evento) => {
      if (estado.modo === "idle") return;
      ponerPunto(evento.latlng.lat, evento.latlng.lng);
    });
    mostrarPuntos();
  }

  function inicializarEventos() {
    $("btn-origen").addEventListener("click", () => cambiarModo("origen"));
    $("btn-destino").addEventListener("click", () => cambiarModo("destino"));
    $("btn-agregar").addEventListener("click", () => {
      if (estado.paradas.length < config.maxParadas) cambiarModo("parada");
    });
    $("btn-buscar").addEventListener("click", buscarLugar);
    $("busqueda").addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); buscarLugar(); }
    });
    $("salir-ahora").addEventListener("change", () => {
      $("hora-contenedor").hidden = $("salir-ahora").checked;
      limpiarRuta();
    });
    $("hora-personalizada").addEventListener("change", limpiarRuta);
    $("orden-optimo").addEventListener("change", limpiarRuta);
    $("orden-fijo").addEventListener("change", limpiarRuta);
    $("btn-calcular").addEventListener("click", calcularRuta);
    $("mostrar-corta").addEventListener("change", () => {
      if (estado.ruta && mapa) dibujarRutas(estado.ruta);
    });
    $("btn-demo").addEventListener("click", () => preparar("demo"));
    $("btn-real").addEventListener("click", () => preparar("real"));
    $("btn-reintentar").addEventListener("click", () => preparar("real", true));
    const ahora = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    $("hora-personalizada").value = `${ahora.getFullYear()}-${pad(ahora.getMonth()+1)}-${pad(ahora.getDate())}T${pad(ahora.getHours())}:${pad(ahora.getMinutes())}`;
  }

  inicializarEventos();
  inicializarMapa();
  cambiarModo("origen");
  consultarEstado().then(() => preparar("real"));
  setInterval(consultarEstado, 3000);
})();
