/* =========================================================
   GTC Stock — Script commun
   -----------------------------------------------------------
   IMPORTANT (sécurité) :
   Ce script gère uniquement le confort d'utilisation côté
   navigateur (affichage, validation de forme). Il ne réalise
   AUCUNE vérification fiable : le JavaScript côté client peut
   toujours être désactivé, modifié ou contourné par
   l'utilisateur. Il ne remplace jamais une validation et une
   sécurisation côté serveur (voir README.txt, section
   "Sécurité").
   ========================================================= */

document.addEventListener("DOMContentLoaded", function () {

  // ---- 1. Afficher / masquer le mot de passe ----
  document.querySelectorAll("[data-toggle-password]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = document.querySelector(btn.getAttribute("data-toggle-password"));
      if (!input) return;
      var showing = input.type === "text";
      input.type = showing ? "password" : "text";
      btn.querySelector("i").className = showing ? "bi bi-eye" : "bi bi-eye-slash";
    });
  });

  // ---- 2. Indicateur visuel (basique) de force du mot de passe ----
  // Sert uniquement à guider l'utilisateur ; la robustesse réelle
  // du mot de passe doit de toute façon être re-vérifiée côté serveur.
  var pwdInput = document.querySelector("[data-pwd-strength]");
  if (pwdInput) {
    var bar = document.querySelector(".pwd-strength-bar");
    pwdInput.addEventListener("input", function () {
      var val = pwdInput.value;
      var score = 0;
      if (val.length >= 8) score++;
      if (/[A-Z]/.test(val)) score++;
      if (/[0-9]/.test(val)) score++;
      if (/[^A-Za-z0-9]/.test(val)) score++;

      var pct = (score / 4) * 100;
      var colors = ["#e74c3c", "#e67e22", "#f1c40f", "#27ae60"];
      bar.style.width = pct + "%";
      bar.style.background = colors[Math.max(score - 1, 0)];
    });
  }

  // ---- 3. Validation Bootstrap côté client (confort uniquement) ----
  document.querySelectorAll("form[data-validate]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add("was-validated");
    }, false);
  });

  // ---- 4. Vérification "les deux mots de passe correspondent" ----
  var pwd1 = document.querySelector("[data-pwd-original]");
  var pwd2 = document.querySelector("[data-pwd-confirm]");
  if (pwd1 && pwd2) {
    function checkMatch() {
      if (pwd2.value && pwd1.value !== pwd2.value) {
        pwd2.setCustomValidity("Les mots de passe ne correspondent pas.");
      } else {
        pwd2.setCustomValidity("");
      }
    }
    pwd1.addEventListener("input", checkMatch);
    pwd2.addEventListener("input", checkMatch);
  }

});
