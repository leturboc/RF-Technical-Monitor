# Passage en 8.0 — la liste

La V8 (branche `v8-sdr`, pré-release `test-v8-sdr`) part sur `main` quand **tout ce qui suit a été essayé en vrai**.
Coche au fur et à mesure (✅ fait, ⚠ à revoir, ✖ ne marche pas) et envoie le 🩺 diagnostic de ce qui coince.

## 1. Essais avec ton vrai matériel (Clément)

### Le SDR (RSP1B ou HackRF)
- [ ] 🔌 Premier branchement SDR : les 6 étapes passent (outil trouvé, SDR détecté, débit tenu).
- [ ] Gain réglé tout seul : la valeur choisie a l'air juste (pas de saturation au tinySA voisin, son propre).
- [ ] Écoute d'un **vrai micro analogique** (Sennheiser evolution, Shure, Wisycom) : son propre, compander deviné juste.
- [ ] Un micro **numérique** affiche bien 📵 et reste surveillé (niveau, alarmes).
- [ ] Favoris au **pavé numérique** sous Windows (vrai clavier) : une touche = le SDR se cale.
- [ ] 🔁 Patrouille sur 3–4 favoris.
- [ ] 🔊 Pilote : retenu sur un vrai pack ; pack éteint + autre émetteur sur la fréquence = alarme PILOTE.
- [ ] 🚨 Se caler sur les alarmes : une vraie alarme (pack éteint) fait se caler le SDR, « ↩ Revenir » marche.
- [ ] 📏 Caler les niveaux sur le tinySA : correction affichée, écart entre signaux < 3 dB.
- [ ] ⏪ Remonter le temps : réécouter une alarme d'il y a 2 minutes.
- [ ] Mode **combiné** tinySA + SDR pendant au moins 1 h, sans à-coups (processeur raisonnable).
- [ ] Si tu en as deux : **2 SDR** (2 postes, numéros de série, scènes, carte).

### Émission (HackRF seulement, EN CÂBLE + atténuateur)
- [ ] 📡 Un faux micro FM reçu par un vrai récepteur (son, pilote, squelch).
- [ ] Puissance réelle mesurée au tinySA (gain 0, ampli coupé).
- [ ] Intermittent : le tinySA et l'appli le voient, alarme / chasse.

### Sons
- [ ] 🎵 Générateur audio entendu (tonalité, balayage, bruit rose, ton WAV).
- [ ] Sons des alarmes personnalisés entendus (un WAV en alarme critique).
- [ ] 🧪 SDR démo : on entend les micros, le brouilleur passe, les alarmes tombent.

### Récepteurs en réseau (si dispo)
- [ ] Shure (ULX-D / QLX-D / AD) : niveaux et piles lus (sinon : capture `telnet <ip> 2202`).
- [ ] Sennheiser (G4 / EW-DX / 6000) : niveaux lus (sinon : capture Wireshark).

## 2. Ce que fait Claude ce jour-là
1. Vérifier que `v8-sdr` contient toute la V7 : `git log origin/v8-sdr..origin/ui-validation` vide.
2. Retirer la surcharge `APP_VER = f"8.0-dev (base {APP_VER})"` (fin du fichier) ; mettre `APP_VER = "8.0.0"`.
3. Fondre le manuel SDR dans le manuel principal : chapitres de `docs/src/sdr_*.html` dans `PARTS` de
   `tests/make_manual.py`, puis `make_manual.py` et `make_pdf.py` ; retirer `manual_sdr.py` /
   `make_manual_sdr.py` / `docs/manuel_sdr.*` si plus utiles (et l'import `manual_sdr` du programme).
4. Traductions : `lang_en_v8.py` peut rester à part (il est fusionné au chargement).
5. CLAUDE.md : en-tête « Version courante : 8.0.0 », section V8 déplacée dans l'historique.
6. Batterie complète, puis fusion de `v8-sdr` dans `ui-validation` puis `main` (release `v8.0.0`).
7. Après : la V7 n'existe plus comme branche à part (plus de `sync-v8.yml` à garder).
