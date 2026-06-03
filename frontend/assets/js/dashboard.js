let payloadActual = null;
let seccionActual = "inicio";

const panelSubtitulo = document.getElementById("panelSubtitulo");
const menuLinks = document.getElementById("menuLinks");
const dashboardContent = document.getElementById("dashboardContent");
const dashboardMessage = document.getElementById("dashboardMessage");
const nombreUsuario = document.getElementById("nombreUsuario");
const tipoCuentaUsuario = document.getElementById("tipoCuentaUsuario");
const letraUsuario = document.getElementById("letraUsuario");
const saludoUsuario = document.getElementById("saludoUsuario");
const descripcionPanel = document.getElementById("descripcionPanel");
const modoToggle = document.getElementById("modoToggle");

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function aplicarTemaGuardado() {
    if (localStorage.getItem("modo") === "oscuro") {
        document.body.classList.add("dark-mode");
        modoToggle.textContent = "Claro";
    }
}

function alternarTema() {
    document.body.classList.toggle("dark-mode");

    if (document.body.classList.contains("dark-mode")) {
        localStorage.setItem("modo", "oscuro");
        modoToggle.textContent = "Claro";
        return;
    }

    localStorage.setItem("modo", "claro");
    modoToggle.textContent = "Oscuro";
}

function mostrarMensaje(texto, tipo = "success") {
    dashboardMessage.hidden = false;
    dashboardMessage.textContent = texto;
    dashboardMessage.className = `dashboard-message ${tipo}`;
}

function limpiarMensaje() {
    dashboardMessage.hidden = true;
    dashboardMessage.textContent = "";
}

function esEmpresa() {
    return payloadActual?.dashboardType === "empresa";
}

function menuPorRol() {
    if (esEmpresa()) {
        return [
            ["inicio", "Inicio"],
            ["seminarios", "Seminarios"],
            ["participantes", "Participantes"],
            ["estadisticas", "Estadisticas"],
            ["logout", "Cerrar sesion"]
        ];
    }

    return [
        ["inicio", "Inicio"],
        ["eventos", "Eventos disponibles"],
        ["inscripciones", "Mis inscripciones"],
        ["certificados", "Certificados"],
        ["logout", "Cerrar sesion"]
    ];
}

function renderMenu() {
    menuLinks.innerHTML = menuPorRol().map(([id, label]) => `
        <li class="${id === seccionActual ? "active" : ""}">
            <a href="#" data-section="${id}">${label}</a>
        </li>
    `).join("");
}

function renderUsuario() {
    const usuario = payloadActual.usuario;
    const cuenta = esEmpresa() ? "Cuenta empresarial" : "Cuenta participante";

    panelSubtitulo.textContent = esEmpresa() ? "Panel empresarial" : "Panel participante";
    nombreUsuario.textContent = usuario.nombre;
    tipoCuentaUsuario.textContent = cuenta;
    letraUsuario.textContent = usuario.nombre.charAt(0).toUpperCase();
    saludoUsuario.textContent = `Bienvenido, ${usuario.nombre}`;
    descripcionPanel.textContent = esEmpresa()
        ? "Administra seminarios, participantes y actividad de tu organizacion."
        : "Explora eventos, gestiona tus inscripciones y revisa tus certificados.";
}

function beneficioCards() {
    return `
        <section class="panel-section">
            <div class="title-box">
                <h2>Beneficios activos</h2>
            </div>
            <div class="beneficios-grid">
                ${(payloadActual.beneficios || []).map(beneficio => `
                    <div class="beneficio-card">${escapeHtml(beneficio)}</div>
                `).join("")}
            </div>
        </section>
    `;
}

function renderInicioEmpresa() {
    const perfil = payloadActual.perfilEmpresa;
    const perfilHtml = perfil ? `
        <div class="profile-data-grid">
            <div><span>Razon social</span><strong>${escapeHtml(perfil.razonSocial)}</strong></div>
            <div><span>RUC / ID fiscal</span><strong>${escapeHtml(perfil.identificacionFiscal)}</strong></div>
            <div><span>Sector</span><strong>${escapeHtml(perfil.sector)}</strong></div>
            <div><span>Telefono</span><strong>${escapeHtml(perfil.telefono)}</strong></div>
            <div><span>Sitio web</span><strong>${escapeHtml(perfil.sitioWeb)}</strong></div>
            <div><span>Contacto</span><strong>${escapeHtml(perfil.representante)} - ${escapeHtml(perfil.cargoRepresentante)}</strong></div>
        </div>
    ` : `
        <p class="empty-copy">Esta empresa fue creada antes de pedir datos extendidos. Registra una cuenta empresarial nueva para probar el formulario completo.</p>
    `;

    return `
        <section class="cards-grid">
            <div class="card"><h2>${payloadActual.estadisticas.totalSeminarios}</h2><p>Seminarios creados</p></div>
            <div class="card"><h2>${payloadActual.estadisticas.totalParticipantes}</h2><p>Participantes inscritos</p></div>
            <div class="card"><h2>Empresa</h2><p>Tipo de panel</p></div>
        </section>
        ${beneficioCards()}
        <section class="panel-section">
            <div class="title-box">
                <h2>Perfil empresarial</h2>
            </div>
            ${perfilHtml}
        </section>
    `;
}

function renderInicioCliente() {
    return `
        <section class="cards-grid">
            <div class="card"><h2>${payloadActual.estadisticas.totalEventos}</h2><p>Eventos disponibles</p></div>
            <div class="card"><h2>${payloadActual.estadisticas.totalInscripciones}</h2><p>Inscripciones activas</p></div>
            <div class="card"><h2>${payloadActual.estadisticas.totalCertificados}</h2><p>Certificados pendientes</p></div>
        </section>
        ${beneficioCards()}
    `;
}

function renderInicio() {
    dashboardContent.innerHTML = esEmpresa() ? renderInicioEmpresa() : renderInicioCliente();
}

function renderSeminariosEmpresa() {
    const seminarios = payloadActual.seminarios || [];
    const rows = seminarios.length ? seminarios.map(seminario => `
        <tr>
            <td>${escapeHtml(seminario.titulo)}</td>
            <td>${appApi.formatDisplayDate(seminario.fecha)}</td>
            <td>${escapeHtml(seminario.categoria)}</td>
            <td><span class="status active">Activo</span></td>
            <td>${seminario.participantes}</td>
            <td><button class="btn-delete" type="button" data-action="delete-seminar" data-id="${seminario.id}">Eliminar</button></td>
        </tr>
    `).join("") : `
        <tr><td colspan="6">No hay seminarios creados todavia.</td></tr>
    `;

    dashboardContent.innerHTML = `
        <div class="content-grid">
            <section class="create-box">
                <div class="title-box">
                    <h2>Crear seminario</h2>
                    <p>Publica eventos asociados a tu empresa.</p>
                </div>
                <input type="text" id="tituloSeminario" placeholder="Titulo">
                <input type="date" id="fechaSeminario">
                <select id="categoriaSeminario">
                    <option value="">Selecciona categoria</option>
                    <option value="Tecnologia">Tecnologia</option>
                    <option value="Marketing">Marketing</option>
                    <option value="Negocios">Negocios</option>
                    <option value="Educacion">Educacion</option>
                </select>
                <textarea id="descripcionSeminario" placeholder="Descripcion"></textarea>
                <button class="btn-create" type="button" data-action="create-seminar">Publicar seminario</button>
            </section>
            <section class="activity-box">
                <div class="title-box">
                    <h2>Actividad reciente</h2>
                </div>
                ${renderActividadEmpresa()}
            </section>
        </div>
        <section class="table-section">
            <div class="title-box">
                <h2>Mis seminarios</h2>
            </div>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Seminario</th>
                            <th>Fecha</th>
                            <th>Categoria</th>
                            <th>Estado</th>
                            <th>Participantes</th>
                            <th>Accion</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        </section>
    `;
}

function renderActividadEmpresa() {
    const actividad = payloadActual.actividad || [];
    if (!actividad.length) {
        return `
            <div class="activity-item">
                <h4>Sin actividad todavia</h4>
                <p>Crea tu primer seminario para ver movimientos recientes.</p>
            </div>
        `;
    }

    return actividad.map(item => `
        <div class="activity-item">
            <h4>${escapeHtml(item.titulo)}</h4>
            <p>${escapeHtml(item.detalle)}</p>
        </div>
    `).join("");
}

function renderParticipantesEmpresa() {
    const participantes = payloadActual.participantes || [];
    const rows = participantes.length ? participantes.map(participante => `
        <tr>
            <td>${escapeHtml(participante.nombre)}</td>
            <td>${escapeHtml(participante.correo)}</td>
            <td>${escapeHtml(participante.seminario)}</td>
            <td>${escapeHtml(participante.fechaUnion)}</td>
        </tr>
    `).join("") : `
        <tr><td colspan="4">Aun no hay participantes inscritos en tus seminarios.</td></tr>
    `;

    dashboardContent.innerHTML = `
        <section class="table-section">
            <div class="title-box">
                <h2>Participantes registrados</h2>
                <p>Solo aparecen personas inscritas en seminarios de tu empresa.</p>
            </div>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Nombre</th>
                            <th>Correo</th>
                            <th>Seminario</th>
                            <th>Fecha</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        </section>
    `;
}

function renderEstadisticasEmpresa() {
    dashboardContent.innerHTML = `
        <section class="cards-grid">
            <div class="card"><h2>${payloadActual.estadisticas.totalSeminarios}</h2><p>Seminarios</p></div>
            <div class="card"><h2>${payloadActual.estadisticas.totalParticipantes}</h2><p>Participantes</p></div>
            <div class="card"><h2>100%</h2><p>Datos propios de la empresa</p></div>
        </section>
    `;
}

function renderEventosCliente() {
    const eventos = payloadActual.eventosDisponibles || [];

    dashboardContent.innerHTML = `
        <section class="panel-section">
            <div class="title-box">
                <h2>Eventos disponibles</h2>
                <p>Elige seminarios creados por empresas registradas.</p>
            </div>
            <div class="event-grid">
                ${eventos.length ? eventos.map(evento => `
                    <article class="event-card">
                        <span>${escapeHtml(evento.categoria)}</span>
                        <h3>${escapeHtml(evento.titulo)}</h3>
                        <p>${escapeHtml(evento.descripcion)}</p>
                        <div class="event-meta">
                            <strong>${escapeHtml(evento.empresa)}</strong>
                            <small>${appApi.formatDisplayDate(evento.fecha)}</small>
                        </div>
                        <button class="btn-create" type="button" data-action="enroll" data-id="${evento.id}" ${evento.inscrito ? "disabled" : ""}>
                            ${evento.inscrito ? "Ya inscrito" : "Inscribirme"}
                        </button>
                    </article>
                `).join("") : `<p class="empty-copy">Todavia no hay eventos publicados por empresas.</p>`}
            </div>
        </section>
    `;
}

function renderInscripcionesCliente() {
    const inscripciones = payloadActual.inscripciones || [];
    const rows = inscripciones.length ? inscripciones.map(inscripcion => `
        <tr>
            <td>${escapeHtml(inscripcion.titulo)}</td>
            <td>${escapeHtml(inscripcion.empresa)}</td>
            <td>${appApi.formatDisplayDate(inscripcion.fecha)}</td>
            <td>${escapeHtml(inscripcion.fechaUnion)}</td>
            <td><span class="status active">Activa</span></td>
        </tr>
    `).join("") : `
        <tr><td colspan="5">Aun no tienes inscripciones activas.</td></tr>
    `;

    dashboardContent.innerHTML = `
        <section class="table-section">
            <div class="title-box">
                <h2>Mis inscripciones</h2>
            </div>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Seminario</th>
                            <th>Empresa</th>
                            <th>Fecha evento</th>
                            <th>Fecha inscripcion</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        </section>
    `;
}

function renderCertificadosCliente() {
    const certificados = payloadActual.certificados || [];

    dashboardContent.innerHTML = `
        <section class="panel-section">
            <div class="title-box">
                <h2>Certificados</h2>
                <p>Los certificados se mostraran como pendientes hasta completar el evento.</p>
            </div>
            <div class="event-grid">
                ${certificados.length ? certificados.map(certificado => `
                    <article class="event-card compact">
                        <span>${escapeHtml(certificado.estado)}</span>
                        <h3>${escapeHtml(certificado.titulo)}</h3>
                        <p>${escapeHtml(certificado.empresa)}</p>
                    </article>
                `).join("") : `<p class="empty-copy">Inscribete en un evento para empezar tu historial de certificados.</p>`}
            </div>
        </section>
    `;
}

function renderSeccion() {
    renderMenu();
    limpiarMensaje();

    if (seccionActual === "inicio") {
        renderInicio();
        return;
    }

    if (esEmpresa()) {
        if (seccionActual === "seminarios") renderSeminariosEmpresa();
        if (seccionActual === "participantes") renderParticipantesEmpresa();
        if (seccionActual === "estadisticas") renderEstadisticasEmpresa();
        return;
    }

    if (seccionActual === "eventos") renderEventosCliente();
    if (seccionActual === "inscripciones") renderInscripcionesCliente();
    if (seccionActual === "certificados") renderCertificadosCliente();
}

function hidratarDashboard(payload) {
    payloadActual = payload;
    renderUsuario();
    renderSeccion();
}

async function cargarDashboard() {
    try {
        const payload = await appApi.request("/api/dashboard");
        hidratarDashboard(payload);
    } catch (error) {
        window.location.href = "login.html";
    }
}

async function crearSeminario() {
    const titulo = document.getElementById("tituloSeminario").value.trim();
    const fecha = document.getElementById("fechaSeminario").value;
    const categoria = document.getElementById("categoriaSeminario").value;
    const descripcion = document.getElementById("descripcionSeminario").value.trim();

    try {
        const payload = await appApi.request("/api/seminarios", {
            method: "POST",
            body: { titulo, fecha, categoria, descripcion }
        });
        hidratarDashboard(payload);
        mostrarMensaje(payload.message, "success");
    } catch (error) {
        mostrarMensaje(error.message, "error");
    }
}

async function eliminarSeminario(id) {
    if (!confirm("Deseas eliminar este seminario?")) {
        return;
    }

    try {
        const payload = await appApi.request(`/api/seminarios/${id}`, {
            method: "DELETE"
        });
        hidratarDashboard(payload);
        mostrarMensaje(payload.message, "success");
    } catch (error) {
        mostrarMensaje(error.message, "error");
    }
}

async function inscribirse(seminarId) {
    try {
        const payload = await appApi.request("/api/inscripciones", {
            method: "POST",
            body: { seminarId }
        });
        hidratarDashboard(payload);
        mostrarMensaje(payload.message, "success");
    } catch (error) {
        mostrarMensaje(error.message, "error");
    }
}

async function cerrarSesionActual() {
    try {
        await appApi.request("/api/logout", { method: "POST" });
    } finally {
        window.location.href = "login.html";
    }
}

menuLinks.addEventListener("click", event => {
    const link = event.target.closest("[data-section]");
    if (!link) {
        return;
    }

    event.preventDefault();

    if (link.dataset.section === "logout") {
        cerrarSesionActual();
        return;
    }

    seccionActual = link.dataset.section;
    renderSeccion();
});

dashboardContent.addEventListener("click", event => {
    const actionButton = event.target.closest("[data-action]");
    if (!actionButton) {
        return;
    }

    if (actionButton.dataset.action === "create-seminar") {
        crearSeminario();
    }

    if (actionButton.dataset.action === "delete-seminar") {
        eliminarSeminario(actionButton.dataset.id);
    }

    if (actionButton.dataset.action === "enroll") {
        inscribirse(actionButton.dataset.id);
    }
});

modoToggle.addEventListener("click", alternarTema);

aplicarTemaGuardado();
cargarDashboard();
