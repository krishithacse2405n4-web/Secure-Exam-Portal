
const loginForm = document.getElementById("loginForm");
const message = document.getElementById("message");

loginForm.addEventListener("submit", async function(event) {
    event.preventDefault();

    message.textContent = "Checking credentials...";
    message.style.color = "#2877d3";

    const role = document.getElementById("role").value;
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    try {
        const response = await fetch("/api/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                role: role,
                email: email,
                password: password
            })
        });

        const data = await response.json();

        if (response.ok) {
            message.textContent = "Login successful! Redirecting...";
            message.style.color = "green";

            window.location.assign(data.redirect);
        } else {
            message.textContent = data.message || "Login failed.";
            message.style.color = "red";
        }

    } catch (error) {
        message.textContent = "Unable to connect to the server.";
        message.style.color = "red";
        console.error(error);
    }
});
