const menuPrincipal = document.getElementById("menuPrincipal");
const tipoCuenta = document.getElementById("tipo");
const empresaFields = document.getElementById("empresaFields");

function irRegistro() {
    document.getElementById("registro").scrollIntoView({
        behavior: "smooth"
    });
    cerrarMenu();
}

function irLogin() {
    window.location.href = "login.html";
}

function seleccionarTipo(tipo) {
    tipoCuenta.value = tipo;
    actualizarFormularioCuenta();
    irRegistro();
}

function toggleMenu() {
    menuPrincipal.classList.toggle("abierto");
}

function cerrarMenu() {
    menuPrincipal.classList.remove("abierto");
}

function actualizarFormularioCuenta() {
    const esEmpresa = tipoCuenta.value === "empresa";
    empresaFields.hidden = !esEmpresa;

    empresaFields.querySelectorAll("input").forEach(input => {
        input.required = esEmpresa;
    });
}

function obtenerDatosEmpresa() {
    if (tipoCuenta.value !== "empresa") {
        return null;
    }

    return {
        razonSocial: document.getElementById("razonSocial").value.trim(),
        identificacionFiscal: document.getElementById("identificacionFiscal").value.trim(),
        sector: document.getElementById("sector").value.trim(),
        telefono: document.getElementById("telefonoEmpresa").value.trim(),
        sitioWeb: document.getElementById("sitioWeb").value.trim(),
        representante: document.getElementById("representante").value.trim(),
        cargoRepresentante: document.getElementById("cargoRepresentante").value.trim()
    };
}

async function registrar() {
    const nombre = document.getElementById("nombre").value.trim();
    const correo = document.getElementById("correo").value.trim().toLowerCase();
    const tipo = tipoCuenta.value;
    const password = document.getElementById("password").value.trim();
    const mensaje = document.getElementById("mensaje");

    appApi.clearMessage(mensaje);

    try {
        await appApi.request("/api/register", {
            method: "POST",
            body: {
                nombre,
                correo,
                tipo,
                password,
                empresa: obtenerDatosEmpresa()
            }
        });

        appApi.setMessage(mensaje, "Cuenta creada correctamente. Redirigiendo al panel...", "success");

        setTimeout(() => {
            window.location.href = "dashboard.html";
        }, 1200);
    } catch (error) {
        appApi.setMessage(mensaje, error.message, "error");
    }
}

tipoCuenta.addEventListener("change", actualizarFormularioCuenta);

document.addEventListener("click", event => {
    if (!menuPrincipal.contains(event.target)) {
        cerrarMenu();
    }
});

actualizarFormularioCuenta();
