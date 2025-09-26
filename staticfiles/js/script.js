

// Page d'inscription : toggle mot de passe et confirmation
function togglePassword() {
    const pwd1 = document.getElementById("id_password1");
    const pwd2 = document.getElementById("id_password2");

    if (pwd1) pwd1.type = pwd1.type === "password" ? "text" : "password";
    if (pwd2) pwd2.type = pwd2.type === "password" ? "text" : "password";
}