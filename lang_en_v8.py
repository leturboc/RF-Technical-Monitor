"""Traductions anglaises des textes propres à la V8 (SDR : HackRF, RTL-SDR, écoute, temps réel).
Chargé par install_language en plus de lang_en.py (même format) : la V8 n'en modifie pas les lignes, pour
que les mises à jour de la V7 se fusionnent sans conflit."""

EXACT = {
    ": installe l'API SDRplay (sdrplay.com), puis SoapySDR avec le module SoapySDRPlay3 et les rx_tools (": ': install the SDRplay API (sdrplay.com), then SoapySDR with the SoapySDRPlay3 module and the rx_tools (',
    'CS16': 'CS16',
    'SDRplay RSP1B': 'SDRplay RSP1B',
    'pour le 2ᵉ appareil. Pas encore testé avec un vrai RSP1B.': 'for the 2nd device. Not yet tested with a real RSP1B.',
    '). Port « 📡 SDRplay RSP1B », ou adresse': '). Port “📡 SDRplay RSP1B”, or address',
    '📡 SDR': '📡 SDR',
    '📡 SDR (HackRF, RTL-SDR)': '📡 SDR (HackRF, RTL-SDR)',
    'V8 : réglages SDR, écoute (démodulation) et temps réel avec un HackRF / RTL-SDR.': 'V8: SDR settings, listening (demodulation) and real time with a HackRF / RTL-SDR.',
    ') et lit ses mesures.': ') and reads its measurements.',
    ' (appliqués au prochain cycle).': ' (applied at the next cycle).',
    ' Go': ' GB',
    "(ULX-D, Axient D, EW-D / DX, 6000, Spectera…) non : codecs propriétaires, souvent chiffrés. Pendant l'écoute, le balayage de ce SDR est en pause (un tinySA continue de surveiller).": "(ULX-D, Axient D, EW-D / DX, 6000, Spectera…) cannot: proprietary codecs, often encrypted. While listening, this SDR's sweep is paused (a tinySA keeps monitoring).",
    '(WinUSB). Tu peux aussi copier': '(WinUSB). You can also copy',
    '(contient hackrf_sweep, rtl_power et les pilotes), ou les outils HackRF de Great Scott Gadgets. Le pilote USB se met avec': '(it includes hackrf_sweep, rtl_power and the drivers), or the HackRF tools from Great Scott Gadgets. The USB driver is installed with',
    '(elles doivent tenir dans la fenêtre du SDR : ±1,9 MHz pour un HackRF, ±0,9 MHz pour un RTL-SDR), puis ▶ Écouter. Les micros': '(they must fit in the SDR window: ±1.9 MHz for a HackRF, ±0.9 MHz for an RTL-SDR), then ▶ Listen. The',
    '(et ses .dll) dans un dossier': '(and its .dll files) into a folder',
    '50 µs (Europe)': '50 µs (Europe)',
    ": choisis « 📡 HackRF One » ou « 📡 RTL-SDR » dans la liste des ports (ou comme 2ᵉ appareil). L'appli lance l'outil officiel de balayage (": ': choose “📡 HackRF One” or “📡 RTL-SDR” in the port list (or as the 2nd device). The app runs the official sweep tool (',
    ': le plus simple est': ': the easiest is',
    ": règle l'offset, ou fais la calibration automatique avec un tinySA (2ᵉ appareil).": ': set the offset, or run the automatic calibration with a tinySA (2nd device).',
    'AM (aviation, ondes courtes)': 'AM (aviation, shortwave)',
    'AM, canaux 8,33 / 25 kHz.': 'AM, 8.33 / 25 kHz channels.',
    "Ampli d'entrée du HackRF (+14 dB)": 'HackRF input amplifier (+14 dB)',
    "Arrête l'écoute et ferme.": 'Stops listening and closes.',
    'Arrête la démodulation (le temps réel continue).': 'Stops demodulating (real time keeps running).',
    'Aucun appareil sélectionné.\nBranche le tinySA (et ferme tinySA-App), choisis un SDR (📡) ou active le mode démo.': 'No device selected.\nPlug in the tinySA (and close tinySA-App), choose an SDR (📡) or enable demo mode.',
    'Audio': 'Audio',
    'Aussi dans le journal': 'Also in the log',
    'Aviation (AM 118–137 MHz)': 'Aviation (AM 118–137 MHz)',
    'BLU basse (LSB, radioamateurs < 10 MHz)': 'Lower sideband (LSB, radio amateurs < 10 MHz)',
    'BLU haute (USB, radioamateurs)': 'Upper sideband (USB, radio amateurs)',
    'CW (morse, porteuse pure : bip à 700 Hz)': 'CW (morse, pure carrier: 700 Hz beep)',
    'Canaux 12,5 kHz, FM ±2,5 kHz.': '12.5 kHz channels, FM ±2.5 kHz.',
    'Centre :': 'Centre:',
    'Centre de la fenêtre. Astuce : clic droit sur le spectre principal ou sur une fréquence de la liste.': 'Centre of the window. Tip: right-click the main spectrum or a frequency in the list.',
    'Choisir le dossier des outils SDR.': 'Choose the SDR tools folder.',
    'Circuit SA572 / NE570 (2:1, redressement moyen)': 'SA572 / NE570 chip (2:1, average detection)',
    "Clic sur une porteuse : l'écouter (FM / AM ci-dessous). Molette : zoom horizontal.": 'Click a carrier: listen to it (FM / AM below). Mouse wheel: horizontal zoom.',
    'Coche au moins une fréquence (proches les unes des autres).': 'Tick at least one frequency (close to each other).',
    'Coche au moins une fréquence.': 'Tick at least one frequency.',
    "Coche jusqu'à 4 fréquences": 'Tick up to 4 frequencies',
    "Coche les fréquences à démoduler ; pendant l'écoute, clique une ligne pour l'entendre.": 'Tick the frequencies to demodulate; while listening, click a row to hear it.',
    'Compander :': 'Compander:',
    'Compander RMS 2:1 (type dbx)': 'RMS 2:1 compander (dbx type)',
    'Densité des signaux sur quelques secondes : un signal bref laisse une trace pâle.': 'Signal density over a few seconds: a short signal leaves a faint trace.',
    'Dossier des outils :': 'Tools folder:',
    'Dossier des outils SDR': 'SDR tools folder',
    'Dossier qui contient hackrf_sweep(.exe) / rtl_power(.exe). Vide = recherche automatique.': 'Folder containing hackrf_sweep(.exe) / rtl_power(.exe). Empty = automatic search.',
    'Désaccentuation (atténue le souffle aigu) : 50 µs en général.': 'De-emphasis (reduces high-frequency hiss): usually 50 µs.',
    'Désaccentuation :': 'De-emphasis:',
    'Ear monitor analogique stéréo (PSM, EW IEM)': 'Analogue stereo in-ear monitor (PSM, EW IEM)',
    "Enregistre TOUTE la fenêtre (IQ brut, format SigMF) pour la rejouer plus tard : réécouter n'importe quel micro,\nretrouver un brouilleur… Attention à la place : ≈ 38 Mo/s à 19,2 MS/s, 19 Mo/s à 9,6 MS/s, 5 Mo/s à 2,4 MS/s.\nArrêt automatique sous 2 Go libres ou à la taille maximale (Outils › 📡 Réglages SDR).": 'Records the WHOLE window (raw IQ, SigMF format) to play it back later: listen again to any mic,\ntrack down an interferer… Watch the disk space: ≈ 38 MB/s at 19.2 MS/s, 19 MB/s at 9.6 MS/s, 5 MB/s at 2.4 MS/s.\nStops automatically below 2 GB free or at the maximum size (Tools › 📡 SDR settings).',
    'Enregistrement IQ (TinySA Monitor, temps réel)': 'IQ recording (TinySA Monitor, real time)',
    'Enregistrement IQ max :': 'Max IQ recording:',
    'Enregistrement SigMF (*.sigmf-meta *.sigmf-data)': 'SigMF recording (*.sigmf-meta *.sigmf-data)',
    'Entendre tous les canaux démodulés en même temps (sinon : la ligne choisie).': 'Hear all demodulated channels at the same time (otherwise: the selected row).',
    'Expanseur 2:1 générique': 'Generic 2:1 expander',
    'Expanseur 2:1 générique : approximation des companders des marques (non publiés).': "Generic 2:1 expander: an approximation of the brands' companders (not published).",
    'FLAT : ni compander ni désaccentuation (test)': 'FLAT: no compander, no de-emphasis (test)',
    'FM large (micros HF, ears en mono)': 'Wide FM (wireless mics, mono in-ears)',
    'FM large = micros HF / ears analogiques ; FM étroite = talkies ; AM = aviation.': 'Wide FM = analogue wireless mics / in-ears; narrow FM = walkie-talkies; AM = aviation.',
    "FM large, compander type Lectrosonics (approché, mode SR / LEX des récepteurs Wisycom). Le « Digital Hybrid » Lectrosonics natif n'est pas un FM analogique classique : son rendu ne sera pas bon.": 'Wide FM, Lectrosonics-type compander (approximate, SR / LEX mode of Wisycom receivers). Native Lectrosonics “Digital Hybrid” is not classic analogue FM: it will not sound right.',
    'FM stéréo (radio FM, ears stéréo)': 'FM stereo (FM radio, stereo in-ears)',
    'FM ±45 kHz environ, compander Shure (approché).': 'FM about ±45 kHz, Shure compander (approximate).',
    "FM ±48 kHz crête, compander HDX (approché, comme le mode EVO d'un récepteur Wisycom).": 'FM ±48 kHz peak, HDX compander (approximate, like the EVO mode of a Wisycom receiver).',
    "FM ±48 kHz crête, compander HiDyn plus (approché, comme le mode SEN d'un récepteur Wisycom).": 'FM ±48 kHz peak, HiDyn plus compander (approximate, like the SEN mode of a Wisycom receiver).',
    "FM ±50 kHz environ, compander Wisycom ENR (approché ; ENC / ENS / 1.2 / FLAT dans « Compander » : mets le même mode que l'émetteur).": 'FM about ±50 kHz, Wisycom ENR compander (approximate; ENC / ENS / 1.2 / FLAT in “Compander”: use the same mode as the transmitter).',
    'FM ±75 kHz stéréo (pilote 19 kHz), désaccentuation 50 µs (Europe).': 'FM ±75 kHz stereo (19 kHz pilot), 50 µs de-emphasis (Europe).',
    'FM étroite (talkies, guide)': 'Narrow FM (walkie-talkies, tour guide)',
    "FM étroite ±5 kHz (systèmes de guide, retours d'ordres analogiques).": 'Narrow FM ±5 kHz (tour guide systems, analogue talkback).',
    'Gain LNA / tuner :': 'LNA / tuner gain:',
    'Gain VGA :': 'VGA gain:',
    'Garde le plus haut niveau vu à chaque fréquence depuis le début (ou « Effacer »).': 'Keeps the highest level seen at each frequency since the start (or “Clear”).',
    'Guide / talkback FM étroit': 'Tour guide / narrow FM talkback',
    'HackRF : gain LNA (0 à 40 dB par pas de 8). RTL-SDR : gain du tuner (0 à 50 dB).\nTrop de gain = le SDR sature et invente des signaux (intermod interne).': 'HackRF: LNA gain (0 to 40 dB in steps of 8). RTL-SDR: tuner gain (0 to 50 dB).\nToo much gain = the SDR overloads and makes up signals (internal intermod).',
    'HackRF One': 'HackRF One',
    'HackRF seulement : gain VGA (bande de base, 0 à 62 dB par pas de 2).': 'HackRF only: VGA gain (baseband, 0 to 62 dB in steps of 2).',
    "HackRF seulement. Utile avec une petite antenne loin des émetteurs ; à éviter près d'une scène (saturation).": 'HackRF only. Useful with a small antenna far from the transmitters; avoid it near a stage (overload).',
    'Installer les outils (Windows)': 'Installing the tools (Windows)',
    'Journal : ignorer mes fréquences': 'Log: ignore my frequencies',
    'Journal des signaux apparus puis disparus (les plus récents en haut).\nDouble-clic : écouter cette fréquence.': 'Log of signals that appeared then disappeared (newest at the top).\nDouble-click: listen to that frequency.',
    "Lance / arrête l'écoute.": 'Starts / stops listening.',
    'Lance / arrête le temps réel (le balayage de ce SDR est mis en pause).': "Starts / stops real time (this SDR's sweep is paused).",
    "Lance d'abord le temps réel en direct (▶ Démarrer), puis ⏺ Enregistrer.": 'Start live real time first (▶ Start), then ⏺ Record.',
    'Largeur :': 'Width:',
    'Largeur de la fenêtre vue en permanence. Plus large = plus de calcul : 19,2 MS/s demande un PC costaud\n(regarde la charge en bas : au-delà de 100 %, des échantillons sont perdus).': 'Width of the window watched continuously. Wider = more computing: 19.2 MS/s needs a strong PC\n(watch the load at the bottom: above 100 %, samples are lost).',
    'Le SDR qui écoute (il faut ses outils : hackrf_transfer / rtl_sdr).': 'The SDR used for listening (its tools are needed: hackrf_transfer / rtl_sdr).',
    "Le SDR utilisé (outil d'IQ : hackrf_transfer / rtl_sdr).": 'The SDR used (IQ tool: hackrf_transfer / rtl_sdr).',
    "Les gains s'appliquent au cycle suivant (l'outil est relancé). Pas encore testé avec un vrai HackRF / RTL-SDR : dis-moi ce que ça donne !": 'Gains apply from the next cycle (the tool is restarted). Not yet tested with a real HackRF / RTL-SDR: tell me how it goes!',
    'Max dBFS': 'Max dBFS',
    'Max-hold': 'Max hold',
    'Micro Lectrosonics analogique / compatible': 'Lectrosonics analogue mic / compatible',
    'Micro Sennheiser 3000 / 5000 (SK 5212, SK 50…)': 'Sennheiser 3000 / 5000 mic (SK 5212, SK 50…)',
    'Micro Sennheiser evolution (ew G2 / G3 / G4)': 'Sennheiser evolution mic (ew G2 / G3 / G4)',
    'Micro Shure analogique (UR, ULX, SLX, BLX)': 'Shure analogue mic (UR, ULX, SLX, BLX)',
    'Micro Wisycom analogique (MTP, MRK)': 'Wisycom analogue mic (MTP, MRK)',
    'Morse (CW)': 'Morse (CW)',
    'Multiplex stéréo à porteuse pilote 19 kHz (comme la radio FM) : gauche / droite séparés si le pilote est là, sinon mono.': 'Stereo multiplex with a 19 kHz pilot (like FM radio): left / right separated if the pilot is there, otherwise mono.',
    'Mélanger tous les canaux': 'Mix all channels',
    'NONE-d50 : pas de compander, désaccentuation 50 µs': 'NONE-d50: no compander, 50 µs de-emphasis',
    'NONE-d75 : pas de compander, désaccentuation 75 µs': 'NONE-d75: no compander, 75 µs de-emphasis',
    "Ne note pas les signaux à moins de 100 kHz d'une fréquence de ta liste (tes propres émetteurs).": 'Does not log signals within 100 kHz of a frequency in your list (your own transmitters).',
    'Niveau RF': 'RF level',
    'Note aussi chaque signal détecté dans le journal principal (et son export CSV).': 'Also writes each detected signal to the main log (and its CSV export).',
    'Ouvre le dossier des enregistrements IQ.': 'Opens the IQ recordings folder.',
    'Pas encore testé avec un vrai SDR : dis-moi ce que ça donne !': 'Not yet tested with a real SDR: tell me how it goes!',
    'Pause / lecture.': 'Pause / play.',
    'Persistance': 'Persistence',
    'Pilote / données': 'Pilot / data',
    'Porteuse pure rendue en bip de 700 Hz, filtre étroit 500 Hz.': 'Pure carrier turned into a 700 Hz beep, narrow 500 Hz filter.',
    "Position dans l'enregistrement : glisse pour t'y déplacer.": 'Position in the recording: drag to move around.',
    'PothosSDR': 'PothosSDR',
    'Près de': 'Near',
    'Préréglage :': 'Preset:',
    "Préréglage par type d'appareil : déviation, largeur du canal, bande audio, désaccentuation, compander.\nValeurs de départ (fiches techniques), à ajuster à l'oreille : non vérifiées sur les vrais appareils.": 'Preset per type of device: deviation, channel width, audio band, de-emphasis, compander.\nStarting values (data sheets), to be adjusted by ear: not checked on the real devices.',
    'Quitte la relecture.': 'Leaves playback.',
    'RTL-SDR': 'RTL-SDR',
    'Radio FM (bande 87,5–108)': 'FM radio (87.5–108 band)',
    'Radioamateur phonie BLU haute (USB)': 'Radio amateur voice, upper sideband (USB)',
    "Rejoue un enregistrement IQ (.sigmf-meta / .sigmf-data, aussi ceux d'autres logiciels en ci8 / cu8 / ci16 / cf32) :\nspectre, journal des signaux et écoute comme en direct, sans SDR branché.": 'Plays back an IQ recording (.sigmf-meta / .sigmf-data, also from other software in ci8 / cu8 / ci16 / cf32):\nspectrum, signal log and listening as if live, with no SDR plugged in.',
    'Relire un enregistrement IQ': 'Play back an IQ recording',
    'Remet à zéro le max-hold, la persistance et le waterfall.': 'Resets max hold, persistence and the waterfall.',
    'Réglages SDR (HackRF, RTL-SDR)': 'SDR settings (HackRF, RTL-SDR)',
    'Réglages SDR enregistrés': 'SDR settings saved',
    'Résolution (taille de FFT) : plus fin = sépare mieux deux porteuses proches, mais moins de mises à jour par seconde dans chaque FFT.': 'Resolution (FFT size): finer = better separation of two close carriers, but fewer updates per second in each FFT.',
    'Résolution :': 'Resolution:',
    'SDR :': 'SDR:',
    'SIGNAL (TEMPS RÉEL)': 'SIGNAL (REAL TIME)',
    'Seuil du journal :': 'Log threshold:',
    "Seuil du journal : tout signal qui passe au-dessus est noté (début, fin, durée, niveau max).\nLes niveaux d'un SDR sont relatifs (dBFS), pas des dBm.": 'Log threshold: any signal that goes above it is logged (start, end, duration, max level).\nSDR levels are relative (dBFS), not dBm.',
    'Squelch :': 'Squelch:',
    "Squelch : coupe le son d'un canal quand son niveau RF est sous ce seuil.": 'Squelch: mutes a channel when its RF level is below this threshold.',
    "Taille maximale d'un enregistrement IQ (⏱ Temps réel) : il s'arrête tout seul au-delà\n(et quand il reste moins de 2 Go sur le disque).": 'Maximum size of an IQ recording (⏱ Real time): it stops on its own beyond that\n(and when less than 2 GB is left on the disk).',
    'Talkie PMR446 / talkie pro (12,5 kHz)': 'PMR446 walkie-talkie / pro walkie-talkie (12.5 kHz)',
    'Temps réel': 'Real time',
    "Tonalité au-dessus de l'audio dans le signal FM : pilote de squelch (Sennheiser, Shure…), données\n(batterie, télécommande) ou pilote stéréo 19 kHz. Sa présence dit que l'émetteur est bien là ;\nle CONTENU (niveau de batterie) n'est pas décodé : protocoles des marques non publiés.": "Tone above the audio in the FM signal: squelch pilot (Sennheiser, Shure…), data\n(battery, remote control) or 19 kHz stereo pilot. Its presence says the transmitter is really there;\nthe CONTENT (battery level) is not decoded: the brands' protocols are not published.",
    'Trouvés :': 'Found:',
    'USB au-dessus de 10 MHz (VHF / UHF comprises) ; LSB en dessous : choisis « BLU basse » dans Mode.': 'USB above 10 MHz (VHF / UHF included); LSB below: choose “Lower sideband” in Mode.',
    'Un SDR remplace (ou complète) un tinySA': 'An SDR replaces (or adds to) a tinySA',
    "V8 : HackRF One / RTL-SDR à la place (ou en plus) d'un tinySA : dossier des outils\n(hackrf_sweep, rtl_power), gains, et comment les installer.": 'V8: HackRF One / RTL-SDR instead of (or as well as) a tinySA: tools folder\n(hackrf_sweep, rtl_power), gains, and how to install them.',
    'V8 : démodule une ou plusieurs fréquences proches avec un HackRF / RTL-SDR (FM, AM),\nniveau de chaque canal, expanseur 2:1 (approximation des companders).': 'V8: demodulates one or more close frequencies with a HackRF / RTL-SDR (FM, AM),\nlevel of each channel, 2:1 expander (approximation of the companders).',
    "V8 : une fenêtre fixe (jusqu'à ~15 MHz sur un HackRF) vue SANS TROU : max-hold,\npersistance, waterfall, journal des signaux brefs, clic = écouter.": 'V8: a fixed window (up to ~15 MHz on a HackRF) seen WITH NO GAPS: max hold,\npersistence, waterfall, log of short signals, click = listen.',
    "Vitesse de relecture (le son n'est rendu qu'en ×1).": 'Playback speed (sound only at ×1).',
    'Volume :': 'Volume:',
    'Volume.': 'Volume.',
    'Waterfall : le temps descend (≈ 20 lignes par seconde).': 'Waterfall: time goes downwards (≈ 20 lines per second).',
    'Zadig': 'Zadig',
    'aucune sortie son trouvée': 'no audio output found',
    'automatique (PATH, PothosSDR, dossier « outils »)': 'automatic (PATH, PothosSDR, “outils” folder)',
    'balayage en pause (écoute)': 'sweep paused (listening)',
    'disque presque plein': 'disk almost full',
    'fichier .sigmf-data introuvable à côté': '.sigmf-data file not found next to it',
    'flux coupé': 'stream cut',
    "fréquence d'échantillonnage absente": 'sample rate missing',
    'lancement : ': 'start: ',
    'ne sont pas des dBm étalonnés': 'are not calibrated dBm',
    'numériques': 'digital ones',
    'proches': 'close together',
    'analogiques': 'analogue mics',
    'ouvert': 'open',
    'outil : ': 'tool: ',
    "s'écoutent (FM large) ; les": 'can be listened to (wide FM); the',
    'taille maximale atteinte': 'maximum size reached',
    'Écouter': 'Listen',
    '×2 (sans son)': '×2 (no sound)',
    '×4 (sans son)': '×4 (no sound)',
    "à côté de l'appli.": 'next to the app.',
    '≈ EVO : Sennheiser evolution (ew G2 / G3 / G4, HDX)': '≈ EVO: Sennheiser evolution (ew G2 / G3 / G4, HDX)',
    '≈ Lectrosonics (mode SR / LEX)': '≈ Lectrosonics (SR / LEX mode)',
    '≈ SEN : Sennheiser 3000 / 5000 (HiDyn plus)': '≈ SEN: Sennheiser 3000 / 5000 (HiDyn plus)',
    '≈ Shure analogique': '≈ Shure analogue',
    '≈ Wisycom ENC (voix, plat, pré-accentuation réduite)': '≈ Wisycom ENC (voice, flat, reduced pre-emphasis)',
    '≈ Wisycom ENC 1.2 (dynamique réduite)': '≈ Wisycom ENC 1.2 (reduced dynamics)',
    '≈ Wisycom ENR (réduction de bruit, coupe le haut)': '≈ Wisycom ENR (noise reduction, cuts the highs)',
    '≈ Wisycom ENR 1.2 (dynamique réduite)': '≈ Wisycom ENR 1.2 (reduced dynamics)',
    "≈ Wisycom ENS (live, plus d'air)": '≈ Wisycom ENS (live, more air)',
    '⏱ Temps réel': '⏱ Real time',
    '⏱ Temps réel (SDR)': '⏱ Real time (SDR)',
    '⏱ Temps réel autour de cette fréquence…': '⏱ Real time around this frequency…',
    '⏱ Temps réel avec le SDR…': '⏱ Real time with the SDR…',
    "⏹ Arrêter l'enregistrement": '⏹ Stop recording',
    '⏹ Revenir au direct': '⏹ Back to live',
    "⏺ Enregistrer l'IQ": '⏺ Record IQ',
    '▶ Relire': '▶ Play',
    '▶ Écouter': '▶ Listen',
    "⚠ L'écoute 🎧 utilise déjà le SDR : arrête-la d'abord.": '⚠ Listening 🎧 is already using the SDR: stop it first.',
    '⚠ Le temps réel ⏱ utilise déjà le SDR : clique sur son spectre pour écouter.': '⚠ Real time ⏱ is already using the SDR: click its spectrum to listen.',
    "⚠ Les niveaux d'un SDR": '⚠ SDR levels',
    "⚠ SATURATION : baisse le gain (Outils › 📡) ou retire l'ampli": '⚠ OVERLOAD: lower the gain (Tools › 📡) or turn off the amplifier',
    '✏ Réglages à la main': '✏ Manual settings',
    '🎧 Clic sur le spectre pour écouter': '🎧 Click the spectrum to listen',
    '🎧 Écouter': '🎧 Listen',
    '🎧 Écouter avec le SDR': '🎧 Listen with the SDR',
    '🎧 Écouter avec le SDR…': '🎧 Listen with the SDR…',
    '🎧 écoute en cours : balayage du SDR en pause': '🎧 listening: SDR sweep paused',
    "📂 Fin de l'enregistrement.": '📂 End of the recording.',
    '📂 Relire un enregistrement…': '📂 Play back a recording…',
    '📡 Réglages SDR': '📡 SDR settings',
    '📡 Réglages SDR (HackRF, RTL-SDR)…': '📡 SDR settings (HackRF, RTL-SDR)…',
    "🔇 Couper l'écoute": '🔇 Stop listening',
}

TEMPLATES = {
    ' · pilote {} kHz': ' · pilot {} kHz',
    ' · ⚠ {} trop loin (ou au-delà de 4) : pas écoutée(s)': ' · ⚠ {} too far (or beyond 4): not played',
    ' — {} débranché ou occupé ?': ' — {} unplugged or in use?',
    'Fenêtre du SDR centrée sur {} MHz : {} canal(aux) démodulé(s)': 'SDR window centred on {} MHz: {} channel(s) demodulated',
    'Fichier illisible : {}': 'Unreadable file: {}',
    'Impossible de lancer {} : {}': 'Cannot start {}: {}',
    'Temps réel · charge {} % · crête {} dBFS': 'Real time · load {} % · peak {} dBFS',
    "erreur d'écriture ({})": 'write error ({})',
    'format IQ « {} » non géré (ci8, cu8, ci16_le, cf32_le)': 'IQ format “{}” not supported (ci8, cu8, ci16_le, cf32_le)',
    'signal {} MHz {} dBFS': 'signal {} MHz {} dBFS',
    'signal {} MHz, {} dBFS, {} s': 'signal {} MHz, {} dBFS, {} s',
    'sortie son indisponible ({})': 'audio output unavailable ({})',
    '{} Go': '{} GB',
    '{} Mo': '{} MB',
    '{} introuvable (outils {} : PothosSDR, ou Outils › 📡 Réglages SDR).': '{} not found ({} tools: PothosSDR, or Tools › 📡 SDR settings).',
    '{} introuvable : installe les outils {} (PothosSDR sous Windows) ou indique leur dossier dans Outils › 📡 Réglages SDR.': '{} not found: install the {} tools (PothosSDR on Windows) or give their folder in Tools › 📡 SDR settings.',
    '{} muet depuis {} s': '{} silent for {} s',
    '{} pas lancé (aucune bande ?)': '{} not started (no band?)',
    '{} prêt ({})': '{} ready ({})',
    "{} s'est arrêté ({}) — {} débranché ?": '{} stopped ({}) — {} unplugged?',
    '≈ {} MHz ({} MS/s)': '≈ {} MHz ({} MS/s)',
    '⏱ {} : temps réel {} MHz ± {} MHz': '⏱ {}: real time {} MHz ± {} MHz',
    '⏹ Enregistrement arrêté{} — {} dans {}.sigmf-data': '⏹ Recording stopped{} — {} in {}.sigmf-data',
    '⏺ Enregistrement IQ : {}.sigmf-data': '⏺ IQ recording: {}.sigmf-data',
    '⏺ … ({} Mo/s)': '⏺ … ({} MB/s)',
    '⚠ Enregistrement illisible : {}': '⚠ Unreadable recording: {}',
    '⚠ Enregistrement impossible : {}': '⚠ Cannot record: {}',
    '⚠ Temps réel arrêté : {}': '⚠ Real time stopped: {}',
    '⚠ le PC ne suit pas ({} %) : réduis la largeur': "⚠ the PC can't keep up ({} %): reduce the width",
    "⚠ {} : les niveaux s'affichent quand même.": '⚠ {}: the levels are shown anyway.',
    '⚠ Écoute arrêtée : {}': '⚠ Listening stopped: {}',
    '✗ {} introuvable': '✗ {} not found',
    '🎧 {} : écoute autour de {} MHz': '🎧 {}: listening around {} MHz',
    '🎧 {} MHz': '🎧 {} MHz',
    '📂 Relecture : {} · {} MHz · {} MS/s · {} s': '📂 Playback: {} · {} MHz · {} MS/s · {} s',
}

SAME_TEMPLATES = [
    '8.0-dev (base {})',
    'SDR {}',
    'iq_{}_{}MHz',
]
# ---- étape 6 : écouter de partout, ⏺ WAV, 🔁 balayage d'écoute, 📱 écoute sur le téléphone
EXACT.update({
    "Coupe le son de ce PC (la page web 🎧 Écoute continue d'en recevoir).":
        "Mutes this PC (the 🎧 Listen web page still receives the sound).",
    "Enregistre ce que tu entends (fichier WAV 48 kHz stéréo) dans le dossier des journaux,\n« enregistrements_audio » : pour garder la preuve d'un brouilleur, d'un larsen, d'une coupure.":
        "Records what you hear (48 kHz stereo WAV file) in the logs folder,\n“enregistrements_audio”: to keep proof of an interferer, feedback, a dropout.",
    "Le PC écoute avec son SDR (HackRF, RTL-SDR…). Touche 🎧 sur un micro : le son arrive ici, avec un petit retard. Code PIN demandé (celui du PC). Les micros numériques ne s'écoutent pas.":
        "The PC listens with its SDR (HackRF, RTL-SDR…). Tap 🎧 on a mic: the sound arrives here, with a small delay. PIN code required (the PC's). Digital mics cannot be listened to.",
    "Les fréquences cochées ne tiennent pas dans une seule fenêtre du SDR : il passe de l'une à\nl'autre et s'arrête là où ça parle (niveau au-dessus du squelch ; squelch ouvert : 12 dB\nau-dessus du canal le plus calme vu),\nle temps de la phrase. Comme un scanner. Quelques dixièmes de seconde de blanc à chaque saut.":
        "The ticked frequencies do not fit in one SDR window: it goes from one to\nthe other and stops where someone talks (level above the squelch; squelch open: 12 dB\nabove the quietest channel seen),\nfor the length of the sentence. Like a scanner. A few tenths of a second of silence at each hop.",
    "Temps passé sur une fenêtre où rien ne parle.": "Time spent on a window where nobody talks.",
    "WEB": "WEB",
    "requête": "request",
    "Écoute": "Listen",
    "Écouter un micro analogique sur le téléphone, avec le SDR du PC": "Listen to an analogue mic on the phone, with the PC's SDR",
    "⏱ Temps réel autour (SDR)": "⏱ Real time around it (SDR)",
    "⏺ Enregistrer le son": "⏺ Record the sound",
    "⏹ Arrêter l'enregistrement": "⏹ Stop recording",
    "⏺ Son enregistré : {}": "⏺ Sound recorded: {}",
    "⚠ Enregistrement arrêté : {}": "⚠ Recording stopped: {}",
    "⚠ Enregistrement impossible : {}": "⚠ Recording impossible: {}",
    "📱 Écoute arrêtée depuis le téléphone.": "📱 Listening stopped from the phone.",
    "📱 Écoute demandée depuis le téléphone : {} MHz": "📱 Listening requested from the phone: {} MHz",
    "🔁 Balayage d'écoute": "🔁 Listening scan",
    "🔇 Son seulement sur le téléphone": "🔇 Sound on the phone only",
    "🔊 Activer le son ici": "🔊 Turn on sound here",
    "🎧 Écouter avec le SDR": "🎧 Listen with the SDR",
    "🎧 Écouter": "🎧 Listen",
    "Autre fréquence (MHz)": "Other frequency (MHz)",
    "Pas d'écoute en cours": "Not listening",
    "🔊 Son actif": "🔊 Sound on",
    "Son impossible sur ce navigateur": "Sound not possible in this browser",
})
TEMPLATES.update({
    "🔁 Balayage d'écoute : {} fenêtres du SDR, {} fréquence(s).": "🔁 Listening scan: {} SDR windows, {} frequency(ies).",
    "{} s par fenêtre": "{} s per window",
})
SAME_TEMPLATES += ["ecoute_{}_{}MHz.wav", "📍 {}"]
# morceaux de la page web propres à la V8 (vue 🎧 Écoute), ajoutés à lang_en.WEB au chargement
WEB = [
    ("🔊 Activer le son ici", "🔊 Turn on sound here"),
    ("Le PC écoute avec son SDR (HackRF, RTL-SDR…). Touche 🎧 sur un micro : le son arrive ici, avec un petit retard. Code PIN demandé (celui du PC). Les micros numériques ne s'écoutent pas.",
     "The PC listens with its SDR (HackRF, RTL-SDR…). Tap 🎧 on a mic: the sound arrives here, with a small delay. PIN code required (the PC's). Digital mics cannot be listened to."),
    ('placeholder="Autre fréquence (MHz)"', 'placeholder="Other frequency (MHz)"'),
    (">🎧 Écouter</button>", ">🎧 Listen</button>"),
    ('"🎧 Écouter"', '"🎧 Listen"'),
    ('"■ Arrêter"', '"■ Stop"'),
    ('"Pas d\'écoute en cours"', '"Not listening"'),
    ('"Son impossible sur ce navigateur"', '"Sound not possible in this browser"'),
    ('"🔊 Son actif"', '"🔊 Sound on"'),
    ('"Refusé ("', '"Refused ("'),
]
WEB.append(('"Code PIN incorrect."', '"Wrong PIN code."'))
# ---- étape 7 : fiches des SDR, WiNRADiO, surveillance pendant l'écoute
for _k in ("AudioPlaybackStreamCallback", "AudioStreamCallback", "Bandwidth", "BitsPerSample", "ChannelCount",
           "CloseDevice", "DDC1PlaybackStreamCallback", "DDC1StreamCallback", "DDC2PreprocessedStreamCallback",
           "DDC2StreamCallback", "DevicePath", "EEPROMVersion", "FWVersion", "FrontEndFrequencyStep",
           "FrontEndMaxFrequency", "FrontEndMaxHFFrequency", "FrontEndMinFrequency", "FrontEndWindowWidth",
           "GetDDC1Count", "GetDDCInfo", "GetDeviceInfo", "GetIFSpectrumCompensation", "HWVersion", "HardwareOptions",
           "IFCallback", "InterfaceType", "OpenDevice", "PATH", "SampleRate", "SerialNumber", "SetAttenuator",
           "SetCallbacks", "SetDDC1", "SetDDC1Frequency", "SetDDC1Mode", "SetFrontEndFrequency", "SetPower",
           "SetPreamplifier", "StartDDC1", "StartSweeping", "StopDDC1", "StopSweeping", "SweepingCallback",
           "WINFUNCTYPE", "WinDLL", "G39DDCAPI.dll", "SoapySDR", "ADALM-Pluto", "Airspy HF+", "Airspy HF+ Discovery",
           "Airspy Mini", "Airspy R2", "Airspy R2 / Mini", "Ettus USRP", "Ettus USRP B200 / B210", "HackRF One / Pro",
           "HackRF Pro", "LimeSDR", "LimeSDR Mini", "RTL-SDR Blog V3", "RTL-SDR Blog V4", "SDRplay RSP (1A, 1B, dx, duo)",
           "SDRplay RSP1A", "SDRplay RSPduo", "SDRplay RSPdx / RSPdx-R2", "WiNRADiO G39DDC", "WiNRADiO G39DDC Excelsior",
           "WiNRADiO G65DDC", "bladeRF 2.0 micro", "winradio.com (doc + G39DDCAPI.h)", "winradio.com (doc + G65DDCAPI.h)",
           "C:\\Program Files (x86)\\WiNRADiO", "C:\\Program Files (x86)\\WiNRADiO\\G39DDC",
           "C:\\Program Files\\WiNRADiO", "C:\\Program Files\\WiNRADiO\\G39DDC", "Gain"):
    EXACT[_k] = _k
EXACT.update({
    "  (pas pris en charge)": "  (not supported)",
    "(Windows) : HackRF / RTL-SDR :": "(Windows): HackRF / RTL-SDR:",
    "(outils + pilotes, pilote USB avec": "(tools + drivers, USB driver with",
    "+ le module du fabricant + les": "+ the manufacturer's module + the",
    "0 – 88 MHz seulement : pas de micros UHF. Pas pris en charge (API différente : canaux DDC multiples).":
        "0 – 88 MHz only: no UHF mics. Not supported (different API: multiple DDC channels).",
    "100 kHz – 6 GHz, 8 bits ; mode 16 bits (ENOB 9 à 11) à bas débit, pas encore utilisé par les outils hackrf_* (supposé). Entrée max supposée comme le One.":
        "100 kHz – 6 GHz, 8 bits; 16-bit mode (ENOB 9 to 11) at low rates, not yet used by the hackrf_* tools (assumed). Max input assumed the same as the One.",
    "12 bits (10,4 ENOB), 10 MS/s, ~9 MHz sans repliement. Débits pas multiples de 240 kHz : son rééchantillonné.":
        "12 bits (10.4 ENOB), 10 MS/s, ~9 MHz alias-free. Rates not multiples of 240 kHz: audio resampled.",
    "12 bits ; en USB 2 le débit utile tient autour de 4 MS/s.": "12 bits; over USB 2 the usable rate is about 4 MS/s.",
    "12 bits, jusqu'à 56 MHz ; entrée max −15 dBm (fiche).": "12 bits, up to 56 MHz; max input −15 dBm (datasheet).",
    "12 bits, jusqu'à 6 MHz de vue (10 MS/s possibles).": "12 bits, up to 6 MHz view (10 MS/s possible).",
    "12 bits, jusqu'à 61,44 MS/s.": "12 bits, up to 61.44 MS/s.",
    "12 bits, jusqu'à ~30 MS/s.": "12 bits, up to ~30 MS/s.",
    "14 bits jusqu'à ~6 MS/s (moins de bits au-delà, jusqu'à 10 MHz de large). Bien plus de dynamique qu'un 8 bits : un micro faible à côté d'un émetteur fort reste visible.":
        "14 bits up to ~6 MS/s (fewer bits above, up to 10 MHz wide). Much more dynamic range than 8 bits: a weak mic next to a strong transmitter stays visible.",
    "14 bits, 10 MHz, 3 entrées d'antenne (choisies dans le logiciel SDRplay).":
        "14 bits, 10 MHz, 3 antenna inputs (chosen in the SDRplay software).",
    "16 bits à 100 MS/s. Balayage matériel calibré en dBm. Flux IQ (DDC1) jusqu'à 4 MHz (2 canaux) ou 6 MHz (mode large) : débits demandés au récepteur. Piloté par sa DLL Windows G39DDCAPI.dll.":
        "16 bits at 100 MS/s. Hardware sweep calibrated in dBm. IQ stream (DDC1) up to 4 MHz (2 channels) or 6 MHz (wide mode): rates asked from the receiver. Driven through its Windows DLL G39DDCAPI.dll.",
    "8 bits : environ 48 dB de dynamique dans la fenêtre ; un émetteur fort tout près sature vite. Ne pas dépasser −5 dBm à l'entrée.":
        "8 bits: about 48 dB of dynamic range in the window; a strong transmitter close by saturates it quickly. Do not exceed −5 dBm at the input.",
    "8 bits, 2,4 MS/s stables (≈ 1,9 MHz utiles) : une seule petite fenêtre.":
        "8 bits, 2.4 MS/s stable (≈ 1.9 MHz usable): a single small window.",
    ": choisis-le dans la liste des ports (ou comme 2ᵉ appareil). Il balaye tes bandes, et il sait aussi":
        ": choose it in the port list (or as the 2nd device). It sweeps your bands, and it can also",
    "Ajouté aux niveaux de ce SDR pendant l'écoute (dBFS -> dBm à peu près), pour que la\nsurveillance pendant l'écoute ait la même échelle que le tinySA. 0 pour un WiNRADiO\n(déjà en dBm). Le plus juste : la calibration automatique avec un tinySA.":
        "Added to this SDR's levels while listening (dBFS -> roughly dBm), so that\nmonitoring while listening uses the same scale as the tinySA. 0 for a WiNRADiO\n(already in dBm). Most accurate: automatic calibration with a tinySA.",
    "Ampli d'entrée": "Input amp",
    "Ampli d'entrée +14 dB": "Input amp +14 dB",
    "Atténuateur (0 = automatique)": "Attenuator (0 = automatic)",
    "Atténuateur (< 60 MHz)": "Attenuator (< 60 MHz)",
    "Comme le V3 avec la HF intégrée (convertisseur) ; 8 bits, 2,4 MS/s.":
        "Like the V3 with built-in HF (converter); 8 bits, 2.4 MS/s.",
    "Correction de niveau (écoute) :": "Level correction (listening):",
    "Deux tuners : 10 MHz avec un seul, 2 MHz chacun en double tuner (non géré ici : un seul tuner).":
        "Two tuners: 10 MHz with one, 2 MHz each in dual-tuner mode (not handled here: one tuner).",
    "Dossier qui contient les outils (hackrf_sweep, rtl_power, rx_power…) ou la DLL WiNRADiO.\nVide = recherche automatique.":
        "Folder containing the tools (hackrf_sweep, rtl_power, rx_power…) or the WiNRADiO DLL.\nEmpty = automatic search.",
    "Débits : {} MS/s · fenêtre utile jusqu'à {} MHz": "Rates: {} MS/s · usable window up to {} MHz",
    "Entrée max conseillée : {} dBm": "Recommended max input: {} dBm",
    "G39DDC : aucun type de DDC1 disponible": "G39DDC: no DDC1 type available",
    "G39DDC : balayage pas lancé": "G39DDC: sweep not started",
    "G39DDCAPI.dll introuvable : installe le logiciel WiNRADiO G39DDC (il installe la DLL) ou indique son dossier dans 📡 Réglages SDR.":
        "G39DDCAPI.dll not found: install the WiNRADiO G39DDC software (it installs the DLL) or give its folder in 📡 SDR settings.",
    "Gain (linéarité 0 – 21)": "Gain (linearity 0 – 21)",
    "Gain (réduction LNA + IF)": "Gain (LNA + IF reduction)",
    "Gain du tuner": "Tuner gain",
    "Gains de ce modèle": "Gains of this model",
    "HF 0,5 kHz – 31 MHz et VHF 64 – 260 MHz : PAS d'UHF (micros 470-694 hors de portée). Très grande dynamique (110 dB BDR en HF).":
        "HF 0.5 kHz – 31 MHz and VHF 64 – 260 MHz: NO UHF (470-694 mics out of range). Very high dynamic range (110 dB BDR on HF).",
    "Installer": "Install",
    "LNA (gain RF)": "LNA (RF gain)",
    "Mon SDR :": "My SDR:",
    "Même électronique de réception que le RSP1B (14 bits, 10 MHz).": "Same receive electronics as the RSP1B (14 bits, 10 MHz).",
    "Niveaux en dBFS : à caler sur un tinySA (offset)": "Levels in dBFS: to be matched to a tinySA (offset)",
    "Niveaux en vrais dBm (calibrés par l'appareil)": "Levels in real dBm (calibrated by the device)",
    "Pendant l'écoute, le spectre de la fenêtre du SDR sert aussi à surveiller tes fréquences\nqui y tombent (si le SDR est ton appareil de surveillance). Un tinySA branché garde\nla surveillance de tout.":
        "While listening, the SDR window's spectrum is also used to monitor your frequencies\nthat fall in it (if the SDR is your monitoring device). A connected tinySA keeps\nmonitoring everything.",
    "Préampli": "Preamp",
    "Réglages SDR": "SDR settings",
    "Source : {}": "Source: {}",
    "Ton SDR : l'appli adapte les débits, la largeur de la fenêtre, les gains et l'échelle\ndes niveaux à ses caractéristiques (bits, plage, entrée max).":
        "Your SDR: the app adapts the rates, the window width, the gains and the level\nscale to its characteristics (bits, range, max input).",
    "Trop de gain = le SDR sature et invente des signaux (intermod interne) ; trop peu = les\nmicros faibles disparaissent dans le bruit. Commence au milieu.":
        "Too much gain = the SDR saturates and invents signals (internal intermod); too little = weak\nmics disappear into the noise. Start in the middle.",
    "VGA (gain bande de base)": "VGA (baseband gain)",
    "WiNRADiO : pilote Windows seulement.": "WiNRADiO: Windows driver only.",
    "WiNRADiO G39DDC introuvable ou déjà utilisé (OpenDevice a échoué).": "WiNRADiO G39DDC not found or already in use (OpenDevice failed).",
    "automatique (PATH, PothosSDR, dossier « outils », dossier WiNRADiO)": "automatic (PATH, PothosSDR, “outils” folder, WiNRADiO folder)",
    "dynamique théorique ≈ {} dB": "theoretical dynamic range ≈ {} dB",
    "démoduler": "demodulate",
    "fiche (non relue)": "datasheet (not re-read)",
    "linéarité": "linearity",
    "pour écouter un micro analogique.": "to listen to an analogue mic.",
    "{} bits": "{} bits",
    "⚠ {} : hors de la plage du {} ({} – {} MHz).": "⚠ {}: outside the range of the {} ({} – {} MHz).",
    "📡 Le tinySA continue de surveiller toute ta liste pendant l'écoute.": "📡 The tinySA keeps monitoring your whole list while you listen.",
    "📡 Surveillance pendant l'écoute : {} – {} MHz ({} de tes fréquences).": "📡 Monitoring while listening: {} – {} MHz ({} of your frequencies).",
})
TEMPLATES.update({
    "WiNRADiO G39DDC · n° {}": "WiNRADiO G39DDC · no. {}",
    "G39DDC ouvert : n° {}, {}–{} MHz, pas {} Hz, fenêtre {} MHz": "G39DDC open: no. {}, {}–{} MHz, step {} Hz, window {} MHz",
    "WiNRADiO G39DDC muet depuis {} s": "WiNRADiO G39DDC silent for {} s",
    "{} : {} à {}, par pas de {}.": "{}: {} to {}, in steps of {}.",
    "G39DDC : {} a échoué": "G39DDC: {} failed",
    "{} introuvable (outils {} : PothosSDR / SoapySDR, ou 📡 Réglages SDR).": "{} not found ({} tools: PothosSDR / SoapySDR, or 📡 SDR settings).",
    "balayage {}–{} MHz (front-end), FFT {}": "sweep {}–{} MHz (front end), FFT {}",
})
SAME_TEMPLATES += [" (ENOB {})", "{} : {} – {} MHz"]
# ---- étape 7 : réglages SDR simplifiés
EXACT.update({
    "1. Installe PothosSDR (SoapySDR + modules Airspy, Lime, Pluto, UHD, bladeRF). 2. Ajoute les rx_tools (rx_power, rx_sdr). 3. Branche le SDR : il doit apparaître dans « SoapySDRUtil --find ».":
        "1. Install PothosSDR (SoapySDR + Airspy, Lime, Pluto, UHD, bladeRF modules). 2. Add the rx_tools (rx_power, rx_sdr). 3. Plug in the SDR: it must show up in “SoapySDRUtil --find”.",
    "1. Installe l'API SDRplay (site sdrplay.com). 2. Installe PothosSDR (SoapySDR). 3. Ajoute le module SoapySDRPlay3 et les rx_tools (rx_power, rx_sdr).":
        "1. Install the SDRplay API (sdrplay.com). 2. Install PothosSDR (SoapySDR). 3. Add the SoapySDRPlay3 module and the rx_tools (rx_power, rx_sdr).",
    "Basse (près des scènes, émetteurs forts)": "Low (near the stages, strong transmitters)",
    "Comment l'installer ?": "How to install it?",
    "Fiche technique, gains étage par étage, dossier des outils, correction de niveau.":
        "Datasheet, gains stage by stage, tools folder, level correction.",
    "Haute (loin, micros faibles)": "High (far away, weak mics)",
    "Installe PothosSDR (il contient hackrf_sweep, hackrf_transfer et les pilotes). Si Windows ne voit pas le HackRF : pilote WinUSB avec Zadig.":
        "Install PothosSDR (it contains hackrf_sweep, hackrf_transfer and the drivers). If Windows does not see the HackRF: WinUSB driver with Zadig.",
    "Installe PothosSDR (rtl_power, rtl_sdr). Pilote WinUSB avec Zadig (choisir « Bulk-In, Interface 0 »).":
        "Install PothosSDR (rtl_power, rtl_sdr). WinUSB driver with Zadig (choose “Bulk-In, Interface 0”).",
    "Installe le logiciel WiNRADiO G39DDC (il installe G39DDCAPI.dll et le pilote). Le récepteur doit être reconnu par son propre logiciel ; ferme ce logiciel avant de lancer la surveillance.":
        "Install the WiNRADiO G39DDC software (it installs G39DDCAPI.dll and the driver). The receiver must be recognised by its own software; close that software before starting monitoring.",
    "Installer {}": "Install {}",
    "Les étapes d'installation pour ce SDR (logiciels à installer sous Windows).": "The install steps for this SDR (software to install on Windows).",
    "Règle tous les gains du SDR d'un coup. Basse : près des scènes, quand des émetteurs forts\nsont tout près (évite la saturation). Haute : antenne loin, micros faibles.":
        "Sets all the SDR's gains at once. Low: near the stages, when strong transmitters\nare close by (avoids saturation). High: antenna far away, weak mics.",
    "Réglages avancés": "Advanced settings",
    "SDR": "SDR",
    "Sensibilité :": "Sensitivity:",
    "fenêtre jusqu'à {} MHz": "window up to {} MHz",
    "niveaux en dBm": "levels in dBm",
    "niveaux à caler": "levels to calibrate",
    "État :": "Status:",
    "✔ Prêt": "✔ Ready",
    "✗ Il manque : {}": "✗ Missing: {}",
})
SAME_TEMPLATES += ["{} – {} MHz"]
# ---- étape 8 : type de signal, santé d'un micro, signaux brefs, enregistrement sur alarme
EXACT.update({
    "Analyse du signal écouté (ou cliqué) : type probable, largeur occupée (99 % de la\npuissance), écart au bruit, tient-il dans un canal de 200 kHz. Repères calculés sur le\nspectre : à confirmer à l'oreille.":
        "Analysis of the signal you listen to (or click): likely type, occupied bandwidth (99 % of the\npower), margin above noise, does it fit in a 200 kHz channel. Estimates computed from the\nspectrum: confirm by ear.",
    "BREF": "BREF",
    "ENREGISTRÉ (alarme)": "RECORDED (alarm)",
    "FM large (≈ 50 – 250 kHz) : micro HF ou ears analogique. Il s'écoute (🎧).": "Wide FM (≈ 50 – 250 kHz): analogue wireless mic or IEM. It can be listened to (🎧).",
    "FM large avec pilote stéréo 19 kHz : ears analogique en stéréo ou radio FM.": "Wide FM with a 19 kHz stereo pilot: analogue stereo IEM or FM radio.",
    "FM stéréo (ears / radio)": "Stereo FM (IEM / radio)",
    "FM étroite (10 – 50 kHz) : talkie, PMR446, intercom, télémétrie.": "Narrow FM (10 – 50 kHz): walkie-talkie, PMR446, intercom, telemetry.",
    "FM étroite (talkie)": "Narrow FM (walkie-talkie)",
    "IQ enregistré 15 s (temps réel)": "IQ recorded 15 s (real time)",
    "Le temps réel voit des signaux de quelques millisecondes, que le balayage rate. Sur une\nfréquence « doit rester libre » de la fenêtre, il lève une alarme CONFLIT (signal bref),\nnotée au journal, qui se termine seule après 1 minute.":
        "Real time sees signals lasting a few milliseconds, which the sweep misses. On a\n“must stay free” frequency in the window, it raises a CONFLICT alarm (short signal),\nlogged, which ends by itself after 1 minute.",
    "Micro / ears FM analogique": "Analogue FM mic / IEM",
    "Micro / ears numérique": "Digital mic / IEM",
    "Pas de signal assez fort à cette fréquence.": "No strong enough signal at this frequency.",
    "Plateau large (5 – 8 MHz) et plat : un multiplex TNT. Les micros doivent l'éviter.": "Wide (5 – 8 MHz) flat plateau: a DTT multiplex. Mics must avoid it.",
    "Plateau plat de 150 kHz à 1 MHz : micro ou ears numérique (codec), DECT, données. Ne s'écoute pas.": "Flat plateau from 150 kHz to 1 MHz: digital mic or IEM (codec), DECT, data. Cannot be listened to.",
    "Plus de 1 MHz de large sans être plat : bloc numérique (WMAS, Spectera ?), vidéo HF, LTE / 5G, ou plusieurs signaux collés.":
        "More than 1 MHz wide without being flat: digital block (WMAS, Spectera?), wireless video, LTE / 5G, or several signals side by side.",
    "Porteuse pure": "Pure carrier",
    "Quand une alarme (conflit, absent) part sur une fréquence de la fenêtre écoutée, le son des\n10 secondes d'avant et des 10 suivantes est enregistré en WAV (preuve du brouillage),\ndans « enregistrements_audio », et noté au journal.":
        "When an alarm (conflict, absent) goes off on a frequency in the listened window, the sound of the\n10 seconds before and the 10 after is recorded as WAV (proof of the interference),\nin “enregistrements_audio”, and logged.",
    "Quand une alarme part sur une fréquence de la fenêtre, enregistre 15 s d'IQ (toute la\nfenêtre, pour réécouter et analyser après). Gros fichiers : décoché d'office.":
        "When an alarm goes off on a frequency in the window, records 15 s of IQ (the whole\nwindow, to listen and analyse later). Big files: unticked by default.",
    "Rien de net": "Nothing clear",
    "Signal large": "Wide signal",
    "TV numérique (TNT)": "Digital TV (DTT)",
    "Très étroit et stable : porteuse sans modulation (émetteur allumé micro coupé, oscillateur, horloge d'un appareil, intermod d'une porteuse).":
        "Very narrow and stable: unmodulated carrier (transmitter on with mic muted, oscillator, a device's clock, intermod of a carrier).",
    "Type · santé du micro": "Type · mic health",
    "hors fréquence ?": "off frequency?",
    "largeur occupée {} kHz": "occupied bandwidth {} kHz",
    "signal bref de {} s vu par le SDR (temps réel)": "short signal of {} s seen by the SDR (real time)",
    "son de l'alarme : {}": "alarm sound: {}",
    "trop chaud (sature ?)": "too hot (clipping?)",
    "très froid": "very cold",
    "{} dB au-dessus du bruit": "{} dB above noise",
    "⏺ Alarme {} sur {} : son enregistré (10 s avant, 10 s après)…": "⏺ Alarm {} on {}: sound recorded (10 s before, 10 s after)…",
    "⏺ Son de l'alarme enregistré : {}": "⏺ Alarm sound recorded: {}",
    "⏺ Sur alarme : enregistrer l'IQ 15 s": "⏺ On alarm: record 15 s of IQ",
    "⏺ Sur alarme : garder le son (10 s avant, 10 s après)": "⏺ On alarm: keep the sound (10 s before, 10 s after)",
    "⚠ déborde d'un canal de {} kHz": "⚠ spills over a {} kHz channel",
    "⚡ Signal bref sur une fréquence « doit rester libre » = alarme": "⚡ Short signal on a “must stay free” frequency = alarm",
    "✔ tient dans un canal de {} kHz": "✔ fits in a {} kHz channel",
    "🔎 C'est quoi ce signal ? (SDR)": "🔎 What is this signal? (SDR)",
})
TEMPLATES.update({"dérive {} kHz": "drift {} kHz", "dév. ±{} kHz": "dev. ±{} kHz", "pilote {} kHz": "pilot {} kHz"})
SAME_TEMPLATES += ["🔎 {} MHz : ", "alarme_{}_{}MHz.wav"]
# ---- étape 9 : moniteur multicanal SDR
EXACT.update({
    " · dérive sur 10 min : moyenne {} kHz, ± {} kHz": " · drift over 10 min: mean {} kHz, ± {} kHz",
    " · {} hors de la fenêtre (le tinySA ou le balayage s'en occupe)": " · {} outside the window (the tinySA or the sweep handles them)",
    " ⚠ sature": " ⚠ clipping",
    "Aucune de tes fréquences n'est dans la plage de ce SDR.": "None of your frequencies is in this SDR's range.",
    "Combien de micros sont démodulés en même temps (son, déviation, dérive). Plus = plus de calcul.\nLes autres sont mesurés par la FFT et passent à tour de rôle toutes les 5 s.":
        "How many mics are demodulated at the same time (sound, deviation, drift). More = more computing.\nThe others are measured by the FFT and take turns every 5 s.",
    "Coupures de son alors que la RF est bonne : câble, capsule, bouton mute ?": "Sound dropouts while RF is good: cable, capsule, mute button?",
    "Diagnostic": "Diagnosis",
    "Décrochages RF répétés : antenne masquée, trop loin, ou brouillage.": "Repeated RF dropouts: antenna blocked, too far, or interference.",
    "Fenêtre : {} – {} MHz · {} fréquence(s) surveillée(s)": "Window: {} – {} MHz · {} frequency(ies) monitored",
    "Fréquence qui dérive ({} kHz) : pack froid, quartz, mauvais réglage.": "Frequency drifting ({} kHz): cold pack, crystal, wrong setting.",
    "Historique du micro choisi (10 dernières minutes) : RF, bruit, son.": "History of the chosen mic (last 10 minutes): RF, noise, sound.",
    "Lance / arrête le moniteur multicanal.": "Starts / stops the multichannel monitor.",
    "Le SDR qui écoute (il faut ses outils, ou la DLL WiNRADiO).": "The SDR that listens (its tools are needed, or the WiNRADiO DLL).",
    "Moniteur multicanal SDR": "SDR multichannel monitor",
    "Performances : échantillons perdus (le PC ou l'USB ne suit pas), charge du calcul, retard.": "Performance: lost samples (the PC or USB can't keep up), computing load, delay.",
    "Porteuse là mais pas de son : micro coupé (mute) ou pack sans audio.": "Carrier present but no sound: mic muted or pack without audio.",
    "RAS": "All good",
    "RF": "RF",
    "RF = niveau (dBFS) et écart au bruit · Son = RMS / crête (🎧 = récepteur virtuel) ·\nSanté = déviation et dérive · Largeur = 99 % de la puissance · Voisins = marge sur les canaux\nadjacents · Diagnostic = croisement RF + son.":
        "RF = level (dBFS) and margin above noise · Sound = RMS / peak (🎧 = virtual receiver) ·\nHealth = deviation and drift · Width = 99 % of the power · Neighbours = margin over the adjacent\nchannels · Diagnosis = RF + sound combined.",
    "RF trop faible : risque de décrochage (antenne, distance, pile ?).": "RF too weak: dropout risk (antenna, distance, battery?).",
    "Rien à surveiller avec ce SDR.": "Nothing to monitor with this SDR.",
    "Récepteurs virtuels :": "Virtual receivers:",
    "Santé": "Health",
    "Signal fort dans le canal voisin ({} dB sous le canal) : désensibilisation, intermod.": "Strong signal in the adjacent channel ({} dB below the channel): desensitisation, intermod.",
    "Son saturé : gain du pack trop fort (ou chanteur très près).": "Sound clipping: pack gain too high (or singer very close).",
    "Toutes tes fréquences qui tiennent dans la fenêtre du SDR sont mesurées en même temps (niveau, voisins, largeur). Les plus importantes ont en plus un":
        "All your frequencies that fit in the SDR window are measured at the same time (level, neighbours, width). The most important ones also get a",
    "Voisins": "Neighbours",
    "Waterfall du micro choisi (± 150 kHz) : le temps descend.": "Waterfall of the chosen mic (± 150 kHz): time flows down.",
    "kHz autour du micro": "kHz around the mic",
    "qui les démodule : son, déviation, dérive, coupures. Clique une ligne pour l'écouter et voir son waterfall et son historique.":
        "that demodulates them: sound, deviation, drift, dropouts. Click a row to listen and see its waterfall and history.",
    "récepteur virtuel": "virtual receiver",
    "▶ Surveiller": "▶ Monitor",
    "⚙ SDR : {} · {} récepteur(s) virtuel(s)": "⚙ SDR: {} · {} virtual receiver(s)",
    "⚠ Le SDR est déjà pris (écoute ou temps réel) : ferme-les d'abord.": "⚠ The SDR is already in use (listening or real time): close them first.",
    "⚠ Moniteur arrêté : {}": "⚠ Monitor stopped: {}",
    "📡 Moniteur multicanal SDR (tous tes micros, son, santé)…": "📡 SDR multichannel monitor (all your mics, sound, health)…",
})
TEMPLATES.update({
    " · silence {} s": " · silence {} s",
    "📡 {} : {} canaux autour de {} MHz": "📡 {}: {} channels around {} MHz",
    "pertes {} % · charge {} % · retard {} s": "loss {} % · load {} % · delay {} s",
})
SAME_TEMPLATES += ["🎧 {} ({} MHz) : ", "{} / {} dB", "{} dBFS · "]
EXACT["V8 : tous tes micros de la fenêtre du SDR mesurés en même temps (niveau, voisins,\nlargeur) ; les plus importants démodulés (son, déviation, dérive, coupures)."] = \
    "V8: all your mics in the SDR window measured at the same time (level, neighbours,\nwidth); the most important ones demodulated (sound, deviation, drift, dropouts)."
EXACT["📡 Moniteur multicanal"] = "📡 Multichannel monitor"

# ---------------------------------------------------------------- V8 étape 10 : incidents (lot B)
EXACT.update({
    " (sans IQ)": " (no IQ)",
    " : {} dB": ": {} dB",
    " : {} en 10 min": ": {} in 10 min",
    " · dossier : {}": " · folder: {}",
    "Alarme": "Alarm",
    "Aussi pendant ce temps : ": "Also during this time: ",
    "Bruit qui monte": "Noise rising",
    "Choisis dans la chronologie une ligne qui a un dossier.": "Pick a line with a folder in the timeline.",
    "Chronologie": "Timeline",
    "Chronologie du micro": "Mic timeline",
    "Crée tout de suite un dossier d'incident pour le micro choisi (ou le 1er de la liste).":
        "Creates an incident folder right now for the selected mic (or the first one in the list).",
    "Diagnostic RF + son": "RF + audio diagnosis",
    "Dossier": "Folder",
    "Dossier d'incident à rejouer": "Incident folder to replay",
    "Décrochage RF": "RF dropout",
    "Décrochages répétés": "Repeated dropouts",
    "Garde le signal brut (IQ) pour pouvoir REJOUER l'incident et l'écouter.\nGros fichiers : environ 10 à 20 Mo par "
    "seconde selon le SDR.": "Keeps the raw signal (IQ) so you can REPLAY the incident and listen to it.\nBig files: about "
                             "10 to 20 MB per second depending on the SDR.",
    "INCIDENT SDR": "SDR INCIDENT",
    "IQ (SigMF) : {} — {} s, {} MHz autour de {} MHz": "IQ (SigMF): {} — {} s, {} MHz around {} MHz",
    "IQ non gardé (case décochée)": "IQ not kept (box unticked)",
    "Incident": "Incident",
    "Incident noté à la main": "Incident noted by hand",
    "Lance d'abord le moniteur (▶ Surveiller).": "Start the monitor first (▶ Monitor).",
    "Mesures : mesures.json": "Measurements: mesures.json",
    "Mesures autour du moment (trait rouge)": "Measurements around the moment (red line)",
    "Micro choisi": "Selected mic",
    "Ouvre le dossier des incidents.": "Opens the incidents folder.",
    "Ouvre le rapport de l'incident choisi et rejoue son IQ dans le temps réel (son, spectre).":
        "Opens the selected incident's report and replays its IQ in real-time view (sound, spectrum).",
    "Pas d'IQ dans ce dossier : seul le rapport s'ouvre.": "No IQ in this folder: only the report opens.",
    "Pas d’IQ enregistré : {}": "No IQ recorded: {}",
    "Quand un micro a un souci (alarme, décrochage, bruit qui monte, voisin trop fort…), garde\ntout seul ses mesures, un "
    "rapport et l'IQ des secondes AVANT et APRÈS (à rejouer).\nUn dossier toutes les 2 min au plus ; les plus anciens sont "
    "effacés au-delà de 2 Go.": "When a mic has a problem (alarm, dropout, rising noise, strong neighbour…), automatically\n"
                                "keeps its measurements, a report and the IQ of the seconds BEFORE and AFTER (to replay).\n"
                                "At most one folder every 2 min; the oldest are deleted beyond 2 GB.",
    "Rejouer : 📡 Moniteur multicanal › Chronologie › ▶ Rejouer, ou Temps réel › Relire un enregistrement.":
        "Replay: 📡 Multichannel monitor › Timeline › ▶ Replay, or Real time › Replay a recording.",
    "Signal bref inconnu": "Unknown short signal",
    "Signal sur la fréquence": "Signal on the frequency",
    "Tout ce qui est arrivé à tes micros pendant la surveillance (le plus récent en haut).\nDouble-clic sur une ligne avec "
    "un dossier = rejouer l'incident.": "Everything that happened to your mics while monitoring (newest at the top).\n"
                                        "Double-click a line with a folder = replay the incident.",
    "V8 : choisis un dossier d'incident du moniteur multicanal : son rapport s'ouvre et\nson IQ est rejoué dans le temps "
    "réel (écouter, revoir le spectre).": "V8: pick an incident folder from the multichannel monitor: its report opens and\n"
                                         "its IQ is replayed in real-time view (listen, review the spectrum).",
    "Voisin trop fort": "Neighbour too strong",
    "avec l'IQ": "with IQ",
    "dérive": "drift",
    "moniteur arrêté": "monitor stopped",
    "{} MHz, {} s, {} dBFS": "{} MHz, {} s, {} dBFS",
    "⏳ en cours…": "⏳ in progress…",
    "▶ Rejouer": "▶ Replay",
    "📂 Dossiers": "📂 Folders",
    "📦 Dossier d'incident automatique": "📦 Automatic incident folder",
    "📦 Noter un incident": "📦 Note an incident",
    "📦 Rejouer un incident": "📦 Replay an incident",
    "📦 Rejouer un incident SDR…": "📦 Replay an SDR incident…",
})
SAME_TEMPLATES = list(SAME_TEMPLATES) + [
    "<h1>⚠ {} : {} · {} MHz</h1>", "{} : {}{} dB", "<p class='muted'>{} · {}</p>", "<tr><td>{}</td><td>{}</td></tr>",
    "<title>{} · {}</title>", "<text x='{}' y='{}' font-size='10' text-anchor='end' fill='#6b7488'>{} s</text>",
    "<text x='{}' y='{}' font-size='11' fill='{}'>■ {}</text>",
    "<text x='{}' y='{}' font-size='10' text-anchor='end' fill='#6b7488'>{}</text>",
    "<text x='4' y='{}' font-size='10' fill='#6b7488'>{}</text></svg>", "<h2>{}</h2><table><tr><th>{}</th><th>{}</th></tr>",
    "<p class='muted'>{}</p>", "<svg viewBox='0 0 {} {}' width='100%' style='max-width:{}px'>",
    "<line x1='{}' x2='{}' y1='{}' y2='{}' stroke='#ff3b30' stroke-dasharray='4 3'/>",
    "<polyline fill='none' stroke='{}' stroke-width='1.5' points='{}'/>", "incident_{}_{}",
    "<text x='{}' y='{}' font-size='10' fill='#6b7488'>{} s</text>",
    "<rect x='{}' y='{}' width='{}' height='{}' fill='#f7f9fc' stroke='#d8dde8'/>", "<li>{}</li></ul>",
    "<li class='{}'>{}</li>"]

# ---------------------------------------------------------------- V8 étape 11 : répétition, comparaison, Shure, kit
EXACT.update({k: k for k in ("< GET 0 ALL >", "AB", "ALL", "FREQUENCY", "SAMPLE", "UNKN", "UNKNOWN", "[AX][BX]")})
EXACT.update({
    " · décrochages vus seulement par {} : {}, seulement par {} : {}": " · dropouts seen only by {}: {}, only by {}: {}",
    "Adresses :": "Addresses:",
    "Adresses IP des récepteurs (port 2202 par défaut, sinon « adresse:port »).":
        "IP addresses of the receivers (port 2202 by default, otherwise “address:port”).",
    "Aucun récepteur : tape une adresse puis Connecter.": "No receiver: type an address then Connect.",
    "Bruit plus haut qu'en répétition ({} dB)": "Noise higher than in rehearsal ({} dB)",
    "Connecter": "Connect",
    "Diversity A / B": "Diversity A / B",
    "Le plus simple : le kit SDR. Télécharge kit-sdr-windows.zip (pré-release « Kit SDR » du dépôt) et dézippe-le À CÔTÉ "
    "de TinySA-Monitor.exe (dossier « kit-sdr ») : hackrf_sweep, rtl_power, rx_tools et SoapySDR sont trouvés tout seuls. "
    "Restent à installer à part : le pilote USB (Zadig), et pour un SDRplay ou un WiNRADiO, le logiciel de la marque.":
        "Easiest: the SDR kit. Download kit-sdr-windows.zip (the “Kit SDR” pre-release of the repository) and unzip it "
        "NEXT TO TinySA-Monitor.exe (“kit-sdr” folder): hackrf_sweep, rtl_power, rx_tools and SoapySDR are found "
        "automatically. Still to install separately: the USB driver (Zadig), and for an SDRplay or a WiNRADiO, the "
        "brand's software.",
    "Pile": "Battery",
    "RF = niveau reçu par le récepteur (dBm) · Antenne = A, B ou aucune · Diversity = part du\ntemps sur chaque antenne et "
    "bascules (beaucoup de bascules / « aucune » = antennes à revoir).":
        "RF = level received by the receiver (dBm) · Antenna = A, B or none · Diversity = share of\ntime on each antenna "
        "and switches (many switches / “none” = check the antennas).",
    "RF bien plus faible qu'en répétition ({} dB)": "RF much weaker than in rehearsal ({} dB)",
    "Retient ce qui a été appris pendant la répétition (gardé dans les réglages) : il sert en mode 🎤 Spectacle.":
        "Keeps what was learned during rehearsal (saved in the settings): it is used in 🎤 Show mode.",
    "Rien d'appris pour l'instant : laisse tourner la répétition (30 s par micro au moins).":
        "Nothing learned yet: let the rehearsal run (at least 30 s per mic).",
    "Récepteur": "Receiver",
    "Récepteurs Shure (télémétrie)": "Shure receivers (telemetry)",
    "Se connecte aux récepteurs (et retient les adresses).": "Connects to the receivers (and remembers the addresses).",
    "Son plus fort qu'en répétition ({} dB)": "Sound louder than in rehearsal ({} dB)",
    "Surveillance : comme d'habitude.\n🎭 Répétition : le moniteur APPREND ce qui est normal pour chaque micro (niveau, "
    "bruit, son).\n🎤 Spectacle : il prévient quand un micro s'écarte de sa répétition.":
        "Monitoring: as usual.\n🎭 Rehearsal: the monitor LEARNS what is normal for each mic (level, noise, sound).\n"
        "🎤 Show: it warns when a mic drifts away from its rehearsal.",
    "Tes récepteurs Shure en réseau (ULX-D, QLX-D, SLX-D, Axient Digital…) disent eux-mêmes ce qu'ils reçoivent : niveau "
    "RF, antenne utilisée, son, pile. Tape leur adresse IP (séparées par des virgules) puis":
        "Your networked Shure receivers (ULX-D, QLX-D, SLX-D, Axient Digital…) tell you themselves what they receive: RF "
        "level, antenna in use, sound, battery. Type their IP address (comma-separated) then",
    "V8 : niveau RF, antenne A / B, diversity, son et pile que voient tes récepteurs\nShure en réseau, reliés à ta liste ; "
    "comparés au SDR dans le moniteur multicanal.":
        "V8: RF level, antenna A / B, diversity, sound and battery seen by your networked\nShure receivers, linked to your "
        "list; compared with the SDR in the multichannel monitor.",
    "aucune : {} %": "none: {} %",
    "connexion fermée par le récepteur": "connection closed by the receiver",
    "connexion…": "connecting…",
    "plus de réponse depuis 15 s": "no answer for 15 s",
    "récepteur": "receiver",
    "{} / {} : décalage {} dB (± {})": "{} / {}: offset {} dB (± {})",
    "{} / {} : pas assez de mesures communes": "{} / {}: not enough common measurements",
    "{} bascules": "{} switches",
    "⚠ Pas encore de répétition gardée : passe en 🎭 Répétition pendant les balances.":
        "⚠ No rehearsal saved yet: switch to 🎭 Rehearsal during the soundcheck.",
    "🎤 Comparé à la répétition « {} » ({} micros).": "🎤 Compared with the rehearsal “{}” ({} mics).",
    "🎤 Spectacle (comparer)": "🎤 Show (compare)",
    "🎭 J'apprends : {} micro(s) appris (30 s de mesures chacun au moins).":
        "🎭 Learning: {} mic(s) learned (at least 30 s of measurements each).",
    "🎭 Répétition (apprendre)": "🎭 Rehearsal (learn)",
    "💾 Garder la répétition": "💾 Keep the rehearsal",
    "💾 Répétition gardée : {} micros. Passe en 🎤 Spectacle pour comparer.":
        "💾 Rehearsal saved: {} mics. Switch to 🎤 Show to compare.",
    "📦 avec {}": "📦 with {}",
    "📶 Récepteurs Shure": "📶 Shure receivers",
    "📶 Récepteurs Shure en réseau (télémétrie)…": "📶 Networked Shure receivers (telemetry)…",
})
SAME_TEMPLATES += ["< SET {} METER_RATE {} >"]

# ---------------------------------------------------------------- V8 étape 12 : fondations + compléments (lot D)
EXACT.update({k: k for k in ("ALARM|WARN|FAULT|ERROR|INTERFERENCE|RF_INT_DET", "CLEAR", "NONE", "_lastFL")})
EXACT.update({
    " · stabilité ± {} / ± {} dB": " · stability ± {} / ± {} dB",
    " · {} HORS de la fenêtre : pas surveillées par ce SDR": " · {} OUTSIDE the window: not monitored by this SDR",
    " · {} démodulées en continu": " · {} demodulated continuously",
    " · {} à tour de rôle (toutes les 5 s)": " · {} in turn (every 5 s)",
    " · ⚠ {} critique(s) sans récepteur : le PC ne suit pas, baisse le nombre de micros ou ferme d'autres fenêtres":
        " · ⚠ {} critical one(s) without a receiver: the PC can't keep up, reduce the number of mics or close other windows",
    "1 jour": "1 day",
    "Alerte du récepteur": "Receiver alert",
    "Alertes": "Alerts",
    "Antenne {} presque jamais utilisée : câble, antenne ou booster à vérifier":
        "Antenna {} almost never used: check the cable, antenna or booster",
    "Balance": "Soundcheck",
    "Ce qu'il faut savoir avant d'enregistrer du son.": "What you should know before recording sound.",
    "Ce que le SDR couvre vraiment et ce que le PC arrive à démoduler en ce moment.":
        "What the SDR really covers and what the PC manages to demodulate right now.",
    "Ce qui est arrivé au micro, dans l'ordre. Double-clic = aller à ce moment dans l'IQ.":
        "What happened to the mic, in order. Double-click = go to that moment in the IQ.",
    "Chaque micro dans chaque phase apprise : écart au bruit, bruit de fond, niveau du son.\nUn micro bien plus faible au "
    "show qu'à la balance = antenne masquée, pack mal placé…":
        "Each mic in each learned phase: margin above noise, noise floor, sound level.\nA mic much weaker during the show "
        "than at soundcheck = antenna blocked, pack badly placed…",
    "Charge du calcul": "Processing load",
    "Conservation : {} (réglable dans 📡 Réglages SDR).": "Kept for: {} (adjustable in 📡 SDR settings).",
    "D'accord pour enregistrer ?": "OK to record?",
    "Disque libre": "Free disk",
    "Début du spectacle": "Start of the show",
    "Déconnexions du SDR": "SDR disconnections",
    "Enregistrements gardés :": "Recordings kept:",
    "Enregistrer du son ?": "Record sound?",
    "Exploitation": "Running the show",
    "File du son": "Sound queue",
    "IQ enregistré": "Recorded IQ",
    "Incidents gardés": "Incidents kept",
    "La phase du show : balance, répétition, début, exploitation… (tu peux en taper une autre).\nChaque phase apprise est "
    "gardée à part ; on compare le show à celle qu'on choisit.":
        "The phase of the show: soundcheck, rehearsal, start, running… (you can type another one).\nEach learned phase is "
        "kept separately; the show is compared with the one you choose.",
    "La santé du SDR et du PC : échantillons perdus, retard, charge, mémoire, disque,\ndéconnexions. Orange / rouge = la "
    "surveillance n'est plus complète.":
        "Health of the SDR and the PC: lost samples, delay, load, memory, disk,\ndisconnections. Orange / red = "
        "monitoring is no longer complete.",
    "Le canal voisin monte": "The adjacent channel is rising",
    "Le récepteur signale : {} {}": "The receiver reports: {} {}",
    "Le son démodulé contient des voix : artistes, équipes, public. Avant d'enregistrer :\n• n'enregistre que ce qui sert "
    "(preuve d'un brouillage, réglage d'un micro) ;\n• garde-le peu de temps (effacement automatique après la durée "
    "choisie) ;\n• ne le diffuse pas, et préviens les personnes concernées si les règles du lieu le demandent.\nLes "
    "enregistrements IQ des incidents contiennent aussi le son (on peut les réécouter).":
        "Demodulated sound contains voices: artists, crews, audience. Before recording:\n• only record what is useful "
        "(proof of interference, setting up a mic);\n• keep it for a short time (automatic deletion after the chosen "
        "period);\n• do not share it, and inform the people concerned if the venue's rules require it.\nIncident IQ "
        "recordings also contain the sound (they can be listened to again).",
    "Le son, l'IQ et les dossiers d'incident plus vieux que ça sont effacés tout seuls\n(ils contiennent des voix : ne les "
    "garde pas plus que nécessaire).":
        "Sound, IQ and incident folders older than this are deleted automatically\n(they contain voices: don't keep them "
        "longer than necessary).",
    "Mémoire du tampon IQ": "IQ buffer memory",
    "Pertes signalées par le SDR": "Losses reported by the SDR",
    "Phases": "Phases",
    "Pile du micro presque vide ({} barre)": "Mic battery almost empty ({} bar)",
    "Recalages d'horloge": "Clock resyncs",
    "Retard du calcul": "Processing delay",
    "Rouge = du son est enregistré en ce moment ; orange = il le sera si une alarme part.\nLes enregistrements sont effacés "
    "tout seuls après la durée choisie (📡 Réglages SDR).":
        "Red = sound is being recorded right now; orange = it will be if an alarm goes off.\nRecordings are deleted "
        "automatically after the chosen period (📡 SDR settings).",
    "RÉCEPTEUR": "RECEIVER",
    "Récepteurs virtuels": "Virtual receivers",
    "Répétition": "Rehearsal",
    "Signal plus large que prévu": "Signal wider than expected",
    "Signal plus large que prévu ({} kHz au lieu de {}) : déviation trop forte, pack déréglé, ou deux émetteurs l'un sur "
    "l'autre.": "Signal wider than expected ({} kHz instead of {}): deviation too high, pack misadjusted, or two "
                "transmitters on top of each other.",
    "Son enregistré": "Recorded sound",
    "Son enregistré et vie privée": "Recorded sound and privacy",
    "Son haché ({} coupures en 10 s) : contact, câble de capsule, squelch trop haut ?":
        "Choppy sound ({} cuts in 10 s): contact, capsule cable, squelch too high?",
    "Souffle dans le son ({} dBFS entre les mots) : réglage du compander, pack fatigué, ou RF juste.":
        "Hiss in the sound ({} dBFS between words): compander setting, tired pack, or marginal RF.",
    "Spectre au moment de l’incident": "Spectrum at the time of the incident",
    "Système": "System",
    "Waterfall du micro (± 150 kHz, le plus récent en haut)": "Mic waterfall (± 150 kHz, newest at the top)",
    "balaye, écoute et démodule": "sweeps, listens and demodulates",
    "bruit {}": "noise {}",
    "dans {} s : {}": "in {} s: {}",
    "disque presque plein : IQ non gardé": "disk almost full: IQ not kept",
    "durée : {} s": "duration: {} s",
    "il y a {} s : {}": "{} s ago: {}",
    "ne démodule pas": "does not demodulate",
    "son {}": "sound {}",
    "tout garder": "keep everything",
    "{} fréquences dans la fenêtre : niveau, voisins et largeur de toutes":
        "{} frequencies in the window: level, neighbours and width of all",
    "{} jours": "{} days",
    "{} pertes de diversité (aucune antenne) : micro hors de portée ?": "{} diversity losses (no antenna): mic out of range?",
    "Échantillons perdus": "Lost samples",
    "écoute et démodule ({} MHz d'un coup)": "listens and demodulates ({} MHz at once)",
    "⏺ SON ENREGISTRÉ": "⏺ SOUND RECORDING",
    "⏺ prêt à enregistrer sur alarme": "⏺ ready to record on alarm",
    "⚠ SDR décroché ({}) : nouvel essai dans {} s…": "⚠ SDR dropped ({}): retrying in {} s…",
    "⚠ « {} » pas encore apprise : choisis « 🎭 Apprendre » pendant cette phase.":
        "⚠ “{}” not learned yet: choose “🎭 Learn” during this phase.",
    "🎤 Comparer à la phase": "🎤 Compare with the phase",
    "🎤 Comparé à « {} » ({} micros, {}).": "🎤 Compared with “{}” ({} mics, {}).",
    "🎭 Apprendre la phase": "🎭 Learn the phase",
    "🎭 J'apprends « {} » : {} micro(s) appris (30 s de mesures chacun au moins).":
        "🎭 Learning “{}”: {} mic(s) learned (at least 30 s of measurements each).",
    "💾 « {} » gardée : {} micros. Choisis « 🎤 Comparer » pendant le show.":
        "💾 “{}” saved: {} mics. Choose “🎤 Compare” during the show.",
    "📦 Incident : {} · {} MHz": "📦 Incident: {} · {} MHz",
})
SAME_TEMPLATES += ["color: {}; font-weight: bold;", "<p class='muted'>{} · {}", " : {} kHz",
                   "<h2>{}</h2><img src='{}' style='width:100%;max-width:900px;image-rendering:pixelated'>", "{} Mo · {} s"]
EXACT["Fenêtre : {} – {} MHz"] = "Window: {} – {} MHz"
EXACT.update({                                      # étape 12 : rangement (menu SDR dans l'ordre d'usage)
    "Tous tes micros qui tiennent dans la fenêtre du SDR, surveillés en même temps (RF, son, santé). Clique une ligne "
    "pour l'écouter.": "All your mics that fit in the SDR window, monitored at the same time (RF, sound, health). Click a "
                       "line to listen to it.",
    "Toutes tes fréquences de la fenêtre sont mesurées en même temps (niveau, voisins, largeur). Les plus\nimportantes "
    "ont en plus un « récepteur virtuel » qui les démodule : son, déviation, dérive, coupures.":
        "All your frequencies in the window are measured at the same time (level, neighbours, width). The most\n"
        "important ones also get a “virtual receiver” that demodulates them: sound, deviation, drift, cuts.",
    "⏱ Temps réel (un bout de bande, sans trou)…": "⏱ Real time (a slice of band, without gaps)…",
    "🎧 Écouter un micro…": "🎧 Listen to a mic…",
    "📡 Moniteur multicanal (tous mes micros d'un coup)…": "📡 Multichannel monitor (all my mics at once)…",
    "📡 Réglages SDR (mon SDR, sensibilité)…": "📡 SDR settings (my SDR, sensitivity)…",
    "📡 SDR (écoute et moniteur)": "📡 SDR (listening and monitor)",
    "📦 Rejouer un incident…": "📦 Replay an incident…",
    "📶 Récepteurs Shure (pile, antennes)…": "📶 Shure receivers (battery, antennas)…",
})

# ---------------------------------------------------------------- V8 étape 13 : récepteurs d'autres marques
EXACT.update({k: k for k in ("AX", "XB", "MSG", "None", "Push 60 100 3\r", "Wisycom (MRK, MCR)",
                             "Sennheiser EW-DX / Digital 6000 / SpeechLine (SSC)", "Sennheiser evolution G3 / G4 / 2000",
                             "Shure (ULX-D, QLX-D, SLX-D, Axient Digital)")})
EXACT.update({
    "Adresse IP du récepteur (le port habituel de la marque est mis tout seul ; sinon « adresse:port »).":
        "IP address of the receiver (the brand's usual port is added automatically; otherwise “address:port”).",
    "Adresse illisible : tape une adresse IP (ex. 192.168.1.50).": "Unreadable address: type an IP address (e.g. 192.168.1.50).",
    "Ajoute ce récepteur et s'y connecte (retenu dans les réglages).": "Adds this receiver and connects to it (saved in the settings).",
    "Aucun récepteur : choisis la marque, tape une adresse puis ＋ Ajouter.": "No receiver: choose the brand, type an address then ＋ Add.",
    "Autre marque (Sony, Audio-Technica, Lectrosonics, Mipro…)": "Other brand (Sony, Audio-Technica, Lectrosonics, Mipro…)",
    "La marque / famille du récepteur (le protocole réseau en dépend).": "The brand / family of the receiver (the network protocol depends on it).",
    "Marque :": "Brand:",
    "Pas de protocole réseau public connu pour cette marque. Avec une doc ou une capture réseau (Wireshark) de son logiciel, "
    "on peut l'ajouter.": "No known public network protocol for this brand. With documentation or a network capture "
                         "(Wireshark) of its software, it can be added.",
    "Retire le récepteur choisi de la liste.": "Removes the selected receiver from the list.",
    "Récepteurs en réseau (télémétrie)": "Networked receivers (telemetry)",
    "Tes récepteurs en réseau disent eux-mêmes ce qu'ils reçoivent : niveau RF, antenne, son, pile, alertes. Choisis la "
    "marque, tape l'adresse IP, puis": "Your networked receivers tell you themselves what they receive: RF level, antenna, "
                                      "sound, battery, alerts. Choose the brand, type the IP address, then",
    "Tes récepteurs. Choisis-en un puis « Retirer » (ou touche Suppr).": "Your receivers. Pick one then “Remove” (or the Delete key).",
    "V8 : niveau RF, antenne A / B, diversity, son, pile et alertes de tes récepteurs en\nréseau (Shure, Sennheiser), reliés "
    "à ta liste ; comparés au SDR dans le moniteur.": "V8: RF level, antenna A / B, diversity, sound, battery and alerts of "
                                                     "your networked\nreceivers (Shure, Sennheiser), linked to your list; "
                                                     "compared with the SDR in the monitor.",
    "Wisycom n'a pas de protocole public (Wisycom Manager parle en privé avec ses récepteurs). Pour l'ajouter : une capture "
    "réseau (Wireshark) entre Wisycom Manager et un récepteur.": "Wisycom has no public protocol (Wisycom Manager talks "
                                                                 "privately with its receivers). To add it: a network "
                                                                 "capture (Wireshark) between Wisycom Manager and a receiver.",
    "pas de réponse": "no answer",
    "📶 Récepteurs en réseau": "📶 Networked receivers",
    "📶 Récepteurs en réseau (Shure, Sennheiser…)…": "📶 Networked receivers (Shure, Sennheiser…)…",
    "Retirer": "Remove",
    "＋ Ajouter": "＋ Add",
    "Adresse :": "Address:",
})

# ---------------------------------------------------------------- V8 étape 14 : fiabilité (2ᵉ audit)
EXACT.update({k: k for k in ("Found HackRF|Serial number", "SoapySDRUtil",
                             "error|not found|no .*device|failed|impossible|denied")})
EXACT.update({
    "(il y a {})": "({} ago)",
    "il y a {}": "{} ago",
    "{} min": "{} min",
    "Ce modèle n'est pas pris en charge.": "This model is not supported.",
    "Ce que l'appli garde, et quand :\n• En mémoire seulement (rien sur le disque) : le son que tu écoutes, et les ~20 "
    "dernières secondes de signal brut (IQ) du moniteur. Tout disparaît à l'arrêt.\n• Sur le disque, uniquement quand :\n"
    "  – tu cliques « ⏺ Enregistrer le son » ou « Enregistrer l'IQ » (jusqu'à ce que tu arrêtes) ;\n  – une alarme part et "
    "« Sur alarme : garder le son » est coché (10 s avant + 10 s après) ;\n  – un incident du moniteur est noté (dossier : "
    "IQ d'avant et d'après, mesures, rapport).\n• Où : dans le dossier des journaux (enregistrements_audio, "
    "enregistrements_iq, incidents).\n• Contenu : des VOIX (artistes, équipes, public) — l'IQ aussi, on peut le "
    "réécouter.\n• Combien de temps : effacés tout seuls après la durée choisie (vérifié toutes les heures). L'appli "
    "efface SES fichiers ; elle ne peut rien pour les copies faites ailleurs (clé USB, sauvegarde, e-mail).\nN'enregistre "
    "que ce qui sert, ne le diffuse pas, et préviens les personnes concernées si les règles du lieu le demandent.":
        "What the app keeps, and when:\n• In memory only (nothing on disk): the sound you listen to, and the last ~20 "
        "seconds of raw signal (IQ) of the monitor. Everything is gone when it stops.\n• On disk, only when:\n  – you "
        "click “⏺ Record sound” or “Record IQ” (until you stop);\n  – an alarm goes off and “On alarm: keep the sound” is "
        "ticked (10 s before + 10 s after);\n  – a monitor incident is noted (folder: IQ before and after, measurements, "
        "report).\n• Where: in the logs folder (enregistrements_audio, enregistrements_iq, incidents).\n• Content: VOICES "
        "(artists, crews, audience) — the IQ too, it can be listened to again.\n• How long: deleted automatically after "
        "the chosen period (checked every hour). The app deletes ITS files; it can do nothing about copies made "
        "elsewhere (USB stick, backup, e-mail).\nOnly record what is useful, don't share it, and inform the people "
        "concerned if the venue's rules require it.",
    "Débit tenu": "Rate sustained",
    "Essai du SDR": "SDR test",
    "Essaie VRAIMENT le SDR branché (quelques secondes) : outil trouvé, SDR vu par son pilote,\nsignal reçu, débit tenu. "
    "Ferme d'abord les autres logiciels qui l'utilisent.": "REALLY tries the connected SDR (a few seconds): tool found, "
                                                           "SDR seen by its driver,\nsignal received, rate sustained. "
                                                           "Close other software using it first.",
    "G39DDCAPI.dll introuvable : installe le logiciel WiNRADiO": "G39DDCAPI.dll not found: install the WiNRADiO software",
    "Outil du SDR trouvé": "SDR tool found",
    "SDR détecté (pilote OK)": "SDR detected (driver OK)",
    "Signal reçu (IQ)": "Signal received (IQ)",
    "Suivi": "Coverage",
    "Valeurs d'il y a {} : le récepteur ne répond plus (réseau, alimentation ?).":
        "Values from {} ago: the receiver no longer answers (network, power?).",
    "aucune donnée : SDR occupé par un autre logiciel ?": "no data: SDR busy with other software?",
    "code de sortie {}": "exit code {}",
    "enregistrement interrompu pendant l'écriture (fichier .part) : IQ incomplet":
        "recording interrupted while writing (.part file): incomplete IQ",
    "fichier IQ vide ou presque (moins de 0,05 s)": "IQ file empty or nearly (less than 0.05 s)",
    "flux figé : plus de données depuis {} s": "frozen stream: no data for {} s",
    "le PC ou l'USB ne suit pas (câble, port USB 3, autre logiciel)": "the PC or USB can't keep up (cable, USB 3 port, other software)",
    "le tinySA ou le balayage s'en occupe": "the tinySA or the sweep handles it",
    "vérifié à l'ouverture du flux": "checked when the stream opens",
    "{} MS/s reçus sur {} demandés": "{} MS/s received out of {} requested",
    "{} Mo en {} s": "{} MB in {} s",
    "{} introuvable : dézippe le kit SDR à côté de l'appli (ou installe les outils)":
        "{} not found: unzip the SDR kit next to the app (or install the tools)",
    "… en attente des premières mesures": "… waiting for the first measurements",
    "… essai en cours (quelques secondes)": "… test running (a few seconds)",
    "⏸ mesure ancienne": "⏸ old measurement",
    "■ arrêté": "■ stopped",
    "○ PAS surveillé (hors fenêtre)": "○ NOT monitored (outside the window)",
    "● RF + son en continu": "● RF + sound continuously",
    "◐ RF en continu, son à tour de rôle": "◐ RF continuously, sound in turn",
    "⚠ Flux du SDR figé (plus de données depuis {}) : je relance le SDR…": "⚠ SDR stream frozen (no data for {}): restarting the SDR…",
    "⚠ Le SDR est utilisé (moniteur, écoute ou temps réel) : arrête-les d'abord.":
        "⚠ The SDR is in use (monitor, listening or real time): stop them first.",
    "⚠ dégradée (pertes ou retard)": "⚠ degraded (losses or delay)",
    "✔ Ton SDR marche : il peut surveiller et écouter.": "✔ Your SDR works: it can monitor and listen.",
    "✗ Essai impossible : {}": "✗ Test impossible: {}",
    "✗ Il y a un souci : regarde la 1re ligne en rouge, puis « Comment l'installer ? ».":
        "✗ There is a problem: look at the first line in red, then “How to install it?”.",
    "🔌 Tester mon SDR": "🔌 Test my SDR",
})
EXACT[" · son démodulé pour le plus possible (selon le PC), les autres à tour de rôle"] = \
    " · sound demodulated for as many as possible (depending on the PC), the others in turn"

# ---------------------------------------------------------------- V8 étape 16 : le SDR au cœur (panneaux, modes)
EXACT.update({k: k for k in ("SdrMicsPanel", "SdrReceiverPanel", "SdrSpectrumPanel", "SdrWaterfallPanel", "⏺ IQ")})
EXACT.update({
    "A gauche / B droite": "A left / B right",
    "Au casque : A dans l'oreille gauche, B dans la droite (sinon mélangés).":
        "On headphones: A in the left ear, B in the right (otherwise mixed).",
    "B est hors de la fenêtre du SDR ({} MHz autour de A) : il ne s'entend pas.":
        "B is outside the SDR window ({} MHz around A): it can't be heard.",
    "Ce que tu utilises : 📟 tinySA, 📡 SDR, ou les deux (combiné). Chaque mode a sa disposition de base\net des "
    "pré-affichages ; ensuite tu bouges les panneaux comme tu veux (ta disposition est retenue).":
        "What you use: 📟 tinySA, 📡 SDR, or both (combined). Each mode has its basic layout\nand preset views; then you "
        "move the panels as you like (your layout is remembered).",
    "Charge du calcul et saturation de l'entrée du SDR.": "Processing load and SDR input saturation.",
    "Choisir le SDR, sa sensibilité, le tester.": "Choose the SDR, its sensitivity, test it.",
    "Clic = écouter": "Click = listen",
    "Clic = écouter (A) · clic droit = B": "Click = listen (A) · right-click = B",
    "Deuxième récepteur, écouté en même temps que A (dans la même fenêtre du SDR).":
        "Second receiver, heard at the same time as A (in the same SDR window).",
    "Enregistre ce que tu entends (WAV). Demande ton accord la 1re fois (voix).":
        "Records what you hear (WAV). Asks for your consent the first time (voices).",
    "Enregistre le signal brut de toute la fenêtre (gros fichiers), à relire dans le Temps réel.":
        "Records the raw signal of the whole window (big files), to replay in Real time.",
    "Finesse du spectre (plus grand = plus fin, plus de calcul).": "Spectrum resolution (larger = finer, more processing).",
    "Fréquence du récepteur B (clic droit sur le spectre ou un micro pour y aller).":
        "Frequency of receiver B (right-click on the spectrum or a mic to go there).",
    "Fréquence écoutée (récepteur A). Molette / flèches = d'un pas ; clique sur le spectre ou un micro pour y aller.":
        "Listened frequency (receiver A). Wheel / arrows = one step; click the spectrum or a mic to go there.",
    "Garde le plus haut niveau vu à chaque fréquence (repérer un signal bref).":
        "Keeps the highest level seen at each frequency (to spot a short signal).",
    "Lance / arrête le SDR : spectre sans trou, écoute de A (et B), surveillance de la fenêtre.":
        "Starts / stops the SDR: gap-free spectrum, listening to A (and B), monitoring of the window.",
    "Niveau SDR": "SDR level",
    "Pas de la molette.": "Wheel step.",
    "Pré-affichages SDR (ensuite, bouge tout comme tu veux)": "SDR preset views (then move everything as you like)",
    "S-mètre de A : niveau reçu dans le canal (dBm, à caler avec un tinySA).":
        "S-meter of A: level received in the channel (dBm, to calibrate with a tinySA).",
    "S-mètre de B.": "S-meter of B.",
    "Squelch : en dessous de ce niveau, le son est coupé (pas de souffle entre deux phrases).":
        "Squelch: below this level the sound is muted (no hiss between sentences).",
    "Tes fréquences dans la fenêtre du SDR. Clic = l'écouter (A) ; clic droit = en B.":
        "Your frequencies in the SDR window. Click = listen to it (A); right-click = in B.",
    "Ton SDR (📡 Réglages SDR pour le changer).": "Your SDR (📡 SDR settings to change it).",
    "Tu peux aussi faire glisser les bandes A et B.": "You can also drag the A and B bands.",
    "Un seul écran : tire le panneau « 📡 SDR · Spectre » par sa barre de titre pour en faire une fenêtre, ou branche le "
    "2ᵉ écran.": "Only one screen: drag the “📡 SDR · Spectrum” panel by its title bar to make it a window, or connect "
                 "the 2nd screen.",
    "charge {} % · saturation {} %": "load {} % · saturation {} %",
    "{} autre(s) fréquence(s) hors de la fenêtre du SDR : clique un micro ou tape sa fréquence en A pour y aller.":
        "{} other frequency(ies) outside the SDR window: click a mic or type its frequency in A to go there.",
    "↺ Disposition de base du mode": "↺ Basic layout of the mode",
    "⏺ Son": "⏺ Sound",
    "■ Arrêter le SDR": "■ Stop the SDR",
    "▶ Démarrer le SDR": "▶ Start the SDR",
    "⚙ Réglages SDR": "⚙ SDR settings",
    "⚠ Le SDR est déjà pris (moniteur, écoute ou temps réel) : ferme-les d'abord.":
        "⚠ The SDR is already in use (monitor, listening or real time): close them first.",
    "⚠ SDR arrêté : {}": "⚠ SDR stopped: {}",
    "👁 Surveiller mes micros": "👁 Monitor my mics",
    "📟 Mode tinySA seul": "📟 tinySA mode only",
    "📟 Mode tinySA.": "📟 tinySA mode.",
    "📟 tinySA": "📟 tinySA",
    "📟+📡 Combiné": "📟+📡 Combined",
    "📟+📡 Mode combiné (tinySA + SDR)": "📟+📡 Combined mode (tinySA + SDR)",
    "📟+📡 Mode combiné : tinySA et SDR côte à côte, tout est déplaçable.":
        "📟+📡 Combined mode: tinySA and SDR side by side, everything can be moved.",
    "📡 Mode SDR (panneaux SDR à l'écran)": "📡 SDR mode (SDR panels on screen)",
    "📡 Mode SDR : tout est déplaçable (barres de titre), ta disposition est retenue.":
        "📡 SDR mode: everything can be moved (title bars), your layout is remembered.",
    "📡 Réglages SDR…": "📡 SDR settings…",
    "📡 SDR · Mes micros": "📡 SDR · My mics",
    "📡 SDR · Récepteur": "📡 SDR · Receiver",
    "📡 SDR · Spectre": "📡 SDR · Spectrum",
    "📡 SDR · Waterfall": "📡 SDR · Waterfall",
    "📡 {} · fenêtre {} MHz": "📡 {} · window {} MHz",
    "🔎 Analyser le spectre": "🔎 Analyze the spectrum",
    "🖥 Spectre SDR sur l'autre écran": "🖥 SDR spectrum on the other screen",
})
SAME_TEMPLATES += ["{} · {} dBm", "sdr_{}_{}MHz.wav"]
TEMPLATES["FFT {}"] = "FFT {}"
EXACT.update({
    "V8 : le SDR à l'écran (récepteur, spectre, waterfall, mes micros) à la place du spectre tinySA.\nTous les panneaux se "
    "déplacent, s'empilent, se détachent ; ta disposition est retenue.":
        "V8: the SDR on screen (receiver, spectrum, waterfall, my mics) instead of the tinySA spectrum.\nAll panels can be "
        "moved, stacked, detached; your layout is remembered.",
    "V8 : tinySA et SDR ensemble, les deux spectres côte à côte.": "V8: tinySA and SDR together, both spectra side by side.",
    "V8 : la disposition tinySA seule (les panneaux SDR sont rangés, le SDR s'arrête).":
        "V8: the tinySA layout only (SDR panels put away, the SDR stops).",
    "📡 Mode SDR": "📡 SDR mode",
    "📟+📡 Mode combiné": "📟+📡 Combined mode",
    "📟 Mode tinySA": "📟 tinySA mode",
})

# ---------------------------------------------------------------- V8 étapes 16 bis / ter et 17
EXACT.update({k: k for k in ("DejaVu Sans Mono", "color: #8e8e93; font-family: monospace;", "SDR ", "SDR 1")})
EXACT.update({
    "(celui des Réglages SDR)": "(the one in SDR settings)",
    "4 SDR au plus.": "4 SDRs at most.",
    "Couper / remettre le son.": "Mute / unmute.",
    "Début · centre · fin de la fenêtre du SDR, et sa largeur.": "Start · centre · end of the SDR window, and its width.",
    "Démarre ou arrête le poste choisi.": "Starts or stops the selected SDR.",
    "Dézoomer.": "Zoom out.",
    "Force du signal reçu dans le canal écouté (dBm) :\nrouge à gauche = très faible (risque de décrochage), orange = "
    "faible, vert = bon,\nrouge à droite = trop fort (le SDR sature : baisse la sensibilité).\nLe petit trait orange = le "
    "plus fort récemment. Valeurs justes si le SDR est calé (avec un tinySA).":
        "Strength of the signal received in the listened channel (dBm):\nred on the left = very weak (dropout risk), orange "
        "= weak, green = good,\nred on the right = too strong (the SDR saturates: lower the sensitivity).\nThe small orange "
        "mark = the strongest recently. Values are right if the SDR is calibrated (with a tinySA).",
    "Fréquence : molette sur un chiffre = le change ; flèches ←/→ puis ↑/↓ au clavier ;\ndouble-clic = taper la "
    "fréquence.": "Frequency: wheel over a digit = changes it; ←/→ then ↑/↓ arrows on the keyboard;\ndouble-click = type "
                  "the frequency.",
    "Le 1er SDR reste (il suffit de ne pas le démarrer).": "The 1st SDR stays (just don't start it).",
    "Le type d'appareil que tu écoutes : règle tout seul la démodulation, le compander et la désaccentuation\n(Sennheiser "
    "evolution, Shure, Wisycom, ears, talkies…).": "The type of device you listen to: sets demodulation, compander and "
                                                   "de-emphasis automatically\n(Sennheiser evolution, Shure, Wisycom, "
                                                   "IEMs, walkie-talkies…).",
    "Mes SDR": "My SDRs",
    "Micro préc.": "Prev. mic",
    "Micro suiv.": "Next mic",
    "Modèle": "Model",
    "Nom et n° de série se tapent ; Modèle et Scènes se choisissent dans leur liste.":
        "Name and serial number are typed; Model and Scenes are picked from their list.",
    "N° de série": "Serial number",
    "Ouvre la carte : fais glisser un SDR sur une scène pour qu'il la surveille.":
        "Opens the map: drag an SDR onto a scene so it monitors it.",
    "Pas : clic sur le spectre et micro suivant arrondis à ce pas.": "Step: clicks on the spectrum and next mic rounded to this step.",
    "Pas de flux": "No stream",
    "Plusieurs SDR peuvent tourner en même temps que tes tinySA : chacun surveille et écoute les micros de SES scènes "
    "(aucune scène = tout le site), avec ses propres panneaux. Place-les sur la 🗺 carte comme les tinySA.":
        "Several SDRs can run at the same time as your tinySAs: each one monitors and listens to the mics of ITS scenes "
        "(no scene = the whole site), with its own panels. Place them on the 🗺 map like the tinySAs.",
    "RBW (finesse) · taille de FFT · fenêtre · détecteur · charge · échelle ; et le curseur.":
        "RBW (resolution) · FFT size · window · detector · load · scale; and the cursor.",
    "Retire le poste choisi (le 1er reste).": "Removes the selected SDR (the 1st stays).",
    "SATURATION {} %": "SATURATION {} %",
    "Scènes": "Scenes",
    "Spectre du son entendu (0 – 15 kHz) : voix, souffle, sifflement, ronflette.":
        "Spectrum of the heard sound (0 – 15 kHz): voice, hiss, whistle, hum.",
    "Toute la fenêtre du SDR.": "The whole SDR window.",
    "Un poste SDR de plus (4 au plus) : ses panneaux apparaissent en onglets, déplace-les où tu veux.":
        "One more SDR (4 at most): its panels appear as tabs, move them wherever you like.",
    "Zoom du canal écouté (A) : la porteuse, sa largeur, les voisins proches.":
        "Zoom on the listened channel (A): the carrier, its width, close neighbours.",
    "Zoomer autour de A.": "Zoom around A.",
    "charge {} %": "load {} %",
    "dBFS (non calé)": "dBFS (uncalibrated)",
    "dBm (calé)": "dBm (calibrated)",
    "kHz (son)": "kHz (sound)",
    "kHz autour de A": "kHz around A",
    "moyenne + crête": "average + peak",
    "trop fort": "too strong",
    "très faible": "very weak",
    "faible": "weak",
    "bon": "good",
    "fort": "strong",
    "{} — à éviter": "{} — avoid",
    "Écouter le micro précédent (A).": "Listen to the previous mic (A).",
    "Écouter le micro suivant (A).": "Listen to the next mic (A).",
    "▶ en marche": "▶ running",
    "⚠ Un autre poste utilise déjà un {} : donne à chacun son n° de série (📡 Mes SDR).":
        "⚠ Another SDR slot already uses a {}: give each one its serial number (📡 My SDRs).",
    "＋ Ajouter un SDR": "＋ Add an SDR",
    "🎧 Écoute :": "🎧 Listening:",
    "📡 Mes SDR (plusieurs, scènes, carte)…": "📡 My SDRs (several, scenes, map)…",
    "🗺 Carte": "🗺 Map",
    "Fréquence": "Frequency",
    "Fréquence (MHz) :": "Frequency (MHz):",
})
SAME_TEMPLATES += ["{} · {} · {} MHz ({} MHz)", "RBW {} · FFT {} · Blackman · ", "⌖ {} MHz · {} dBFS", "dock_sdr{}_", "{} Hz",
                   "color: {}; font-weight: bold; font-size: 18px;"]
SAME_TEMPLATES += ["{} dBm · {}"]
EXACT.update({
    "V8 : plusieurs SDR en même temps que les tinySA, chacun ses scènes et ses panneaux, placés sur la\ncarte comme les "
    "tinySA (glisser un SDR sur une scène = il la surveille).":
        "V8: several SDRs at the same time as the tinySAs, each with its scenes and panels, placed on the\nmap like the "
        "tinySAs (drag an SDR onto a scene = it monitors it).",
    "📡 Mes SDR": "📡 My SDRs",
})

# ---------------------------------------------------------------- V8 étape 18 : double-clic, pavé numérique
EXACT.update({
    "Tes fréquences dans la fenêtre du SDR. Clic = l'écouter (A) ; clic droit = en B, ou la mettre sur une touche du pavé "
    "numérique.": "Your frequencies in the SDR window. Click = listen (A); right-click = in B, or put it on a numeric "
                  "keypad key.",
    "Tes micros les plus importants sur les touches 1 à 9 du PAVÉ NUMÉRIQUE : un appui = le SDR se cale\ndessus et tu "
    "l'entends. Clic droit sur un bouton = y mettre le micro écouté (A).":
        "Your most important mics on keys 1 to 9 of the NUMERIC KEYPAD: one press = the SDR tunes to it\nand you hear "
        "it. Right-click on a button = put the listened mic (A) there.",
    "Touche {} du pavé numérique : libre (clic droit = y mettre le micro écouté)":
        "Numeric keypad key {}: free (right-click = put the listened mic there)",
    "Touche {} du pavé numérique : {}": "Numeric keypad key {}: {}",
    "Vider la touche {}": "Clear key {}",
    "⭐ Mettre ici : {}": "⭐ Put here: {}",
    "⭐ Mettre ici le micro écouté (règle A sur un micro d'abord)": "⭐ Put the listened mic here (tune A to a mic first)",
    "⭐ Touche du pavé numérique": "⭐ Numeric keypad key",
    "⭐ Touche {} du pavé numérique : {}": "⭐ Numeric keypad key {}: {}",
    "⭐ Touche {} libre : clic droit sur un micro (📡 Mes micros) ou sur le bouton {} du Récepteur pour l'y mettre.":
        "⭐ Key {} is free: right-click a mic (📡 My mics) or button {} of the Receiver to put it there.",
    "🎧 {} ({} MHz) sur {}": "🎧 {} ({} MHz) on {}",
    "🎧 Écouter (A)": "🎧 Listen (A)",
    "🎧 Écouter en B": "🎧 Listen in B",
})
SAME_TEMPLATES += ["{} ({} MHz)"]

# ---------------------------------------------------------------- V8 étape 19 : réglage d'écoute déduit du micro
EXACT.update({
    "auto (d'après le micro)": "auto (from the mic)",
    "« auto » : réglage déduit du micro (son appareil dans le plan importé, son groupe, son nom).\nChange-le ici : il est "
    "retenu pour CE micro (liste et shows).": "“auto”: setting deduced from the mic (its device in the imported plan, its "
                                             "group, its name).\nChange it here: it is remembered for THIS mic (list and "
                                             "shows).",
    "✋ choisi pour ce micro": "✋ chosen for this mic",
    "📵 {} : système numérique, il ne s'écoute pas (son chiffré). Le niveau et la santé RF restent surveillés.":
        "📵 {}: digital system, it can't be listened to (encrypted audio). Its level and RF health are still monitored.",
})

# ---------------------------------------------------------------- V8 étape 20 : patrouille, alarme, pilote, c'est quoi
EXACT.update({
    "(son non enregistré : accord pas encore donné)": "(sound not recorded: consent not given yet)",
    "Alarme si la porteuse n'a pas son pilote": "Alarm if the carrier has no pilot",
    "C'est quoi sur A (d'après la forme du spectre : une supposition, pas une certitude) et ce que\ndit le PILOTE : la "
    "tonalité inaudible de ton émetteur, retenue la 1re fois qu'on l'entend.\nPorteuse sans son pilote = ce n'est "
    "peut-être pas ton émetteur. Clic droit = oublier le pilote.":
        "What is on A (from the shape of the spectrum: a guess, not a certainty) and what the PILOT\nsays: the inaudible "
        "tone of your transmitter, remembered the 1st time it is heard.\nCarrier without its pilot = maybe not your "
        "transmitter. Right-click = forget the pilot.",
    "Enregistre le son de l'alarme : 10 s avant (si le SDR écoutait déjà ce micro) et 20 s\naprès, en WAV. Demande ton "
    "accord la 1re fois (voix).": "Records the sound of the alarm: 10 s before (if the SDR was already on this mic) and "
                                  "20 s\nafter, as WAV. Asks for your consent the 1st time (voices).",
    "Le SDR entend une porteuse sur ce micro, mais pas la tonalité pilote de ton émetteur (retenue la 1re fois) : un "
    "autre émetteur est peut-être sur ta fréquence, ou ton pack a changé de réglage.":
        "The SDR hears a carrier on this mic, but not the pilot tone of your transmitter (remembered the 1st time): "
        "another transmitter may be on your frequency, or your pack's settings changed.",
    "Écoute (le SDR y est calé) ; éteins ton pack : si la porteuse reste, c'est un brouilleur (chasse, fréquence de "
    "secours). Pilote changé exprès : clic droit sur la ligne d'info du Récepteur › Oublier le pilote.":
        "Listen (the SDR is tuned to it); switch your pack off: if the carrier stays, it's an interferer (hunt, backup "
        "frequency). Pilot changed on purpose: right-click the Receiver info line › Forget the pilot.",
    "Le SDR passe tout seul d'un micro à l'autre (tes favoris ⭐, sinon tous), avec la bonne\nécoute pour chacun. Une "
    "touche du pavé numérique ou un clic sur une fréquence l'arrête.":
        "The SDR goes from one mic to the next by itself (your ⭐ favourites, otherwise all), with the right\nlistening "
        "setting for each. A numeric keypad key or a click on a frequency stops it.",
    "Mes favoris ⭐ (pavé numérique)": "My ⭐ favourites (numeric keypad)",
    "Oublier le pilote (aucun retenu pour ce micro)": "Forget the pilot (none remembered for this mic)",
    "Oublier le pilote de {}": "Forget the pilot of {}",
    "PILOTE": "PILOT",
    "Quels micros la patrouille parcourt (les éteints 💤 et ceux en pause sont sautés).":
        "Which mics the patrol goes through (💤 switched-off and paused ones are skipped).",
    "Revenir où tu étais avant l'alarme (fréquence, écoute, patrouille).":
        "Go back to where you were before the alarm (frequency, listening, patrol).",
    "SDR (étape 20)": "SDR (step 20)",
    "SDR : ": "SDR: ",
    "SDR SUR ALARME": "SDR ON ALARM",
    "Temps passé sur chaque micro pendant la patrouille.": "Time spent on each mic during the patrol.",
    "Tous les micros de ce SDR": "All the mics of this SDR",
    "Une nouvelle alarme (conflit, intermod, absent, trop fort, pilote) sur un micro de ce SDR :\nle SDR s'y cale tout "
    "seul, tu entends ce qui se passe, et le journal dit ce que c'est.":
        "A new alarm (conflict, intermod, absent, too strong, pilot) on a mic of this SDR:\nthe SDR tunes to it by "
        "itself, you hear what's going on, and the log says what it is.",
    "pas de pilote vu (normal pour certains micros)": "no pilot seen (normal for some mics)",
    "pas de porteuse : pilote non jugé": "no carrier: pilot not judged",
    "pilote attendu ({} kHz)…": "pilot expected ({} kHz)…",
    "pilote {} kHz vu (il sera retenu pour ce micro)": "pilot {} kHz seen (it will be remembered for this mic)",
    "{} s par micro": "{} s per mic",
    "↩ Reprendre la patrouille": "↩ Resume the patrol",
    "↩ Revenir": "↩ Go back",
    "Revenir": "Go back",
    "↩ Revenir à {}": "↩ Back to {}",
    "⏺ Son enregistré ({} s avant, {} s après).": "⏺ Sound recorded ({} s before, {} s after).",
    "⏺ et enregistrer le son": "⏺ and record the sound",
    "⚠ pilote {} kHz au lieu de {} kHz : un autre émetteur ?": "⚠ pilot {} kHz instead of {} kHz: another transmitter?",
    "⚠ porteuse SANS son pilote : ce n'est peut-être pas ton émetteur (brouilleur ?)":
        "⚠ carrier WITHOUT its pilot: maybe not your transmitter (interferer?)",
    "✔ pilote {} kHz : c'est bien ton émetteur": "✔ pilot {} kHz: it really is your transmitter",
    "🏷 Rien de net sur A": "🏷 Nothing clear on A",
    "🔁 Patrouille": "🔁 Patrol",
    "Patrouille": "Patrol",
    "🔁 Patrouille arrêtée.": "🔁 Patrol stopped.",
    "🔁 Patrouille arrêtée : tu as choisi une fréquence.": "🔁 Patrol stopped: you chose a frequency.",
    "🔁 Rien à parcourir : mets des micros en favoris ⭐ (clic droit sur 1…9) ou choisis « Tous les micros ».":
        "🔁 Nothing to go through: put mics in ⭐ favourites (right-click 1…9) or choose “All the mics”.",
    "🔁 {} / {} · {} · encore {} s": "🔁 {} / {} · {} · {} s left",
    "🔊 Pilote de {} retenu : {} kHz (il sert à reconnaître TON émetteur).":
        "🔊 Pilot of {} remembered: {} kHz (used to recognise YOUR transmitter).",
    "🚨 Se caler sur les alarmes": "🚨 Tune to alarms",
    "🚨 {} sur {} : le SDR s'y est calé.": "🚨 {} on {}: the SDR tuned to it.",
    "⏺ Son de l'alarme enregistré : {}": "⏺ Alarm sound recorded: {}",
    "{} · {} : {}": "{} · {}: {}",
})

# ---------------------------------------------------------------- V8 étape 21 : SDR démo + émission HackRF
EXACT.update({
    " Pas de SDR sous la main ? Essaie 🧪 SDR démo (menu du mode).": " No SDR at hand? Try 🧪 SDR demo (mode menu).",
    " · ampli": " · amp",
    "Ajoute au moins un signal.": "Add at least one signal.",
    "Ajoute les micros choisis dans « Mes fréquences » (ou les 3 premiers).":
        "Adds the mics selected in “My frequencies” (or the first 3).",
    "Allumé 1 s toutes les 4 s : un brouilleur qui va et vient (chasse, alarmes).":
        "On 1 s every 4 s: an interferer that comes and goes (hunt, alarms).",
    "Ampli (+ ~11 dB)": "Amp (+ ~11 dB)",
    "Ampli de sortie du HackRF. Inutile en câble : laisse-le coupé.": "HackRF output amp. Useless on a cable: leave it off.",
    "Bips": "Beeps",
    "Bloc large (numérique, TNT)": "Wide block (digital, DTT)",
    "Ce que le HackRF émet en même temps (8 au plus, tous dans une même fenêtre de quelques MHz).":
        "What the HackRF transmits at the same time (8 at most, all in one window of a few MHz).",
    "Centre {} MHz · débit {} MS/s · {} signal(aux)": "Centre {} MHz · rate {} MS/s · {} signal(s)",
    "Coche d'abord « en câble avec un atténuateur ».": "First tick “on a cable with an attenuator”.",
    "Depuis ma liste": "From my list",
    "FIN D'ÉMISSION SDR": "SDR TRANSMISSION END",
    "Ferme la fenêtre (l'émission s'arrête).": "Closes the window (transmission stops).",
    "Gain :": "Gain:",
    "Gain d'émission du HackRF (0 à 47 dB). Commence à 0 : en câble, c'est déjà bien assez.":
        "HackRF transmit gain (0 to 47 dB). Start at 0: on a cable, that's already plenty.",
    "Intermittent": "Intermittent",
    "Je suis EN CÂBLE avec un atténuateur, aucune antenne branchée": "I am ON A CABLE with an attenuator, no antenna connected",
    "L'émission s'arrête toute seule au bout de ce temps.": "Transmission stops by itself after this time.",
    "Lance / arrête l'émission.": "Starts / stops the transmission.",
    "Micro FM (large)": "FM mic (wide)",
    "Mélodie": "Melody",
    "Niveau par rapport au signal le plus fort (0 dB).": "Level relative to the strongest signal (0 dB).",
    "Numérique": "Digital",
    "Pilote": "Pilot",
    "Retire les lignes choisies.": "Removes the selected rows.",
    "Réserve": "Reserve",
    "SDR démo": "SDR demo",
    "SDR démo coupé : le poste SDR reprendra ton vrai SDR au prochain ▶.":
        "SDR demo off: the SDR station will use your real SDR on the next ▶.",
    "MHz": "MHz",
    "Type": "Type",
    "Son": "Sound",
    "Niveau": "Level",
    "Durée :": "Duration:",
    "Fermer": "Close",
    "Ajoute au moins un signal": "Add at least one signal",
    "Émission SDR": "SDR transmission",
    "ÉMISSION SDR": "SDR TRANSMISSION",
    "arrêtée": "stopped",
    "en câble": "on a cable",
    "simulée (SDR démo)": "simulated (SDR demo)",
    "{} min": "{} min",
    "{} · gain {} dB{} · {}": "{} · gain {} dB{} · {}",
    "⚠ Émission arrêtée : {}": "⚠ Transmission stopped: {}",
    "⚠ Impossible de lancer hackrf_transfer : {}": "⚠ Can't start hackrf_transfer: {}",
    "hackrf_transfer introuvable (outils HackRF : PothosSDR, ou 📡 Réglages SDR).":
        "hackrf_transfer not found (HackRF tools: PothosSDR, or 📡 SDR settings).",
    "Un poste SDR utilise le HackRF : arrête-le d'abord (un HackRF reçoit OU émet).":
        "An SDR station is using the HackRF: stop it first (a HackRF receives OR transmits).",
    "📡 Émission en cours · {} min {:02d} s restantes": "📡 Transmitting · {} min {:02d} s left",
    "■ Arrêter l'émission": "■ Stop transmitting",
    "📡 Émettre": "📡 Transmit",
    "Émettre": "Transmit",
    "📡 Émettre avec un HackRF (en câble)": "📡 Transmit with a HackRF (on a cable)",
    "📡 Émettre avec un HackRF (en câble)…": "📡 Transmit with a HackRF (on a cable)…",
    "＋ Ajouter un signal": "＋ Add a signal",
    "Ajouter un signal": "Add a signal",
    "Retirer": "Remove",
    "Un faux micro FM de plus (change le type, le son…).": "One more fake FM mic (change the type, the sound…).",
    "Tonalité pilote inaudible (32,768 kHz) comme beaucoup de micros analogiques.":
        "Inaudible pilot tone (32.768 kHz) like many analog mics.",
    "Obligatoire pour émettre.": "Required to transmit.",
    "Lance / arrête l'émission": "Starts / stops the transmission",
    "Porteuse pure": "Pure carrier",
    "Talkie (FM étroite)": "Walkie-talkie (narrow FM)",
    "Voix « un, deux »": "Voice “one, two”",
    "Tonalité 1 kHz": "1 kHz tone",
    "⚠ Émettre à l'antenne sans autorisation est interdit. En CÂBLE seulement, avec un atténuateur (30 dB ou plus) avant "
    "l'entrée du récepteur ou du tinySA.": "⚠ Transmitting over the air without authorisation is forbidden. ON A CABLE "
                                          "only, with an attenuator (30 dB or more) before the receiver's or tinySA's "
                                          "input.",
    "🧪 SDR démo allumé : émission SIMULÉE, rien ne sort. Le SDR démo la « reçoit » : regarde le spectre et écoute.":
        "🧪 SDR demo on: SIMULATED transmission, nothing goes out. The SDR demo “receives” it: watch the spectrum and "
        "listen.",
    "🧪 SDR démo (sans matériel)": "🧪 SDR demo (no hardware)",
    "🧪 SDR démo (sans matériel, avec du son)": "🧪 SDR demo (no hardware, with sound)",
    "🧪 SDR démo (allumer / éteindre)": "🧪 SDR demo (on / off)",
    "🧪 SDR démo : tes micros sont « reçus » avec du son et un pilote ; un brouilleur passe de temps en temps, un micro "
    "s'éteint, un autre perd son pilote.": "🧪 SDR demo: your mics are “received” with sound and a pilot; an interferer "
                                           "passes now and then, a mic switches off, another loses its pilot.",
    "Signaux fabriqués par l'appli à partir de tes micros (son, pilote, brouilleur qui passe, micro qui s'éteint) : pour "
    "découvrir le poste SDR sans matériel.": "Signals made by the app from your mics (sound, pilot, passing interferer, mic "
                                            "switching off): to discover the SDR station without hardware.",
    "SDR démo (sans matériel)": "SDR demo (no hardware)",
    "SDR démo (sans matériel, avec du son)": "SDR demo (no hardware, with sound)",
})
TEMPLATES.update({
    "Signaux trop écartés ({} MHz) : {} MHz au plus en une fois.": "Signals too far apart ({} MHz): {} MHz at most at once.",
    "{} signaux au plus.": "{} signals at most.",
    "Fréquences entre {} et {} MHz.": "Frequencies between {} and {} MHz.",
})
SAME_TEMPLATES += ["HF {}"]
EXACT.update({
    "V8 : pas de SDR ? L'appli fabrique les signaux de tes micros (son, pilote, brouilleur qui passe,\nmicro qui s'éteint) : "
    "tout le poste SDR marche, écoute comprise.": "V8: no SDR? The app makes the signals of your mics (sound, pilot, passing "
                                                 "interferer,\nmic switching off): the whole SDR station works, listening "
                                                 "included.",
    "V8 : faux micros FM, porteuses, brouilleur intermittent émis par un HackRF, EN CÂBLE\navec un atténuateur (tester un "
    "récepteur, l'intermod, s'entraîner à la chasse).": "V8: fake FM mics, carriers, intermittent interferer transmitted "
                                                         "by a HackRF, ON A CABLE\nwith an attenuator (test a receiver, "
                                                         "intermod, practise hunting).",
})
EXACT.update({"📡 Émettre avec un HackRF": "📡 Transmit with a HackRF", "🧪 SDR démo": "🧪 SDR demo"})

# ---------------------------------------------------------------- V8 étape 21 : sources sonores / générateur audio
EXACT.update({
    "(aucun fichier)": "(no file)",
    "Alarme critique": "Critical alarm",
    "Alarme info": "Info alarm",
    "Alarme normale": "Normal alarm",
    "Appel des micros ✓": "Mic roll call ✓",
    "Balayage {} → {} Hz en {} s ({})": "Sweep {} → {} Hz in {} s ({})",
    "Bruit blanc": "White noise",
    "Bruit rose": "Pink noise",
    "Coché : chaque octave dure le même temps (comme à l'oreille). Décoché : linéaire en Hz.":
        "Ticked: each octave lasts the same time (like the ear). Unticked: linear in Hz.",
    "D'où vient le son.": "Where the sound comes from.",
    "Dans l'écoute d'un micro HF (FM), les aigus au-delà de ~15 kHz sont coupés : c'est la bande audio d'un micro, pas "
    "un défaut.": "When listening to a wireless mic (FM), highs above ~15 kHz are cut: that's a mic's audio band, not a "
                  "fault.",
    "Durée d'un balayage (il recommence ensuite).": "Duration of one sweep (then it starts again).",
    "Fichier :": "File:",
    "Fichier WAV": "WAV file",
    "Fréquence d'arrivée du balayage.": "End frequency of the sweep.",
    "Fréquence de départ du balayage.": "Start frequency of the sweep.",
    "Fréquence du son (20 Hz – 20 kHz).": "Frequency of the sound (20 Hz – 20 kHz).",
    "Générateur : balayage (sweep)": "Generator: sweep",
    "Générateur : une fréquence (20 Hz – 20 kHz)": "Generator: one frequency (20 Hz – 20 kHz)",
    "Joue le son sur la sortie audio de l'appli (⚙ Réglages › Son).": "Plays the sound on the app's audio output (⚙ Settings › Sound).",
    "Le son qui module ce signal : générateur, balayage, bruit, sons de l'appli, ton WAV…":
        "The sound modulating this signal: generator, sweep, noise, app sounds, your WAV…",
    "Les sons que joue l'appli (alarmes, appel des micros), répétés.": "The sounds the app plays (alarms, mic roll call), repeated.",
    "Logarithmique (autant de temps par octave)": "Logarithmic (same time per octave)",
    "Mon fichier WAV": "My WAV file",
    "Silence (porteuse seule)": "Silence (carrier only)",
    "Son :": "Sound:",
    "Source :": "Source:",
    "Ton fichier WAV (voix, musique, signal de test), joué en boucle.": "Your WAV file (voice, music, test signal), looped.",
    "Tonalité {} Hz": "Tone {} Hz",
    "Un son de l'appli": "An app sound",
    "Fréquence :": "Frequency:",
    "De :": "From:",
    "À :": "To:",
    "Volume :": "Volume:",
    "Volume (commence bas : un générateur peut être fort).": "Volume (start low: a generator can be loud).",
    "▶ Écouter ici": "▶ Listen here",
    "Écouter ici": "Listen here",
    "📂 Choisir un WAV…": "📂 Choose a WAV…",
    "Choisir un WAV…": "Choose a WAV…",
    "🎵 Choisir un son": "🎵 Choose a sound",
    "🎵 Générateur audio (20 Hz – 20 kHz)": "🎵 Audio generator (20 Hz – 20 kHz)",
    "🎵 Générateur audio (20 Hz – 20 kHz)…": "🎵 Audio generator (20 Hz – 20 kHz)…",
    "🎵 Générateur audio": "🎵 Audio generator",
    "🎵 Son de {} dans le SDR démo": "🎵 Sound of {} in the SDR demo",
    "🎵 Son de ce micro dans le SDR démo…": "🎵 Sound of this mic in the SDR demo…",
    "V8 : une fréquence de 20 Hz à 20 kHz, un balayage, du bruit, les sons de l'appli ou ton\nWAV, joués sur la sortie "
    "audio de l'appli (et utilisables pour l'émission / le SDR démo).": "V8: a frequency from 20 Hz to 20 kHz, a sweep, "
                                                                        "noise, the app's sounds or your\nWAV, played on "
                                                                        "the app's audio output (and usable for "
                                                                        "transmission / the SDR demo).",
    "WAV : {}": "WAV: {}",
    "WAV illisible : {}": "Unreadable WAV: {}",
    "WAV : format non pris en charge": "WAV: format not supported",
    "WAV vide": "Empty WAV",
    "{} s de son": "{} s of sound",
    "▶ {} (en boucle)": "▶ {} (looped)",
    "⚠ Son impossible ici : {}": "⚠ Sound impossible here: {}",
    "log": "log",
    "linéaire": "linear",
    "Son WAV (*.wav);;Tous (*)": "WAV sound (*.wav);;All (*)",
})
SAME_TEMPLATES += ["tsm_gen_{}.wav"]
EXACT["color: #8e8e93;"] = "color: #8e8e93;"
EXACT.update({
    "(générateur, sons, ton WAV…)": "(generator, sounds, your WAV…)",
    "Le son joué pour : {}. Clic = choisir (générateur, bruit, autre son, ton WAV…).":
        "The sound played for: {}. Click = choose (generator, noise, another sound, your WAV…).",
    "Revenir au son d'origine.": "Back to the original sound.",
    "Réglages (sons des alarmes)": "Settings (alarm sounds)",
    "Sons des alarmes": "Alarm sounds",
    "Écouter ce son.": "Listen to this sound.",
    "🎵 Son : {}": "🎵 Sound: {}",
    "🎵 Son d'origine": "🎵 Original sound",
    "🎵 {}": "🎵 {}",
    "{} :": "{}:",
})

# ---------------------------------------------------------------- V8 étape 22 : premier branchement, calibration, ⏪
EXACT.update({
    " · ⚠ écarts importants : antennes à des endroits différents ?": " · ⚠ large differences: antennas in different places?",
    ".wav / .png": ".wav / .png",
    "1. Mon SDR": "1. My SDR", "2. Le trouver": "2. Find it", "3. Régler le gain tout seul": "3. Set the gain automatically",
    "4. Écouter un micro": "4. Listen to a mic", "5. Caler les niveaux (facultatif)": "5. Calibrate the levels (optional)",
    "6. Diagnostic": "6. Diagnostics",
    "Branche ton SDR, puis fais les étapes dans l'ordre. Si une étape bloque, le 🩺 diagnostic en bas résume tout pour le "
    "support.": "Plug in your SDR, then do the steps in order. If a step gets stuck, the 🩺 diagnostics at the bottom sums "
                "everything up for support.",
    "Choisis d'abord un instant (clic sur le waterfall).": "First pick a moment (click on the waterfall).",
    "Clique sur le waterfall pour choisir un instant.": "Click on the waterfall to pick a moment.",
    "Combien de temps le poste SDR garde en mémoire (son : ~11 Mo par minute).":
        "How long the SDR station keeps in memory (sound: ~11 MB per minute).",
    "Compare les mêmes signaux vus par le tinySA et le SDR : niveaux du SDR en vrais dBm.":
        "Compares the same signals seen by the tinySA and the SDR: SDR levels in real dBm.",
    "Correction de niveau": "Level correction",
    "Correction mesurée : {} dB (± {} dB sur {} signaux) · actuelle : {} dB":
        "Measured correction: {} dB (± {} dB over {} signals) · current: {} dB",
    "Couper le SDR démo": "Turn the SDR demo off",
    "Dossier des outils": "Tools folder",
    "ENREGISTRÉ (SDR)": "RECORDED (SDR)",
    "Enregistre le son (WAV, 60 s) et l'image du waterfall. Demande ton accord la 1re fois.":
        "Saves the sound (WAV, 60 s) and the waterfall image. Asks for your consent the 1st time.",
    "Essaie chaque gain et garde le plus fort qui ne sature pas.": "Tries each gain and keeps the highest that doesn't saturate.",
    "Ferme l'assistant (ce qui est réglé reste réglé).": "Closes the wizard (what's set stays set).",
    "Ferme la fenêtre (la mémoire continue de se remplir).": "Closes the window (the memory keeps filling).",
    "Gains": "Gains",
    "Garde cette correction pour ce modèle de SDR (📡 Réglages SDR › correction de niveau).":
        "Keeps this correction for this SDR model (📡 SDR settings › level correction).",
    "Il y a {} min {:02d} s · A = {}": "{} min {:02d} s ago · A = {}",
    "Lance d'abord la surveillance du tinySA (▶ Démarrer).": "First start the tinySA monitoring (▶ Start).",
    "Lance d'abord le poste SDR (▶ du Récepteur), en mode combiné avec le tinySA.":
        "First start the SDR station (▶ of the Receiver), in combined mode with the tinySA.",
    "Lance la comparaison.": "Starts the comparison.",
    "Lance le poste SDR sur un de tes micros : tu dois l'entendre.": "Starts the SDR station on one of your mics: you should hear it.",
    "Le SDR démo est allumé : coupe-le pour régler ton vrai SDR.": "The SDR demo is on: turn it off to set up your real SDR.",
    "Le SDR démo n'a rien à caler : ses niveaux sont fabriqués. Coupe-le pour caler ton vrai SDR.":
        "The SDR demo has nothing to calibrate: its levels are made up. Turn it off to calibrate your real SDR.",
    "Le modèle exact de ton SDR (règle ses débits, gains et plage).": "The exact model of your SDR (sets its rates, gains and range).",
    "Le plus récent en haut. Clic = choisir cet instant.": "Most recent at the top. Click = pick this moment.",
    "Le tinySA mesure en dBm, le SDR en dBFS (relatif à son convertisseur). Avec les DEUX en marche (mode combiné) et des "
    "signaux dans la fenêtre du SDR (tes micros allumés), l'appli compare les mêmes signaux pendant 15 s et en déduit la "
    "correction du SDR. Mets les deux antennes au même endroit.":
        "The tinySA measures in dBm, the SDR in dBFS (relative to its converter). With BOTH running (combined mode) and "
        "signals in the SDR window (your mics on), the app compares the same signals for 15 s and deduces the SDR's "
        "correction. Put both antennas in the same place.",
    "Les signaux vus par les deux (puissance sur ± 100 kHz).": "The signals seen by both (power over ± 100 kHz).",
    "Manuel SDR introuvable.": "SDR manual not found.",
    "Mesure… {} s": "Measuring… {} s",
    "Outil trouvé, SDR détecté, signal reçu, débit tenu.": "Tool found, SDR detected, signal received, rate kept up.",
    "Pas assez de signaux vus par les deux (il en faut {}) : allume des micros dans la fenêtre du SDR, ou rapproche les "
    "antennes.": "Not enough signals seen by both ({} needed): switch on mics in the SDR window, or bring the antennas "
                 "closer.",
    "Pas de son gardé à cet instant (poste arrêté, ou trop ancien).": "No sound kept at this moment (station stopped, or too old).",
    "Recharge les dernières secondes.": "Reloads the latest seconds.",
    "Rejoue ce que le poste SDR faisait entendre à cet instant (60 s au plus).":
        "Replays what the SDR station was playing at that moment (60 s at most).",
    "Rien en mémoire : lance le poste SDR (▶ du Récepteur), puis reviens ici.":
        "Nothing in memory: start the SDR station (▶ of the Receiver), then come back here.",
    "Rien à comparer : le tinySA balaye-t-il la fenêtre du SDR ?": "Nothing to compare: does the tinySA sweep the SDR window?",
    "Réglage du gain": "Gain setting",
    "Test du SDR": "SDR test",
    "aucun essai": "no test",
    "aucun micro dans la plage du SDR : règle A à la main (fréquence du Récepteur)":
        "no mic in the SDR range: set A by hand (Receiver frequency)",
    "aucune donnée reçue": "no data received",
    "ce SDR n'a pas de gain réglable ici : règle-le dans 📡 Réglages SDR": "this SDR has no adjustable gain here: set it in 📡 SDR settings",
    "en marche": "running",
    "essai des gains…": "trying the gains…",
    "essai impossible : {}": "test impossible: {}",
    "gain auto {} : {} dB ({})": "auto gain {}: {} dB ({})",
    "gain maximal sans saturer": "maximum gain without saturating",
    "le plus haut sans saturer ({} dB de marge)": "the highest without saturating ({} dB of headroom)",
    "niveaux calés sur le tinySA : {} dB ({})": "levels calibrated on the tinySA: {} dB ({})",
    "passage gardé : {}": "passage kept: {}",
    "poste SDR lancé sur {} : tu dois l'entendre (🔊 volume du Récepteur)":
        "SDR station started on {}: you should hear it (🔊 Receiver volume)",
    "premier branchement SDR": "first SDR connection",
    "recherche…": "searching…",
    "rien reçu": "nothing received",
    "rien": "nothing",
    "sature même au plus bas : éloigne l'antenne ou ajoute un atténuateur":
        "saturates even at the lowest: move the antenna away or add an attenuator",
    "signal très fort : peu de marge, même au plus bas (atténuateur conseillé)":
        "very strong signal: little headroom, even at the lowest (attenuator advised)",
    "tinySA (dBm)": "tinySA (dBm)",
    "SDR (dBFS)": "SDR (dBFS)",
    "{} : {} – {} MHz, fenêtre jusqu'à {} MHz": "{}: {} – {} MHz, window up to {} MHz",
    "{} Mo en mémoire": "{} MB in memory",
    "{} min gardées": "{} min kept",
    "Écart (dB)": "Difference (dB)",
    "Écrit un fichier qui résume tout (à m'envoyer si ça coince).": "Writes a file that sums everything up (send it to me if it gets stuck).",
    "↻ Mettre à jour": "↻ Refresh", "Mettre à jour": "Refresh",
    "⏪ Remonter le temps · {}": "⏪ Go back in time · {}",
    "▶ Mesurer (15 s)": "▶ Measure (15 s)", "Mesurer (15 s)": "Measure (15 s)",
    "▶ Réécouter à partir d'ici": "▶ Replay from here", "Réécouter à partir d'ici": "Replay from here",
    "✔ Appliquer la correction": "✔ Apply the correction", "Appliquer la correction": "Apply the correction",
    "✔ Correction gardée pour {} : {} dB.": "✔ Correction kept for {}: {} dB.",
    "✔ Gardé : {}": "✔ Kept: {}",
    "🎚 Régler le gain": "🎚 Set the gain", "Régler le gain": "Set the gain",
    "🎧 Écouter": "🎧 Listen",
    "💾 Garder ce passage": "💾 Keep this passage", "Garder ce passage": "Keep this passage",
    "📏 Caler les niveaux du SDR sur le tinySA": "📏 Calibrate the SDR levels on the tinySA",
    "📏 Caler les niveaux du SDR sur le tinySA…": "📏 Calibrate the SDR levels on the tinySA…",
    "📏 Caler sur le tinySA": "📏 Calibrate on the tinySA", "Caler sur le tinySA": "Calibrate on the tinySA",
    "🔌 Chercher mon SDR": "🔌 Look for my SDR", "Chercher mon SDR": "Look for my SDR",
    "🔌 Premier branchement SDR": "🔌 First SDR connection",
    "🔌 Premier branchement SDR (assistant)…": "🔌 First SDR connection (wizard)…",
    "🧪 Le SDR démo est allumé : l'assistant règle ton VRAI SDR, coupe la démo d'abord.":
        "🧪 The SDR demo is on: the wizard sets up your REAL SDR, turn the demo off first.",
    "🩺 Diagnostic à envoyer": "🩺 Diagnostics to send", "Diagnostic à envoyer": "Diagnostics to send",
    "⏪ Remonter le temps": "⏪ Go back in time", "Remonter le temps": "Go back in time",
    "⏪ Remonter le temps (dernières minutes)…": "⏪ Go back in time (last minutes)…",
    "📖 Manuel SDR": "📖 SDR manual",
    "Les dernières minutes de ce poste : waterfall, réécouter un passage, le garder.":
        "The last minutes of this station: waterfall, replay a passage, keep it.",
    "il y a (s)": "ago (s)",
    "Modèle": "Model", "Poste": "Station", "arrêté": "stopped", "saturation": "saturation", "bruit": "noise",
    "crête": "peak",
    "V8 : choisir son SDR, le trouver, régler le gain tout seul, écouter un micro,\ncaler les niveaux, et un diagnostic à "
    "envoyer si ça coince.": "V8: choose your SDR, find it, set the gain automatically, listen to a mic,\ncalibrate the "
                             "levels, and diagnostics to send if it gets stuck.",
    "V8 : compare les mêmes signaux vus par le tinySA et le SDR : niveaux du SDR en vrais dBm.":
        "V8: compares the same signals seen by the tinySA and the SDR: SDR levels in real dBm.",
    "V8 : les dernières minutes du poste SDR (waterfall + son) : réécouter un passage, le garder.":
        "V8: the last minutes of the SDR station (waterfall + sound): replay a passage, keep it.",
    "V8 : le manuel du poste SDR (écoute, surveillance, démo, émission, calibration…).":
        "V8: the SDR station manual (listening, monitoring, demo, transmission, calibration…).",
})
SAME_TEMPLATES += ["TinySA Monitor {} — {} — {}", "  gain {} : {} {} %, {} {} dBFS, {} {} dBFS", "{} : {} dB",
                   "tsm_rewind_{}.wav", "diagnostic_sdr_{}.txt", "  err : {}", "{} : {}", "{} {}", "{}:{}%"]
EXACT.update({"peu de marge": "little headroom", "{} = {} dB : {}": "{} = {} dB: {}",
              "📏 Caler les niveaux du SDR": "📏 Calibrate the SDR levels"})
EXACT[" · ⚠ pas du tinySA ({} kHz) plus grand que sa RBW ({} kHz) : mesure moins sûre (zoome ou affine le pas)"] = \
    " · ⚠ tinySA step ({} kHz) larger than its RBW ({} kHz): less reliable measurement (zoom in or use a finer step)"

# ---------------------------------------------------------------- V8 : points de l'audit vus avec Clément
EXACT.update({
    "Ce n'est pas ton émetteur (brouilleur ?) : ce pilote n'est pas retenu.":
        "It's not your transmitter (interferer?): this pilot isn't remembered.",
    "Ce pilote sert ensuite à reconnaître ton émetteur (alarme PILOTE s'il manque).":
        "This pilot is then used to recognise your transmitter (PILOT alarm if it's missing).",
    "Combien de temps CHAQUE poste SDR garde en mémoire (son : ~11 Mo par minute et par poste ;\n5 min avec 4 postes ≈ "
    "230 Mo). « Désactivé » : rien n'est gardé.": "How long EACH SDR station keeps in memory (sound: ~11 MB per minute "
                                                  "and per station;\n5 min with 4 stations ≈ 230 MB). “Off”: nothing is "
                                                  "kept.",
    "Désactivé (rien gardé)": "Off (nothing kept)",
    "Désactivé : choisis une durée en haut à gauche.": "Off: choose a duration at the top left.",
    "L'alarme est hors de la fenêtre du SDR : y aller (les autres micros ne sont plus mesurés\npar le SDR pendant ce "
    "temps ; « ↩ Revenir » pour revenir).": "The alarm is outside the SDR window: go there (the other mics are no longer "
                                           "measured\nby the SDR meanwhile; “↩ Go back” to return).",
    "Le poste SDR est en marche : l'arrêter le temps du test ?\n(un SDR ne sert qu'à un logiciel à la fois)":
        "The SDR station is running: stop it for the test?\n(an SDR serves only one program at a time)",
    "Poste SDR en marche": "SDR station running",
    "✔ Oui, le retenir": "✔ Yes, remember it", "Oui, le retenir": "Yes, remember it",
    "✖ Non": "✖ No", "Non": "No",
    "🔊 Pilote {} kHz entendu sur {} : c'est bien ton émetteur ?": "🔊 Pilot {} kHz heard on {}: is it really your transmitter?",
    "🚨 Aller à l'alarme": "🚨 Go to the alarm", "Aller à l'alarme": "Go to the alarm",
    "🚨 {} sur {} : hors de la fenêtre du SDR.": "🚨 {} on {}: outside the SDR window.",
})

# ---------------------------------------------------------------- 8.0 : SDR en bêta
EXACT.update({"📡 SDR (bêta)": "📡 SDR (beta)", "📟+📡 Combiné (bêta)": "📟+📡 Combined (beta)",
              "📡 SDR (bêta : écoute et moniteur)": "📡 SDR (beta: listening and monitor)",
              "SDR (bêta)": "SDR (beta)", "Combiné (bêta)": "Combined (beta)"})

# ---------------------------------------------------------------- 8.0 : c'est quoi un tinySA, un SDR
EXACT.update({
    "📟 tinySA = un petit analyseur de spectre. Il BALAYE toute une bande (par exemple 470–694 MHz), fréquence après "
    "fréquence, et mesure la puissance de chacune en dBm. Parfait pour SURVEILLER tous tes micros d'un coup et voir ce "
    "qui occupe le site. Il ne fait pas entendre le son.":
        "📟 tinySA = a small spectrum analyser. It SWEEPS a whole band (for example 470–694 MHz), frequency after "
        "frequency, and measures the power of each in dBm. Perfect to MONITOR all your mics at once and see what "
        "occupies the site. It doesn't let you hear the sound.",
    "📡 SDR = une radio logicielle (HackRF, SDRplay, RTL-SDR…). Elle reçoit d'un coup une FENÊTRE de quelques MHz, sans "
    "trou, et peut DÉMODULER : tu ENTENDS le son d'un micro analogique. Elle voit moins large d'un coup que le balayage "
    "du tinySA, et ses niveaux sont en vrais dBm une fois calés sur un tinySA. (Fonctions SDR en bêta.)":
        "📡 SDR = a software-defined radio (HackRF, SDRplay, RTL-SDR…). It receives a WINDOW of a few MHz at once, "
        "without gaps, and can DEMODULATE: you HEAR the sound of an analog mic. It sees less wide at once than the "
        "tinySA's sweep, and its levels are in real dBm once calibrated on a tinySA. (SDR features in beta.)",
    "📟+📡 Les deux ensemble : le tinySA surveille tout le site, le SDR écoute et regarde de près un micro ou une zone.":
        "📟+📡 Both together: the tinySA monitors the whole site, the SDR listens and looks closely at a mic or an area.",
    "tinySA": "tinySA", "SDR": "SDR", "Démoduler": "Demodulate",
    "Un petit analyseur de spectre : il balaye toute une bande, fréquence après fréquence, et mesure la puissance de "
    "chacune en dBm. C'est l'appareil de base de l'appli pour SURVEILLER tous tes micros. Il ne fait pas entendre le son.":
        "A small spectrum analyser: it sweeps a whole band, frequency after frequency, and measures the power of each in "
        "dBm. It's the app's basic device to MONITOR all your mics. It doesn't let you hear the sound.",
    "Radio logicielle (HackRF, SDRplay, RTL-SDR…) : elle reçoit d'un coup une fenêtre de quelques MHz, sans trou, et "
    "peut démoduler : tu entends un micro analogique. Moins large d'un coup que le tinySA ; ses niveaux sont justes une "
    "fois calés sur un tinySA. (Bêta.)": "Software-defined radio (HackRF, SDRplay, RTL-SDR…): it receives a window of a "
                                         "few MHz at once, without gaps, and can demodulate: you hear an analog mic. "
                                         "Less wide at once than the tinySA; its levels are right once calibrated on a "
                                         "tinySA. (Beta.)",
    "Retrouver le son transporté par une onde radio (ce que fait un récepteur de micro). Le SDR sait le faire, le tinySA "
    "non. Les micros numériques ne se démodulent pas : leur son est codé, souvent chiffré.":
        "Recovering the sound carried by a radio wave (what a mic receiver does). The SDR can do it, the tinySA can't. "
        "Digital mics can't be demodulated: their sound is coded, often encrypted.",
    "Ce que tu utilises :": "What you use:",
    "Chaque mode a sa disposition de base et des pré-affichages ; ensuite tu bouges les panneaux comme tu veux (ta "
    "disposition est retenue).": "Each mode has its base layout and preset views; then you move the panels as you like "
                                 "(your layout is remembered).",
    "Ton SDR : 📡 Réglages SDR pour le changer.": "Your SDR: 📡 SDR settings to change it.",
    "Le spectre du SDR : la fenêtre de quelques MHz qu'il reçoit en entier, sans trou (ce n'est pas le balayage du "
    "tinySA, qui couvre toute la bande).": "The SDR spectrum: the window of a few MHz it receives in full, without gaps "
                                          "(it's not the tinySA's sweep, which covers the whole band).",
    "Clic = écouter (A) · clic droit = B · molette = zoom.": "Click = listen (A) · right-click = B · wheel = zoom.",
})
