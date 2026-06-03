async function verificarSesionActiva() {
    try {
        await appApi.request("/api/session");
        window.location.href = "dashboard.html";
    } catch (error) {
        return;
    }
}

async function iniciarSesion() {
    const correo = document.getElementById("loginCorreo").value.trim().toLowerCase();
    const password = document.getElementById("loginPassword").value.trim();
    const mensaje = document.getElementById("mensajeLogin");

    appApi.clearMessage(mensaje);

    try {
        await appApi.request("/api/login", {
            method: "POST",
            body: { correo, password }
        });

        appApi.setMessage(mensaje, "Inicio de sesión exitoso. Redirigiendo...", "success");

        setTimeout(() => {
            window.location.href = "dashboard.html";
        }, 900);
    } catch (error) {
        appApi.setMessage(mensaje, error.message, "error");
    }
}

verificarSesionActiva();
