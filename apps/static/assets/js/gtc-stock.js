/* =========================================================
   GTC Stock — Script commun
   -----------------------------------------------------------
   IMPORTANT (sécurité) :
   Ce script gère uniquement le confort d'utilisation côté
   navigateur (affichage, validation de forme). Il ne réalise
   AUCUNE vérification fiable : le JavaScript côté client peut
   toujours être désactivé, modifié ou contourné par
   l'utilisateur. Il ne remplace jamais une validation et une
   sécurisation côté serveur.
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

  // ---- 5. Recherche d'article avec autocomplétion (type-ahead) ----
  // Remplace les listes déroulantes <select> d'article (impraticables dès
  // que le catalogue grandit) par un champ de recherche : quelques
  // lettres de la référence ou de la désignation suffisent, au plus 10
  // suggestions apparaissent (voir apps/templates/includes/article-picker.html
  // pour le balisage attendu, et la route /pages/articles/recherche —
  // elle-même limitée à 10 résultats et déjà filtrée par magasin côté
  // serveur — jamais tout le catalogue chargé d'un coup).
  document.querySelectorAll("[data-article-picker]").forEach(function (racine) {
    var champTexte = racine.querySelector("[data-article-picker-input]");
    var champValeur = racine.querySelector("[data-article-picker-value]");
    var listeSuggestions = racine.querySelector("[data-article-picker-suggestions]");
    if (!champTexte || !champValeur || !listeSuggestions) return;

    var idSourceMagasin = racine.getAttribute("data-magasin-source-input");
    var selectMagasinSource = idSourceMagasin ? document.getElementById(idSourceMagasin) : null;

    var minuteur = null;
    var requeteEnCours = 0;
    var elementsSuggeres = [];
    var indexActif = -1;

    function magasinCourant() {
      return selectMagasinSource ? selectMagasinSource.value : "";
    }

    function viderSelection() {
      champValeur.value = "";
    }

    function fermerSuggestions() {
      listeSuggestions.style.display = "none";
      listeSuggestions.innerHTML = "";
      elementsSuggeres = [];
      indexActif = -1;
    }

    function surSurbrillance() {
      elementsSuggeres.forEach(function (el, i) {
        el.classList.toggle("active", i === indexActif);
      });
    }

    function choisirArticle(article) {
      champValeur.value = article.id;
      champTexte.value = article.nom + " — " + article.reference;
      fermerSuggestions();
    }

    function afficherSuggestions(articles) {
      listeSuggestions.innerHTML = "";
      elementsSuggeres = [];
      indexActif = -1;
      if (!articles.length) {
        var vide = document.createElement("div");
        vide.className = "list-group-item text-muted small";
        vide.textContent = "Aucun article trouvé.";
        listeSuggestions.appendChild(vide);
      } else {
        articles.forEach(function (article) {
          var item = document.createElement("button");
          item.type = "button";
          item.className = "list-group-item list-group-item-action";
          item.textContent = article.nom + " — " + article.reference + " (" + article.quantite + " en stock)";
          // mousedown (pas click) : se déclenche avant le blur du champ
          // texte, qui sinon fermerait les suggestions en premier.
          item.addEventListener("mousedown", function (event) {
            event.preventDefault();
            choisirArticle(article);
          });
          listeSuggestions.appendChild(item);
          elementsSuggeres.push(item);
        });
      }
      listeSuggestions.style.display = "block";
    }

    function rechercher(terme) {
      var url = "/pages/articles/recherche?q=" + encodeURIComponent(terme);
      var magasinId = magasinCourant();
      if (magasinId) url += "&magasin_id=" + encodeURIComponent(magasinId);
      var requete = ++requeteEnCours;
      fetch(url)
        .then(function (reponse) { return reponse.ok ? reponse.json() : []; })
        .then(function (articles) {
          // Ignore une réponse devenue obsolète (une saisie plus récente
          // a déjà déclenché une nouvelle recherche entre-temps).
          if (requete === requeteEnCours) afficherSuggestions(articles);
        })
        .catch(function () { fermerSuggestions(); });
    }

    champTexte.addEventListener("input", function () {
      viderSelection();
      var terme = champTexte.value.trim();
      clearTimeout(minuteur);
      if (!terme || (selectMagasinSource && !magasinCourant())) {
        fermerSuggestions();
        return;
      }
      minuteur = setTimeout(function () { rechercher(terme); }, 200);
    });

    champTexte.addEventListener("keydown", function (event) {
      if (!elementsSuggeres.length) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        indexActif = Math.min(indexActif + 1, elementsSuggeres.length - 1);
        surSurbrillance();
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        indexActif = Math.max(indexActif - 1, 0);
        surSurbrillance();
      } else if (event.key === "Enter") {
        // Empêche une soumission accidentelle du formulaire tant que la
        // sélection n'est pas explicite (au clavier ou à la souris).
        event.preventDefault();
        var cible = indexActif >= 0 ? elementsSuggeres[indexActif] : (
          elementsSuggeres.length === 1 ? elementsSuggeres[0] : null
        );
        if (cible) cible.dispatchEvent(new Event("mousedown"));
      } else if (event.key === "Escape") {
        fermerSuggestions();
      }
    });

    champTexte.addEventListener("blur", function () {
      // Léger délai : laisse le mousedown d'une suggestion s'exécuter
      // avant de fermer la liste (sinon le blur la ferme en premier).
      setTimeout(fermerSuggestions, 150);
    });

    if (selectMagasinSource) {
      function majDisponibilite() {
        var disponible = !!magasinCourant();
        champTexte.disabled = !disponible;
        champTexte.placeholder = disponible
          ? "Rechercher un article (référence ou désignation)…"
          : "Choisissez d'abord le magasin source";
        if (!disponible) {
          champTexte.value = "";
          viderSelection();
          fermerSuggestions();
        }
      }
      selectMagasinSource.addEventListener("change", majDisponibilite);
      majDisponibilite();
    }
  });

  // ---- 6. Bascule de blocs de champs selon un type choisi ----
  // Générique : affiche/masque le bloc de champs pertinent selon la
  // valeur d'un <select> — utilisé par « Type d'entrée » (entrees.html)
  // et « Type de sortie » (sorties.html), sur le même principe. Marquage
  // attendu (dans le même <form> que le sélecteur) :
  //   <select data-type-toggle-select> ... </select>
  //   <div data-type-toggle-groupe="valeur-de-option">
  //     <input data-type-toggle-champ required> <!-- rendu obligatoire
  //       seulement quand ce bloc est actif -->
  //   </div>
  // Désactiver (pas seulement masquer) les champs du bloc inactif évite
  // qu'ils soient quand même soumis, et retirer leur `required` évite
  // qu'ils bloquent la validation native du formulaire alors qu'ils sont
  // invisibles. Un champ de recherche d'article (voir section 5) présent
  // dans un bloc suit la même règle : son champ caché (article_id) et
  // son champ texte visible (`required` par défaut) sont eux aussi
  // désactivés avec le reste du bloc inactif.
  document.querySelectorAll("[data-type-toggle-select]").forEach(function (select) {
    var form = select.closest("form") || document;
    var groupes = form.querySelectorAll("[data-type-toggle-groupe]");
    if (!groupes.length) return;

    function majGroupes() {
      var valeur = select.value;
      groupes.forEach(function (groupe) {
        var actif = groupe.getAttribute("data-type-toggle-groupe") === valeur;
        groupe.hidden = !actif;
        groupe.querySelectorAll("[data-type-toggle-champ]").forEach(function (champ) {
          champ.disabled = !actif;
          if (actif) champ.setAttribute("required", "required");
          else champ.removeAttribute("required");
        });
        groupe.querySelectorAll("[data-article-picker-value], [data-article-picker-input]").forEach(function (champ) {
          champ.disabled = !actif;
        });
      });
    }
    select.addEventListener("change", majGroupes);
    majGroupes();
  });

  // ---- 7. Motif de régularisation : champ libre "Précisez" pour "Autre" ----
  // Générique elle aussi (entrees.html et sorties.html) : le <select> du
  // motif porte data-motif-regularisation="id-du-bloc-a-afficher".
  document.querySelectorAll("[data-motif-regularisation]").forEach(function (select) {
    var groupeAutre = document.getElementById(select.getAttribute("data-motif-regularisation"));
    if (!groupeAutre) return;
    var champAutre = groupeAutre.querySelector("input");

    function majAutre() {
      var affiche = select.value === "Autre";
      groupeAutre.hidden = !affiche;
      if (champAutre) champAutre.disabled = !affiche;
    }
    select.addEventListener("change", majAutre);
    majAutre();
  });

});
