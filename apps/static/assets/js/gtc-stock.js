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

// Cœur commun des champs "recherche avec autocomplétion" (type-ahead) —
// utilisé aussi bien par le composant Article (includes/article-picker.html)
// que par le composant Fournisseur (includes/fournisseur-picker.html) :
// même comportement (suggestions, navigation clavier, sélection), seules
// l'URL de recherche et la mise en forme des résultats changent selon
// `options`. Hors de DOMContentLoaded : ne touche pas le DOM tant qu'on ne
// l'appelle pas, peut donc être défini avant que la page soit prête.
//   options.champTexte / champValeur / listeSuggestions : éléments DOM.
//   options.construireUrl(terme) -> URL de recherche.
//   options.texteSuggestion(item) -> libellé d'une ligne de suggestion.
//   options.texteChoisi(item) -> texte posé dans le champ après sélection.
//   options.estActif() (optionnel) -> le champ n'est utilisable que si vrai
//     (ex. tant qu'un magasin source n'est pas choisi) ; sans cette
//     option, le champ est toujours actif.
//   options.placeholderActif / placeholderInactif (si estActif fourni).
// Retourne { rafraichirDisponibilite } pour qu'un appelant externe
// notifie un changement de l'état d'`estActif()` (ex. au changement du
// magasin source). Émet aussi, sur `options.champTexte` lui-même (donc
// récupérable par son id, ou par délégation sur un ancêtre puisque
// l'évènement remonte), un évènement "picker:choix" (detail = l'item
// choisi) — pour qu'une page puisse réagir à une sélection sans dupliquer
// cette logique (voir entrees.html : affichage du fournisseur de
// l'article choisi).
function creerPickerRecherche(options) {
  var champTexte = options.champTexte;
  var champValeur = options.champValeur;
  var listeSuggestions = options.listeSuggestions;

  var minuteur = null;
  var requeteEnCours = 0;
  var elementsSuggeres = [];
  var indexActif = -1;

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

  function choisir(item) {
    champValeur.value = item.id;
    champTexte.value = options.texteChoisi(item);
    fermerSuggestions();
    champTexte.dispatchEvent(new CustomEvent("picker:choix", { detail: item, bubbles: true }));
  }

  function afficherSuggestions(items) {
    listeSuggestions.innerHTML = "";
    elementsSuggeres = [];
    indexActif = -1;
    if (!items.length) {
      var vide = document.createElement("div");
      vide.className = "list-group-item text-muted small";
      vide.textContent = "Aucun résultat.";
      listeSuggestions.appendChild(vide);
    } else {
      items.forEach(function (item) {
        var el = document.createElement("button");
        el.type = "button";
        el.className = "list-group-item list-group-item-action";
        el.textContent = options.texteSuggestion(item);
        // mousedown (pas click) : se déclenche avant le blur du champ
        // texte, qui sinon fermerait les suggestions en premier.
        el.addEventListener("mousedown", function (event) {
          event.preventDefault();
          choisir(item);
        });
        listeSuggestions.appendChild(el);
        elementsSuggeres.push(el);
      });
    }
    listeSuggestions.style.display = "block";
  }

  function estDisponible() {
    return !options.estActif || options.estActif();
  }

  function rechercher(terme) {
    var url = options.construireUrl(terme);
    var requete = ++requeteEnCours;
    fetch(url)
      .then(function (reponse) { return reponse.ok ? reponse.json() : []; })
      .then(function (items) {
        // Ignore une réponse devenue obsolète (une saisie plus récente a
        // déjà déclenché une nouvelle recherche entre-temps).
        if (requete === requeteEnCours) afficherSuggestions(items);
      })
      .catch(function () { fermerSuggestions(); });
  }

  function rafraichirDisponibilite() {
    if (!options.estActif) return;
    var disponible = estDisponible();
    champTexte.disabled = !disponible;
    champTexte.placeholder = disponible ? options.placeholderActif : options.placeholderInactif;
    if (!disponible) {
      champTexte.value = "";
      viderSelection();
      fermerSuggestions();
    }
  }

  champTexte.addEventListener("input", function () {
    viderSelection();
    var terme = champTexte.value.trim();
    clearTimeout(minuteur);
    if (!terme || !estDisponible()) {
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
    // Léger délai : laisse le mousedown d'une suggestion s'exécuter avant
    // de fermer la liste (sinon le blur la ferme en premier).
    setTimeout(fermerSuggestions, 150);
  });

  rafraichirDisponibilite();
  return { rafraichirDisponibilite: rafraichirDisponibilite };
}

// Initialise UN composant "recherche d'article" (voir
// apps/templates/includes/article-picker.html) — extrait en fonction
// nommée (plutôt qu'en corps de boucle inline) pour pouvoir aussi
// l'appeler sur une ligne ajoutée dynamiquement APRÈS le chargement de la
// page (voir section 11, bordereau de route : plusieurs lignes
// d'articles répétables). Hors de DOMContentLoaded comme
// creerPickerRecherche, pour la même raison : appelable dès que l'élément
// existe, pas seulement au chargement initial.
function initialiserArticlePicker(racine) {
  var champTexte = racine.querySelector("[data-article-picker-input]");
  var champValeur = racine.querySelector("[data-article-picker-value]");
  var listeSuggestions = racine.querySelector("[data-article-picker-suggestions]");
  if (!champTexte || !champValeur || !listeSuggestions) return;

  var idSourceMagasin = racine.getAttribute("data-magasin-source-input");
  var selectMagasinSource = idSourceMagasin ? document.getElementById(idSourceMagasin) : null;

  var picker = creerPickerRecherche({
    champTexte: champTexte,
    champValeur: champValeur,
    listeSuggestions: listeSuggestions,
    estActif: selectMagasinSource ? function () { return !!selectMagasinSource.value; } : null,
    placeholderActif: "Rechercher un article (référence ou désignation)…",
    placeholderInactif: "Choisissez d'abord le magasin source",
    construireUrl: function (terme) {
      var url = "/pages/articles/recherche?q=" + encodeURIComponent(terme);
      if (selectMagasinSource && selectMagasinSource.value) {
        url += "&magasin_id=" + encodeURIComponent(selectMagasinSource.value);
      }
      return url;
    },
    texteSuggestion: function (a) {
      return a.nom + " — " + a.reference + " (" + a.quantite + " en stock)";
    },
    texteChoisi: function (a) { return a.nom + " — " + a.reference; },
  });

  if (selectMagasinSource) {
    selectMagasinSource.addEventListener("change", picker.rafraichirDisponibilite);
  }

  // Bloc Réception fournisseur (entrees.html) seulement : plus de champ
  // Fournisseur propre au formulaire — dérivé automatiquement de
  // l'article choisi (voir includes/article-picker.html,
  // article_picker_fournisseur_cible, et gtc_data.rechercher_articles
  // pour fournisseur_id/fournisseur_nom). Le champ affiché (readonly)
  // porte lui-même `required` (voir data-type-toggle-champ dans
  // entrees.html) : setCustomValidity bloque la soumission avec un
  // message clair tant que l'article choisi n'a pas de fournisseur
  // rattaché — la vérification qui compte reste côté serveur (add_entree).
  var idCibleFournisseur = racine.getAttribute("data-fournisseur-cible");
  var cibleFournisseur = idCibleFournisseur ? document.getElementById(idCibleFournisseur) : null;
  if (cibleFournisseur) {
    var champFournisseur = cibleFournisseur.querySelector("[data-article-fournisseur-champ]");
    var alerteFournisseur = cibleFournisseur.querySelector("[data-article-fournisseur-alerte]");
    var reinitialiserFournisseur = function () {
      if (champFournisseur) {
        champFournisseur.value = "";
        champFournisseur.setCustomValidity("");
      }
      if (alerteFournisseur) alerteFournisseur.hidden = true;
    };
    champTexte.addEventListener("picker:choix", function (event) {
      var article = event.detail;
      var aFournisseur = !!article.fournisseur_nom;
      if (champFournisseur) {
        champFournisseur.value = aFournisseur ? article.fournisseur_nom : "";
        champFournisseur.setCustomValidity(
          aFournisseur ? "" : "Cet article n'a pas de fournisseur rattaché : complétez d'abord sa fiche article."
        );
      }
      if (alerteFournisseur) alerteFournisseur.hidden = aFournisseur;
    });
    // Une nouvelle saisie invalide la sélection précédente (voir
    // viderSelection dans creerPickerRecherche) : le fournisseur affiché
    // doit suivre, sous peine d'afficher un fournisseur qui ne
    // correspond plus au champ article_id (vide) réellement soumis.
    champTexte.addEventListener("input", reinitialiserFournisseur);
  }
}

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
  // serveur — jamais tout le catalogue chargé d'un coup). Cœur commun
  // (recherche, suggestions, navigation clavier) dans creerPickerRecherche,
  // logique par composant dans initialiserArticlePicker (toutes deux
  // définies ci-dessus, hors DOMContentLoaded) — partagé avec le
  // composant Fournisseur (section 9) et les lignes ajoutées
  // dynamiquement du bordereau de route (section 11).
  document.querySelectorAll("[data-article-picker]").forEach(initialiserArticlePicker);

  // ---- 9. Recherche de fournisseur avec autocomplétion (type-ahead) ----
  // Même principe que le composant Article ci-dessus (section 5), pour le
  // fournisseur habituel d'un article (voir includes/fournisseur-picker.html,
  // pages/fiche_stock.html et pages/articles.html) — remplace le <select>
  // qu'utilisait ce champ. Suggestions via /pages/fournisseurs/recherche
  // (gtc_data.rechercher_fournisseurs), limitée à 10 résultats. Toujours
  // actif (pas de dépendance à un autre champ, contrairement à l'article).
  document.querySelectorAll("[data-fournisseur-picker]").forEach(function (racine) {
    var champTexte = racine.querySelector("[data-fournisseur-picker-input]");
    var champValeur = racine.querySelector("[data-fournisseur-picker-value]");
    var listeSuggestions = racine.querySelector("[data-fournisseur-picker-suggestions]");
    if (!champTexte || !champValeur || !listeSuggestions) return;

    creerPickerRecherche({
      champTexte: champTexte,
      champValeur: champValeur,
      listeSuggestions: listeSuggestions,
      construireUrl: function (terme) {
        return "/pages/fournisseurs/recherche?q=" + encodeURIComponent(terme);
      },
      texteSuggestion: function (f) {
        return f.contact ? f.nom + " — " + f.contact : f.nom;
      },
      texteChoisi: function (f) { return f.nom; },
    });
  });

  // ---- 6. Bascule de blocs de champs selon un type choisi ----
  // Générique : affiche/masque le bloc de champs pertinent selon la
  // valeur d'un <select> — utilisé par « Type d'entrée » (entrees.html),
  // « Type de sortie » (sorties.html) et, imbriqué À L'INTÉRIEUR d'un
  // bloc « Type de sortie », le « Justificatif » (bon de livraison vs
  // bordereau de route). Marquage attendu (dans le même <form> que le
  // sélecteur) :
  //   <select data-type-toggle-select id="mon-select"> ... </select>
  //   <div data-type-toggle-groupe="valeur-de-option"
  //        data-type-toggle-for="mon-select"> <!-- l'id ci-dessus ;
  //     omissible tant qu'UN SEUL sélecteur toggle existe dans le
  //     formulaire (rétrocompatible avec entrees.html) — sinon
  //     OBLIGATOIRE pour ne pas être géré par le mauvais sélecteur
  //     (voir sorties.html : Type de sortie ET Justificatif imbriqués) -->
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
    // data-type-toggle-for : un groupe SANS cet attribut reste géré par
    // n'importe quel sélecteur toggle du formulaire (comportement
    // d'origine, un seul niveau de bascule) ; AVEC, seulement par le
    // sélecteur dont l'id correspond — nécessaire dès qu'un formulaire a
    // plusieurs sélecteurs toggle imbriqués (sinon le sélecteur du
    // dessus déciderait, à tort, du sort des groupes du sélecteur du
    // dessous, et réciproquement).
    var groupes = Array.prototype.filter.call(
      form.querySelectorAll("[data-type-toggle-groupe]"),
      function (groupe) {
        var pour = groupe.getAttribute("data-type-toggle-for");
        return !pour || pour === select.id;
      }
    );
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
        // Un groupe qui redevient actif peut lui-même contenir un AUTRE
        // sélecteur toggle imbriqué (Justificatif, dans le bloc Type de
        // sortie = Mouvement de sortie) : le resynchroniser à chaque
        // fois, car la bascule du sélecteur PARENT ne déclenche pas
        // toute seule le "change" de l'enfant — sans ça, le required
        // ci-dessus s'appliquerait à tort à SES deux sous-blocs à la
        // fois plutôt qu'au seul actif.
        if (actif) {
          groupe.querySelectorAll("[data-type-toggle-select]").forEach(function (imbrique) {
            imbrique.dispatchEvent(new Event("change"));
          });
        }
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

  // ---- 8. Sidebar en menu masqué (mobile/tablette) ----
  // En dessous de lg (992px), la sidebar est masquée par défaut (voir
  // gtc-stock.css) : le bouton ☰ de la topbar, le fond assombri et la
  // touche Échap la font glisser en vue / la referment. Au-dessus de lg
  // elle reste toujours visible (le bouton ☰ est lui-même caché,
  // d-lg-none) : rien de ce qui suit ne s'applique alors.
  var sidebar = document.getElementById("sidebarNav");
  var bouton = document.getElementById("sidebarToggle");
  var boutonFermer = document.getElementById("sidebarClose");
  var fond = document.getElementById("sidebarBackdrop");
  if (sidebar && bouton && fond) {
    function ouvrir() {
      sidebar.classList.add("show");
      fond.classList.add("show");
      bouton.setAttribute("aria-expanded", "true");
    }
    function fermer() {
      sidebar.classList.remove("show");
      fond.classList.remove("show");
      bouton.setAttribute("aria-expanded", "false");
    }
    bouton.addEventListener("click", function () {
      if (sidebar.classList.contains("show")) fermer(); else ouvrir();
    });
    if (boutonFermer) boutonFermer.addEventListener("click", fermer);
    fond.addEventListener("click", fermer);
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") fermer();
    });
  }

  // ---- 10. Analyse des articles : graphique en anneau (voir
  // pages/analyse_articles.html) ----
  // Survol/focus d'un segment -> estompe les autres segments et met en
  // surbrillance la ligne correspondante de la légende (le tableau à
  // droite du graphique) ; l'inverse au survol d'une ligne. Purement
  // cosmétique : le tableau reste la vue complète des valeurs (légende
  // ET vue tabulaire à la fois), jamais rien d'accessible seulement au
  // survol — voir aussi le <title> natif de chaque <circle> (info-bulle
  // du navigateur, sans JS).
  document.querySelectorAll(".donut-wrap").forEach(function (wrap) {
    var segments = wrap.querySelectorAll("[data-donut-index]");
    if (!segments.length) return;
    var lignes = document.querySelectorAll("[data-donut-legende-ligne]");

    function activer(index) {
      segments.forEach(function (seg) {
        var estCelleCi = seg.getAttribute("data-donut-index") === String(index);
        seg.classList.toggle("is-dimmed", index !== null && !estCelleCi);
      });
      lignes.forEach(function (ligne) {
        ligne.classList.toggle("is-active", ligne.getAttribute("data-donut-legende-ligne") === String(index));
      });
    }

    segments.forEach(function (seg) {
      var index = seg.getAttribute("data-donut-index");
      seg.addEventListener("pointerenter", function () { activer(index); });
      seg.addEventListener("focus", function () { activer(index); });
      seg.addEventListener("pointerleave", function () { activer(null); });
      seg.addEventListener("blur", function () { activer(null); });
    });
    lignes.forEach(function (ligne) {
      var index = ligne.getAttribute("data-donut-legende-ligne");
      ligne.addEventListener("pointerenter", function () { activer(index); });
      ligne.addEventListener("pointerleave", function () { activer(null); });
    });
  });

  // ---- 11. Bordereau de route : lignes d'articles répétables + action
  // du formulaire selon le justificatif choisi (voir pages/sorties.html) ----
  // Un même bordereau peut couvrir PLUSIEURS articles : "Ajouter un
  // article" clone la toute première ligne (déjà initialisée par la
  // section 5 au chargement), réinitialise ses valeurs copiées et lui
  // donne un suffixe d'id unique avant d'appeler initialiserArticlePicker
  // dessus — une ligne ajoutée après le chargement n'est PAS couverte
  // par le balayage initial de la section 5. Toujours au moins une
  // ligne : le bouton "Retirer" reste désactivé tant qu'il n'y en a
  // qu'une (jamais de bordereau sans article).
  var conteneurLignes = document.getElementById("bordereau-lignes-conteneur");
  var boutonAjouterLigne = document.getElementById("bordereau-ajouter-ligne");
  if (conteneurLignes && boutonAjouterLigne) {
    var compteurLignesBordereau = 0;

    function majBoutonsRetirerBordereau() {
      var lignes = conteneurLignes.querySelectorAll("[data-bordereau-ligne]");
      lignes.forEach(function (ligne) {
        var bouton = ligne.querySelector("[data-bordereau-ligne-retirer]");
        if (bouton) bouton.disabled = lignes.length <= 1;
      });
    }

    function brancherRetraitLigne(ligne) {
      var bouton = ligne.querySelector("[data-bordereau-ligne-retirer]");
      if (!bouton) return;
      bouton.addEventListener("click", function () {
        ligne.remove();
        majBoutonsRetirerBordereau();
      });
    }

    function ajouterLigneBordereau() {
      var premiere = conteneurLignes.querySelector("[data-bordereau-ligne]");
      if (!premiere) return;
      compteurLignesBordereau++;
      var nouvelle = premiere.cloneNode(true);

      // Réinitialise ce que cloneNode a copié (sinon la nouvelle ligne
      // démarrerait avec la même saisie que celle dupliquée).
      nouvelle.querySelectorAll("input[type=text], input[type=number]").forEach(function (champ) {
        champ.value = "";
      });
      nouvelle.querySelectorAll("[data-article-picker-value]").forEach(function (champ) {
        champ.value = "";
      });
      nouvelle.querySelectorAll("[data-article-picker-suggestions]").forEach(function (liste) {
        liste.innerHTML = "";
        liste.style.display = "none";
      });
      // Suffixe unique sur les id / label[for] internes (jamais sur les
      // `name`, laissés identiques d'une ligne à l'autre EXPRÈS : c'est
      // ce qui permet à request.form.getlist("bordereau_xxx[]") de tout
      // récupérer, dans l'ordre, côté serveur).
      nouvelle.querySelectorAll("[id]").forEach(function (el) {
        el.id = el.id + "-" + compteurLignesBordereau;
      });
      nouvelle.querySelectorAll("label[for]").forEach(function (label) {
        label.setAttribute("for", label.getAttribute("for") + "-" + compteurLignesBordereau);
      });

      conteneurLignes.appendChild(nouvelle);
      nouvelle.querySelectorAll("[data-article-picker]").forEach(initialiserArticlePicker);
      brancherRetraitLigne(nouvelle);
      majBoutonsRetirerBordereau();
    }

    conteneurLignes.querySelectorAll("[data-bordereau-ligne]").forEach(brancherRetraitLigne);
    majBoutonsRetirerBordereau();
    boutonAjouterLigne.addEventListener("click", ajouterLigneBordereau);
  }

  // Le formulaire de sortie poste vers deux endpoints différents selon
  // le justificatif : Bordereau de route (plusieurs articles, champs
  // d'en-tête propres) a besoin d'une route dédiée ; tout le reste
  // continue de poster vers creer_sortie, inchangé. `data-action-sortie`
  // / `data-action-bordereau-route` (voir pages/sorties.html) portent
  // les deux URLs ; piloté par les DEUX sélecteurs (Type de sortie ET
  // Justificatif), l'un ou l'autre pouvant faire basculer la bonne cible.
  var formSortie = document.getElementById("form-sortie");
  var selectTypeSortie = document.getElementById("sortie-type-sortie");
  var selectTypeDocument = document.getElementById("sortie-type-document");
  if (formSortie && selectTypeSortie && formSortie.dataset.actionBordereauRoute) {
    var majActionFormulaireSortie = function () {
      var estBordereau = selectTypeSortie.value === "mouvement_sortie" &&
        selectTypeDocument && selectTypeDocument.value === "Bordereau de route";
      formSortie.action = estBordereau
        ? formSortie.dataset.actionBordereauRoute
        : formSortie.dataset.actionSortie;
    };
    selectTypeSortie.addEventListener("change", majActionFormulaireSortie);
    if (selectTypeDocument) selectTypeDocument.addEventListener("change", majActionFormulaireSortie);
    majActionFormulaireSortie();
  }

});
