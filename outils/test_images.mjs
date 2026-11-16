/* ==========================================================================
   Test des boutons « Télécharger l'image (PNG) » placés sous les graphiques.

   Chaque page est ouverte dans Chromium (Playwright), sur grand écran et sur
   écran de téléphone. Pour chaque graphique, le test vérifie qu'il y a un
   bouton, l'active au clavier (Tab jusqu'au bouton puis Entrée) ou à la souris,
   et contrôle le fichier téléchargé : un PNG, de taille raisonnable, avec un
   nom explicite. Le test échoue aussi en cas d'erreur JavaScript.

   Usage :  npm install && npm run test:images
            node outils/test_images.mjs evolution.html          (pages choisies)
            DOSSIER_IMAGES=/tmp/images node outils/test_images.mjs   (garde les PNG)
   ========================================================================== */
import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { extname, join, normalize, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const RACINE = join(dirname(fileURLToPath(import.meta.url)), "..");
const PAGES = process.argv.slice(2).length
  ? process.argv.slice(2)
  : ["index.html", "evolution.html", "carte.html", "composition.html",
     "masse-salariale.html", "salaires.html", "retraites.html", "europe.html"];
const ECRANS = [
  { nom: "ordinateur", width: 1280, height: 900 },
  { nom: "téléphone", width: 375, height: 800 },
];
const DOSSIER = process.env.DOSSIER_IMAGES;

const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".woff2": "font/woff2",
  ".json": "application/json", ".png": "image/png",
};
const serveur = createServer(async (req, res) => {
  const chemin = normalize(decodeURIComponent(new URL(req.url, "http://x").pathname)).replace(/^([/\\])+/, "");
  try {
    const contenu = await readFile(join(RACINE, chemin || "index.html"));
    res.writeHead(200, { "Content-Type": TYPES[extname(chemin)] || "application/octet-stream" });
    res.end(contenu);
  } catch {
    res.writeHead(404); res.end();
  }
});
await new Promise((ok) => serveur.listen(0, "127.0.0.1", ok));
const base = `http://127.0.0.1:${serveur.address().port}/`;

// Largeur et hauteur d'un PNG (en-tête IHDR).
function dimensionsPng(octets) {
  const signature = "89504e470d0a1a0a";
  if (octets.subarray(0, 8).toString("hex") !== signature) return null;
  return { largeur: octets.readUInt32BE(16), hauteur: octets.readUInt32BE(20) };
}

if (DOSSIER) await mkdir(DOSSIER, { recursive: true });
const navigateur = await chromium.launch();
const defauts = [];
const erreursJs = [];
let nbImages = 0;

for (const ecran of ECRANS) {
  const contexte = await navigateur.newContext({
    viewport: { width: ecran.width, height: ecran.height }, locale: "fr-FR", acceptDownloads: true,
  });
  for (const page of PAGES) {
    const onglet = await contexte.newPage();
    onglet.on("pageerror", (e) => erreursJs.push(`${page} [${ecran.nom}] : ${e.message}`));
    onglet.on("console", (m) => { if (m.type() === "error") erreursJs.push(`${page} [${ecran.nom}] : ${m.text()}`); });
    await onglet.goto(base + page, { waitUntil: "load" });
    await onglet.waitForTimeout(400);

    // Un bouton par graphique.
    const sansBouton = await onglet.evaluate(() =>
      Array.from(document.querySelectorAll("figure.figure, .carte-zone"))
        .filter((f) => !(f.closest("figure") && f.tagName !== "FIGURE"))
        .filter((f) => f.matches(".carte-zone") ? !(f.nextElementSibling && f.nextElementSibling.querySelector("[data-image-figure]")) : !f.querySelector("[data-image-figure]"))
        .map((f) => f.id || f.className));
    sansBouton.forEach((f) => defauts.push(`${page} [${ecran.nom}] : pas de bouton image pour « ${f} »`));

    const boutons = onglet.locator("[data-image-figure]");
    const n = await boutons.count();
    for (let i = 0; i < n; i++) {
      const bouton = boutons.nth(i);
      await bouton.scrollIntoViewIfNeeded();
      const attente = onglet.waitForEvent("download", { timeout: 15000 });
      if (i === 0) {
        // Au clavier : focus sur l'élément précédent, Tab, puis Entrée.
        await onglet.evaluate((b) => {
          const tous = Array.from(document.querySelectorAll("a[href], button, input, select, [tabindex]"))
            .filter((e) => e.tabIndex >= 0 && !e.disabled && e.offsetParent !== null);
          const k = tous.indexOf(b);
          (k > 0 ? tous[k - 1] : b).focus();
        }, await bouton.elementHandle());
        if (!(await bouton.evaluate((b) => b === document.activeElement))) await onglet.keyboard.press("Tab");
        if (!(await bouton.evaluate((b) => b === document.activeElement))) {
          defauts.push(`${page} [${ecran.nom}] : le bouton image n°${i + 1} n'est pas atteignable avec Tab`);
          await bouton.focus();
        }
        await onglet.keyboard.press("Enter");
      } else {
        await bouton.click();
      }
      let telechargement;
      try {
        telechargement = await attente;
      } catch {
        defauts.push(`${page} [${ecran.nom}] : aucun fichier pour le bouton image n°${i + 1}`);
        continue;
      }
      const nom = telechargement.suggestedFilename();
      const octets = await readFile(await telechargement.path());
      const dim = dimensionsPng(octets);
      nbImages++;
      if (!/^fonction-publique-[a-z0-9-]+\.png$/.test(nom)) defauts.push(`${page} [${ecran.nom}] : nom de fichier inattendu « ${nom} »`);
      if (!dim) defauts.push(`${page} [${ecran.nom}] : « ${nom} » n'est pas un PNG`);
      else if (dim.largeur < 1200 || dim.hauteur < 400 || dim.hauteur > 12000) {
        defauts.push(`${page} [${ecran.nom}] : « ${nom} » a des dimensions inattendues (${dim.largeur} × ${dim.hauteur})`);
      }
      if (DOSSIER) await writeFile(join(DOSSIER, `${ecran.nom === "ordinateur" ? "o" : "t"}-${page.replace(".html", "")}-${String(i + 1).padStart(2, "0")}-${nom}`), octets);
      // Le bouton reprend son libellé, sans état « occupé ».
      await onglet.waitForFunction((b) => !b.hasAttribute("aria-busy"), await bouton.elementHandle());
    }
    console.log(`✓ ${page} [${ecran.nom}] : ${n} image(s)`);
    await onglet.close();
  }
  await contexte.close();
}
await navigateur.close();
serveur.close();

if (erreursJs.length) console.log("\nErreurs JavaScript :\n" + [...new Set(erreursJs)].map((e) => "  " + e).join("\n"));
if (defauts.length) console.log("\nDéfauts :\n" + defauts.map((d) => "  " + d).join("\n"));
console.log(defauts.length || erreursJs.length
  ? `\n${defauts.length + erreursJs.length} problème(s) sur ${nbImages} image(s) produites.`
  : `\n${nbImages} images produites, toutes conformes.`);
process.exit(defauts.length || erreursJs.length ? 1 : 0);
