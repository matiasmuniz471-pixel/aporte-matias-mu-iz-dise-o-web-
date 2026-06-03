window.appApi = (() => {
    async function request(path, options = {}) {
        const fetchOptions = {
            method: options.method || "GET",
            credentials: "same-origin",
            headers: { ...(options.headers || {}) }
        };

        if (options.body !== undefined) {
            fetchOptions.headers["Content-Type"] = "application/json";
            fetchOptions.body = JSON.stringify(options.body);
        }

        const response = await fetch(path, fetchOptions);
        let data = {};

        try {
            data = await response.json();
        } catch (error) {
            data = {};
        }

        if (!response.ok) {
            throw new Error(data.message || "No fue posible completar la solicitud.");
        }

        return data;
    }

    function setMessage(element, text, type) {
        element.textContent = text;
        element.style.color = type === "success" ? "green" : "red";
    }

    function clearMessage(element) {
        element.textContent = "";
    }

    function accountLabel(tipo) {
        return tipo === "empresa" ? "Cuenta empresarial" : "Cuenta participante";
    }

    function formatDisplayDate(dateValue) {
        if (!dateValue) {
            return "";
        }

        const [year, month, day] = dateValue.split("-");
        if (!year || !month || !day) {
            return dateValue;
        }

        return `${day}/${month}/${year}`;
    }

    return {
        request,
        setMessage,
        clearMessage,
        accountLabel,
        formatDisplayDate
    };
})();
