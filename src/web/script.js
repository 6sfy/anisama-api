const API_BASE = (window.API_URL || "").replace(/\/$/, "") || "";

const I18N = {
  fr: {
    'nav.getting_started': 'Getting Started',
    'nav.architecture': 'Architecture',
    'nav.sources': 'Sources',
    'nav.cli': 'CLI',
    'nav.live_demo': 'Live Demo',
    'nav.support': 'Support',
    'nav.introduction': 'Introduction',
    'nav.quick_start': 'Quick Start',
    'nav.installation': 'Installation',
    'nav.project_structure': 'Project Structure',
    'nav.api_reference': 'API Reference',
    'nav.all_sources': 'All 7 Sources',
    'nav.commands': 'Commands',
    'nav.settings': 'Settings',
    'nav.web_terminal': 'Web Terminal',
    'nav.terminal_cmds': 'Terminal Commands',
    'nav.troubleshooting': 'Troubleshooting',
    'nav.changelog': 'Changelog',
    'sidebar.search_placeholder': 'Rechercher...',
    'sidebar.docs_api': 'Docs & API',
    'theme.dark': 'Mode Sombre',
    'theme.light': 'Mode Clair',
    'lang.en': 'EN',
    'lang.fr': 'FR',
    'hero.intro.desc': 'CLI Anime VOSTFR/VF. Cherche, stream et telecharge tes animes depuis <strong style="color:var(--color-accent)">7 sources françaises</strong> — depuis ton terminal, ou via l\'<strong style="color:var(--color-accent)">API centrale</strong>.',
    'card.6_sources': '7 Sources FR',
    'card.6_sources.desc': 'Anime-Sama, Voiranime, FRAnime, MyFluneo, AnimesUltra, French-Anime & AnimoFlix.',
    'card.smart_search': 'Recherche intelligente',
    'card.smart_search.desc': 'Fuzzy matching realiste (rapidfuzz), dedup par titre, 7 sources en cascade.',
    'card.api': 'API centralisee',
    'card.api.desc': 'Server-side scraping + resolution. Le client ne fait que consommer du JSON propre.',
    'card.stream': 'Stream & Download',
    'card.stream.desc': 'mpv, VLC, IINA, MoonPlayer, ImPlay ou telechargement direct.',
    'card.history': 'Historique & Continue',
    'card.history.desc': 'Reprends ton visionnage a l\'episode exact, cross-source.',
    'card.anilist': 'AniList Info',
    'card.anilist.desc': 'Scores, studios, synopsis, tags directement dans le TUI.',
    'hero.quick.title': 'Quick Start',
    'hero.quick.desc': 'Installe et lance-toi en 30 secondes.',
    'quick.code.comment1': '# Install avec pip',
    'quick.code.comment2': '# Lance le TUI interactif',
    'quick.code.comment3': '# Ou recherche directement',
    'quick.tui': 'Le TUI interactif se lance automatiquement. <kbd>↑</kbd><kbd>↓</kbd> pour naviguer, <kbd>Enter</kbd> pour confirmer, <kbd>Esc</kbd> pour revenir.',
    'hero.install.title': 'Installation',
    'hero.install.desc': 'PyPI ou source — au choix.',
    'install.pypi': 'Depuis PyPI',
    'install.source': 'Depuis les sources',
    'install.windows': '<strong>Windows :</strong> utilise <code>python -m src</code> depuis la racine du projet, ou installe avec <code>pip install -e .</code>',
    'install.api_server': 'API Server (optionnel)',
    'install.api_server.desc': 'Si tu veux heberger ta propre API centrale :',
    'install.api.comment': '# Le server demarre sur http://0.0.0.0:20100',
    'hero.arch.title': 'Project Structure',
    'hero.arch.desc': 'Codebase modulaire : CLI client + API server.',
    'arch.api_server': 'API Server',
    'arch.core.desc': 'src/core/<br> <span>cache.py</span> — catalogue & merge<br> <span>scraper.py</span> — Anime-Sama / Voiranime / 3 alt sources<br> <span>scraper_myfluneo.py</span> — MyFluneo (Playwright)<br> <span>resolver.py</span> — video URL extraction<br> <span>search.py</span> — fuzzy search',
    'arch.api_layer.desc': 'src/api/<br> <span>server.py</span> — HTTP handler<br> <span>routes/</span> — search, episodes, resolve, catalog, stats, info, player<br> <span>db/</span> — SQLite + background indexer<br> <span>utils/</span> — http helpers, text utils',
    'arch.web_docs.desc': 'src/web/<br> <span>index.html</span><br> <span>styles.css</span><br> <span>script.js</span>',
    'arch.cli_client': 'CLI Client',
    'arch.interface.desc': 'src/<br> <span>main.py</span> — TUI, menus, flows<br> <span>player.py</span> — mpv/vlc/iina detection<br> <span>api_client.py</span> — API consumer',
    'arch.config.desc': 'data/<br> <span>catalog.json</span><br> <span>settings.json</span><br> <span>history.json</span>',
    'hero.api.title': 'API Reference',
    'hero.api.desc': 'Tous les endpoints JSON de l\'API centrale.',
    'api.base_url': 'Base URL',
    'api.endpoints': 'Endpoints',
    'api.method': 'Method',
    'api.endpoint': 'Endpoint',
    'api.description': 'Description',
    'api.example_search': 'Example : Search',
    'api.example_search.comment': '# Retourne des resultats dedup avec scores realistes',
    'api.example_catalog': 'Example : Catalog',
    'api.rate_limits': 'Limites de débit',
    'api.rate_limits.desc': 'Fenêtre glissante par IP de 60 secondes, avec des budgets indépendants par classe d\'endpoint.',
    'api.rate_class': 'Classe',
    'api.rate_endpoints': 'Endpoints',
    'api.rate_limit': 'Limite',
    'api.rate_cache_note': 'Les cache hits d\'épisodes sont gratuits ; seuls les cache misses comptent dans le budget Episodes.',
    'api.rate_headers': 'Chaque réponse inclut <code>RateLimit-Limit</code>, <code>RateLimit-Remaining</code> et <code>RateLimit-Reset</code>. Un <code>429</code> envoie aussi <code>Retry-After</code>.',
    'api.rate_429_comment': '# HTTP 429 — trop de requêtes',
    'api.rate_config': 'Configurable via <code>ANISAMA_RATE_LIMIT_GLOBAL</code>, <code>ANISAMA_RATE_LIMIT_HEAVY</code>, <code>ANISAMA_RATE_LIMIT_EPISODES</code>, <code>ANISAMA_RATE_LIMIT_RESOLVE</code> et <code>ANISAMA_RATE_LIMIT_WINDOW</code> (<code>0</code> désactive un palier). Derrière Cloudflare, mettre <code>ANISAMA_TRUST_PROXY=1</code>.',
    'hero.sources.title': '7 Sources FR',
    'hero.sources.desc': 'Toutes les plateformes integrees dans l\'API et le CLI.',
    'sources.animesama.desc': 'Source principale. ~1500 entrees. Lecteurs embed : vidmoly, sendvid, sibnet, smoothpre, streamwish, oneupload.',
    'sources.animesama.tag': 'Principal',
    'sources.myfluneo.desc': '~5400 entrees. Next.js SPA. Playwright scraping. Hosts : vidmoly, streamtape.',
    'sources.myfluneo.tag': 'NEW',
    'sources.voiranime.desc': '~960 entrees. Resolution video interne.',
    'sources.voiranime.tag': 'Secondaire',
    'sources.franime.desc': 'API JSON publique. Fast engine, index 0-based, résolution watch2 directe.',
    'sources.franime.tag': 'API',
    'sources.animesultra.desc': '~2600 entrees via sitemap XML. Hosts : vidmoly, sendvid, sibnet, vidstream.',
    'sources.animesultra.tag': 'NEW',
    'sources.frenchanime.desc': 'Hosts : luluvdo, vidmoly, vidara. Scraped via page d\'accueil.',
    'sources.frenchanime.tag': 'NEW',
    'sources.animoflix.desc': 'Hosts : sendvid, sibnet. Playwright fallback pour episodes JS-rendered.',
    'sources.animoflix.tag': 'NEW',
    'hero.animesama.desc': 'Source principale VOSTFR/VF.',
    'animesama.p1': 'Anime-Sama est la source principale avec <strong>~1500 entrees</strong>. Le site utilise des lecteurs embed externes :',
    'animesama.li1': '<strong>vidmoly</strong> — lecteur video embed',
    'animesama.li2': '<strong>sendvid</strong> — lecteur MP4 direct',
    'animesama.li3': '<strong>sibnet</strong> — hebergeur video russe',
    'animesama.li4': '<strong>smoothpre</strong> — lecteur embed',
    'animesama.li5': '<strong>streamwish</strong> — hebergeur video',
    'animesama.li6': '<strong>oneupload</strong> — upload video',
    'animesama.p2': 'Le systeme de miroirs multiples permet un fallback automatique. Le speed-testing selectionne le miroir le plus rapide. Les saisons <code>Scan</code> / <code>Manhwa</code> / <code>Webtoon</code> sont automatiquement filtrees.',
    'hero.voiranime.desc': 'Source secondaire VOSTFR/VF.',
    'hero.franime.desc': 'API JSON publique en VOSTFR/VF.',
    'franime.p1': 'FRAnime (franime.fr) expose une API JSON publique (<code>api.franime.fr</code>). Le fast engine l\'interroge directement : pas de scraping HTML ni de Playwright.',
    'franime.li1': '<strong>Index d\'épisodes 0-based</strong> — corrige l\'ancien 404 <code>Aucun lecteur disponible</code> dû aux numéros 1-based.',
    'franime.li2': '<strong>Résolution watch2 directe</strong> — renvoie l\'URL embed utilisée par le player.',
    'franime.li3': '<strong>VOSTFR/VF</strong> — sélection de la langue via <code>&amp;lang=vo|vf</code>.',
    'voiranime.p1': 'Voiranime fournit un catalogue alternatif avec son propre systeme de resolution video. <strong>~960 entrees</strong> mergees dans le catalogue principal via <code>alt_source</code>.',
    'hero.myfluneo.desc': '~5400 entrees francaises.',
    'myfluneo.p1': 'MyFluneo (myfluneo.eu) est une <strong>nouvelle source</strong> francaise avec <strong>~5400 entrees</strong> VOSTFR/VF. Le site est construit avec Next.js :',
    'myfluneo.li1': '<strong>vidmoly.biz</strong> — lecteur MP4 embed',
    'myfluneo.li2': '<strong>streamtape.com</strong> — lecteur embed',
    'myfluneo.p2': 'Scrappe cote serveur avec <strong>Playwright</strong> (Next.js RSC). Les episodes et resolutions sont pre-cachables.',
    'hero.animesultra.desc': '~2600 entrees via sitemap XML.',
    'animesultra.p1': 'AnimesUltra (ww.animesultra.org) utilise un <strong>sitemap.xml</strong> pour exposer son catalogue complet (~2600 URLs).',
    'animesultra.li1': '<strong>vidmoly</strong>, <strong>sendvid</strong>, <strong>sibnet</strong>, <strong>vidstream.pro</strong>',
    'animesultra.p2': 'La resolution utilise l\'attribut <code>data-embed</code> sur les boutons serveur. Pas de JS dynamique requis pour le catalogue.',
    'hero.frenchanime.desc': 'Scraping par page d\'accueil.',
    'frenchanime.p1': 'French-Anime (french-anime.com) liste les animes recents sur sa page d\'accueil.',
    'frenchanime.li1': '<strong>luluvdo.com</strong> — hebergeur principal',
    'frenchanime.li2': '<strong>vidmoly.biz</strong>, <strong>vidara.to</strong>',
    'frenchanime.p2': 'La resolution passe par extraction d\'iframe depuis la page episode.',
    'hero.animoflix.desc': 'Site JS-heavy avec fallback Playwright.',
    'animoflix.p1': 'AnimoFlix (animoflix.to) est un site moderne avec rendu JavaScript :',
    'animoflix.li1': '<strong>sendvid</strong>, <strong>sibnet.ru</strong>',
    'animoflix.p2': 'Le catalogue est scrappe statiquement via <code>/catalogue/</code>. Les episodes utilisent un <strong>fallback Playwright</strong> si le HTML statique n\'est pas suffisant. Les onglets serveur sont simules par clic automatise.',
    'hero.cli.title': 'Commandes',
    'hero.cli.desc': 'Tous les flags disponibles.',
    'cli.flag': 'Flag',
    'cli.desc': 'Description',
    'cli.lang': 'Filtre langue',
    'cli.dub': 'Raccourci pour VF',
    'cli.download': 'Telecharger au lieu de streamer',
    'cli.episodes': 'Plage : <code>5</code>, <code>1-5</code>, <code>1,3,5</code>',
    'cli.player': 'mpv, vlc, iina, moonplayer, implay',
    'cli.update': 'Forcer le refresh du catalogue',
    'cli.settings': 'Menu des parametres',
    'cli.quiet': 'Reduce output verbosity',
    'cli.code.comment': '# Exemples',
    'hero.config.title': 'Parametres',
    'hero.config.desc': 'Options configurables.',
    'config.p1': 'Edite <code>data/settings.json</code> ou le menu Settings du TUI.',
    'config.setting': 'Parametre',
    'config.default': 'Defaut',
    'config.description': 'Description',
    'config.lang': 'Langue par defaut (vostfr/vf)',
    'config.player': 'Player video par defaut',
    'config.prefer_mp4': 'Preferer MP4 plutot que HLS',
    'config.auto_next': 'Lecture auto du prochain episode',
    'config.download_dir': 'Dossier de telechargement',
    'config.cache_hours': 'Duree de vie du cache catalogue',
    'config.proxy': 'Proxy HTTP (ex: http://127.0.0.1:8080)',
    'hero.terminal.title': 'Terminal Web',
    'hero.terminal.desc': 'Cherche et explore les animes en direct. Appels API reels sur les 7 sources.',
    'term.welcome1': 'Terminal Web anisama — <span class="t-accent">help</span> pour les commandes.',
    'term.welcome2': 'Sources : Anime-Sama · FRAnime · Voiranime · MyFluneo · AnimesUltra · French-Anime · AnimoFlix',
    'hero.cmds.title': 'Commandes du Terminal',
    'cmds.command': 'Commande',
    'cmds.description': 'Description',
    'cmds.example': 'Exemple',
    'cmds.help': 'Affiche l\'aide',
    'cmds.search': 'Cherche sur les 7 sources',
    'cmds.num': 'Affiche les episodes d\'un resultat',
    'cmds.play': 'Resout l\'URL video + ouvre le player',
    'cmds.sources': 'Liste les 7 sources',
    'cmds.stats': 'Stats du catalogue',
    'cmds.clear': 'Nettoie le terminal',
    'hero.trouble.title': 'Depannage',
    'trouble.no_results': 'Aucun resultat',
    'trouble.no_results.desc': 'La recherche utilise le fuzzy matching (rapidfuzz). Essaye des termes plus courts. La recherche cascade 7 sources.',
    'trouble.player': 'Le player ne se lance pas',
    'trouble.player.desc': 'Installe mpv ou VLC. Utilise <code>anisama -p vlc "titre"</code> pour specifier le player.',
    'trouble.windows': 'Erreur d\'import Windows',
    'trouble.windows.desc': 'Execute <code>python -m src</code> depuis la racine, ou <code>pip install -e .</code> puis <code>anisama</code>.',
    'trouble.domain': 'Domaine bloque',
    'trouble.domain.desc': 'Lance <code>anisama -U</code> pour forcer le refresh. Detection auto des domaines actifs.',
    'trouble.resolve': 'API retourne "Could not resolve"',
    'trouble.resolve.desc': 'Certaines sources utilisent Playwright (MyFluneo, AnimoFlix). Verifie que Chromium est installe sur le serveur API.',
    'hero.changelog.title': 'Changelog',
    'changelog.v201.latest': 'Dernière',
    'changelog.v201.new1': '<strong>Voiranime</strong> : source réparée et activée par défaut (nouvelles URLs <code>/&lt;slug&gt;/</code>, sagas, VF/VOSTFR, résolution directe).',
    'changelog.v201.new2': '<strong>Résolution Anime-Sama</strong> : sélection du meilleur miroir résolvable (ansembed/embed4me) et retour d\'un flux <code>m3u8</code> direct.',
    'changelog.v201.new3': '<strong>Page 404</strong> pour les URLs erronées ; les routes API renvoient toujours une erreur JSON.',
    'changelog.v201.new4': '<strong>Sécurité</strong> : rate limiting par palier, erreurs génériques avec <code>request_id</code>, HSTS/CSP, CORS whitelist, token Bearer optionnel, <code>robots.txt</code>.',
    'changelog.v201.fx1': '<strong>Anime-Sama</strong> : les scans/one-shots ne polluent plus la numérotation des épisodes.',
    'changelog.v201.fx2': '<strong>Cache épisodes</strong> : résoudre un épisode enregistre la liste complète sans écraser les URLs déjà résolues.',
    'changelog.v201.fx3': '<strong>Sources</strong> : FRAnime manquait dans la doc ; les 7 sources sont maintenant listées et documentées.',
    'changelog.v201.fx4': '<strong>Lecture HLS</strong> : les tokens <code>m3u8</code> liés à une autre IP/ASN basculent sur l\'iframe ansembed dans <code>/player</code>.',
    'changelog.v201.fx5': '<strong>Hygiène API</strong> : les cache-miss d\'épisodes sont limités à 20/min, HEAD est supporté pour les sondes, <code>/engine</code> est minimal et <code>/stats</code> + <code>/sources</code> partagent les mêmes compteurs.',
    'changelog.v201.fx6': '<strong>IP client</strong> : <code>CF-Connecting-IP</code> / <code>X-Forwarded-For</code> ne sont acceptés que depuis Cloudflare ou les proxies configurés ; logs et rate limits sont par client.',
    'changelog.v201.fx7': '<strong>Liste blanche Host</strong> : les requêtes qui ne ciblent pas <code>anisama.sexcaller.lol</code> sont fermées sans réponse.',
    'changelog.v201.fx8': '<strong>Quotas</strong> : les cache HITs d\'épisodes ne consomment plus de quota et les pourcentages de <code>/stats</code> totalisent 100%.',
    'changelog.v201.up1': '<strong>Mode clair</strong> : thème crème avec blocs de code, tableaux et terminal lisibles.',
    'changelog.v200.new1': '<strong>Fast engine</strong> : Anime-Sama + FRAnime via extraction directe des APIs (10-50x plus rapide, sans BeautifulSoup ni Playwright).',
    'changelog.v200.new2': 'Nouveaux endpoints : <code>/api/v2/seasons</code>, <code>/api/v2/hosts</code>, <code>/api/v2/engine</code>, <code>/health</code>.',
    'changelog.v200.new3': 'Resolution en course API/local avec write-back du cache et re-resolution <code>fresh=1</code> des URLs mortes.',
    'changelog.v200.fx1': '<strong>Scores bornes 0-100</strong> : plus de pourcentages > 100 % dans les resultats de recherche.',
    'changelog.v200.fx2': '<strong>Lecture</strong> : le CLI resout les embeds (uqload, etc.) en flux direct avant lecture ; fallback navigateur pour les pages watch2.',
    'changelog.v200.fx3': '<strong>Pterodactyl</strong> : ecoute sur <code>SERVER_PORT</code>, repli automatique sur <code>0.0.0.0</code> si <code>HOST</code> n\'est pas une interface locale.',
    'changelog.v200.fx4': '<strong>Docs web</strong> : navigation et couche a11y corrigees (<code>a11y.js</code> charge apres <code>script.js</code>).',
    'changelog.v200.up1': 'Playwright devient optionnel : installation plus legere, plus de disque plein sur les petits conteneurs.',
    'changelog.v110.latest': 'Latest',
    'changelog.v110.new1': '<strong>4 nouvelles sources</strong> : MyFluneo (~5400 entrees), AnimesUltra (~2600), French-Anime, AnimoFlix. Total : <strong>6 sources</strong>.',
    'changelog.v110.new2': '<strong>API centrale v2</strong> — server Python modulaire avec scraping cote serveur. Le client consomme uniquement du JSON propre.',
    'changelog.v110.new3': 'Routes API : <code>/api/v2/catalog</code> (pagination + filtres), <code>/api/v2/stats</code> (stats globales), <code>/api/v2/resolve-episode</code> (resolution par numero absolu).',
    'changelog.v110.fx1': '<strong>Scores de recherche realistes</strong> — remplace les scores artificiels (90% pour toute sous-chaine) par un calcul rapidfuzz <code>partial_ratio</code> + <code>token_set_ratio</code> avec penalites par mot en trop. Plus de faux positifs.',
    'changelog.v110.fx2': '<strong>Numero absolu des episodes</strong> — les episodes multi-saisons (ex: Naruto Shippuden EP500) sont maintenant correctement resolus en accumulant le nombre d\'episodes par saison.',
    'changelog.v110.fx3': '<strong>Menu interactif</strong> — un player sauvegarde dans les settings ne bloque plus le lancement du menu principal.',
    'changelog.v110.fx4': '<strong>Descriptions tronquees</strong> — les synopsis AniList/Jikan se terminent par <code>...</code> au lieu d\'etre coupees net.',
    'changelog.v110.up1': 'Fusion cross-source du catalogue avec deduplication par titre normalise (<code>alt_source</code>).',
    'changelog.v103.date': 'Original',
    'changelog.v103.text': 'Release originale par <a href="https://github.com/6sfy" style="color:var(--color-accent)">6sfy</a> avec Anime-Sama et Voiranime. Catalogue local, scraping client-side, recherche basique.',
    'term.help.block': '<div style="line-height:1.8;margin:2px 0">' +
      '<span class="t-accent t-bold">help</span> <span class="t-muted">— Aide</span><br>' +
      '<span class="t-accent t-bold">search</span> <span style="color:#888">&lt;query&gt;</span> <span class="t-muted">— Chercher sur 7 sources</span><br>' +
      '<span class="t-accent t-bold">[num]</span> <span class="t-muted">— Voir les episodes d\'un resultat</span><br>' +
      '<span class="t-accent t-bold">play</span> <span style="color:#888">&lt;ep_num&gt;</span> <span class="t-muted">— Resoudre et jouer un episode</span><br>' +
      '<span class="t-accent t-bold">sources</span> <span class="t-muted">— Lister les 7 sources</span><br>' +
      '<span class="t-accent t-bold">stats</span> <span class="t-muted">— Stats du catalogue</span><br>' +
      '<span class="t-accent t-bold">clear</span> <span class="t-muted">— Nettoyer le terminal</span></div>',
    'term.searching': 'Recherche de',
    'term.no_results': 'Aucun resultat.',
    'term.results': 'resultat(s) :',
    'term.pick_num': 'Tape <span class="t-accent">[num]</span> pour voir les episodes.',
    'term.fetching_eps': 'Recuperation des episodes...',
    'term.no_episodes': 'Aucun episode trouve.',
    'term.episodes_range': 'episodes (EP1 a EP',
    'term.and_more': '... et',
    'term.more': 'de plus.',
    'term.play_hint': 'Tape <span class="t-accent">play &lt;ep_num&gt;</span> pour resoudre. Ex: <span class="t-accent">play 1</span>',
    'term.ep_error': 'Erreur episodes : ',
    'term.resolving': 'Resolution EP',
    'term.resolved': '✅ ',
    'term.play_episode': '▶ Jouer cet episode',
    'term.cant_resolve': 'Impossible de resoudre EP',
    'term.error': 'Erreur : ',
    'term.usage_play': 'Usage: play &lt;numero_episode&gt;',
    'term.usage_search': 'Usage: search &lt;query&gt;',
    'term.usage_play_url': 'Usage: play &lt;url&gt;',
    'term.cant_resolve_url': 'Impossible de resoudre.',
    'term.resolved_type': 'Resolu : ',
    'term.open_player': '▶ Ouvrir le Player',
    'term.stats_total': 'Total: <span class="t-bold">',
    'term.stats_anime': 'anime',
    'term.stats_top_genres': 'Top genres: ',
    'term.cleared': 'Terminal nettoye. <span class="t-accent">help</span> pour l\'aide.',
    'term.unknown_cmd': 'Commande inconnue : <span class="t-bold">',
    'term.unknown_hint': '</span>. Tape <span class="t-accent">help</span>.',
    'term.http_err': 'HTTP '
  }
};

function i18n(key) {
  const lang = localStorage.getItem('anisama-lang') || 'en';
  if (lang === 'en') return '';
  const d = I18N[lang];
  return d && d[key] ? d[key] : '';
}

function applyLang() {
  const lang = localStorage.getItem('anisama-lang') || 'en';
  document.documentElement.setAttribute('lang', lang);
  document.getElementById('langLabel').textContent = lang.toUpperCase();
  const themeLabel = document.getElementById('themeLabel');
  if (themeLabel) {
    const t = localStorage.getItem('anisama-theme');
    const isDark = (t || document.documentElement.getAttribute('data-theme')) !== 'light';
    themeLabel.textContent = i18n(isDark ? 'theme.dark' : 'theme.light') || (isDark ? 'Dark Mode' : 'Light Mode');
  }
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (lang === 'en') {
      const def = el.getAttribute('data-i18n-default');
      if (def != null) {
        if (el.children.length > 0 || /<[^>]+>/.test(def)) {
          el.innerHTML = def;
        } else {
          el.textContent = def;
        }
      }
      return;
    }
    const val = i18n(key);
    if (!val) return;
    if (el.children.length > 0 || /<[^>]+>/.test(val)) {
      el.innerHTML = val;
    } else {
      el.textContent = val;
    }
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    if (lang === 'en') {
      const def = el.getAttribute('data-i18n-placeholder-default');
      if (def != null) el.setAttribute('placeholder', def);
      return;
    }
    const val = i18n(key);
    if (val) el.setAttribute('placeholder', val);
  });

  injectCopyButtons();
}

function toggleLang() {
  const cur = localStorage.getItem('anisama-lang') || 'en';
  const next = cur === 'en' ? 'fr' : 'en';
  localStorage.setItem('anisama-lang', next);
  applyLang();
}

function injectCopyButtons() {
  document.querySelectorAll('.code-block').forEach(block => {
    const bar = block.querySelector('.code-bar');
    if (!bar || bar.querySelector('.copy-btn')) return;
    const btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.title = 'Copy';
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
    btn.addEventListener('click', () => {
      const body = block.querySelector('.code-body');
      if (!body) return;
      navigator.clipboard.writeText(body.textContent).then(() => {
        btn.classList.add('copied');
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
        setTimeout(() => {
          btn.classList.remove('copied');
          btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
        }, 2000);
      });
    });
    bar.appendChild(btn);
  });
}

function showPage(id, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const page = document.getElementById('p-' + id);
  if (page) page.classList.add('active');
  document.querySelectorAll('.nav-group-item').forEach(a => a.classList.remove('active'));
  if (el) el.classList.add('active');
  closeSidebar();
  if (id === 'terminal') document.getElementById('termIn')?.focus();
  window.scrollTo(0, 0);
  return false;
}

function toggleGroup(el) {
  const group = el.closest('.nav-group');
  if (group) group.classList.toggle('collapsed');
}

function closeSidebar() {
  document.getElementById('sidebar')?.classList.remove('open');
  document.getElementById('overlay')?.classList.remove('active');
}

function toggleSidebar() {
  document.getElementById('sidebar')?.classList.toggle('open');
  document.getElementById('overlay')?.classList.toggle('active');
}

function filterNav(q) {
  const items = document.querySelectorAll('.nav-group-item');
  const query = q.toLowerCase().trim();
  items.forEach(a => {
    a.style.display = (!query || a.textContent.toLowerCase().includes(query)) ? '' : 'none';
  });
}

function toggleTheme() {
  const html = document.documentElement;
  const isDark = html.getAttribute('data-theme') !== 'light';
  html.setAttribute('data-theme', isDark ? 'light' : 'dark');
  localStorage.setItem('anisama-theme', isDark ? 'light' : 'dark');
  const label = document.getElementById('themeLabel');
  if (label) label.textContent = i18n(isDark ? 'theme.light' : 'theme.dark') || (isDark ? 'Light Mode' : 'Dark Mode');
}
const savedTheme = localStorage.getItem('anisama-theme');
if (savedTheme) {
  document.documentElement.setAttribute('data-theme', savedTheme);
}

const termOut = document.getElementById('termOut');
const termIn = document.getElementById('termIn');
let history = [], hi = -1, results = [], current_eps = null;

function tp(html, cls) {
  const d = document.createElement('div');
  d.className = 'l' + (cls ? ' ' + cls : '');
  d.innerHTML = html;
  termOut.appendChild(d);
  termOut.scrollTop = termOut.scrollHeight;
}

async function ap(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

termIn.addEventListener('keydown', async function(e) {
  if (e.key === 'Enter') {
    const cmd = this.value.trim(); this.value = '';
    if (!cmd) return;
    history.push(cmd); hi = history.length;
    tp('<span class="t-accent">anisama@web:~$</span> ' + esc(cmd));
    const parts = cmd.split(/\s+/);
    const c = parts[0].toLowerCase();
    const a = parts.slice(1);
    try {
      if (c === 'help') {
        tp(i18n('term.help.block') || ('<div style="line-height:1.8;margin:2px 0">' +
          '<span class="t-accent t-bold">help</span> <span class="t-muted">— Help</span><br>' +
          '<span class="t-accent t-bold">search</span> <span style="color:#888">&lt;query&gt;</span> <span class="t-muted">— Search across 7 sources</span><br>' +
          '<span class="t-accent t-bold">[num]</span> <span class="t-muted">— Show episodes of a result</span><br>' +
          '<span class="t-accent t-bold">play</span> <span style="color:#888">&lt;ep_num&gt;</span> <span class="t-muted">— Resolve and play an episode</span><br>' +
          '<span class="t-accent t-bold">sources</span> <span class="t-muted">— List the 7 sources</span><br>' +
          '<span class="t-accent t-bold">stats</span> <span class="t-muted">— Catalog stats</span><br>' +
          '<span class="t-accent t-bold">clear</span> <span class="t-muted">— Clear the terminal</span></div>'));
      }
      else if (c === 'search') {
        if (!a.length) { tp('<span class="t-red">' + (i18n('term.usage_search') || 'Usage: search &lt;query&gt;') + '</span>'); return; }
        const searching = i18n('term.searching') || 'Searching for';
        tp('<span class="t-muted">' + searching + ' <span class="t-accent">' + esc(a.join(' ')) + '</span>...</span>');
        const d = await ap(API_BASE + '/api/v2/search?q=' + encodeURIComponent(a.join(' ')));
        const items = d.results || d;
        if (!items || !items.length) { tp('<span class="t-red">' + (i18n('term.no_results') || 'No results.') + '</span>'); return; }
        results = items;
        const resLabel = i18n('term.results') || 'result(s):';
        tp('<span class="t-green">' + items.length + ' ' + resLabel + '</span>');
        items.forEach((r, i) => {
          const srcList = [...new Set([r.primary_source, ...(r.sources || [])].filter(Boolean))];
          tp('&nbsp; <span class="t-num">[' + i + ']</span> ' + esc(r.title) + ' <span class="t-muted">(' + srcList.join(', ') + ')</span>');
        });
        tp('<span class="t-muted">' + (i18n('term.pick_num') || 'Type <span class="t-accent">[num]</span> to view episodes.') + '</span>');
      }
      else if (/^\d+$/.test(c) && !isNaN(parseInt(c)) && results.length) {
        const idx = parseInt(c);
        if (idx >= results.length) { tp('<span class="t-red">Invalid index (0-' + (results.length - 1) + ')</span>'); return; }
        const r = results[idx];
        const link_lower = (r.link || '').toLowerCase();
        let src = r.primary_source || 'anime-sama';
        if (link_lower.includes('myfluneo')) src = 'myfluneo';
        else if (link_lower.includes('voiranime')) src = 'voiranime';
        else if (link_lower.includes('animesultra')) src = 'animesultra';
        else if (link_lower.includes('french-anime')) src = 'frenchanime';
        else if (link_lower.includes('animoflix')) src = 'animoflix';
        else if (link_lower.includes('anime-sama')) src = 'anime-sama';
        const slug = r.slug || r.link.split('/').pop();
        tp('<span class="t-green">📺 ' + esc(r.title) + '</span>');
        tp('<span class="t-muted">' + (i18n('term.fetching_eps') || 'Fetching episodes...') + '</span>');
        try {
          const eps = await ap(API_BASE + '/api/v2/episodes?source=' + src + '&slug=' + encodeURIComponent(slug) + '&url=' + encodeURIComponent(r.link));
          const list = eps.episodes || [];
          if (!list.length) { tp('<span class="t-red">' + (i18n('term.no_episodes') || 'No episodes found.') + '</span>'); return; }
          current_eps = { source: src, slug: slug, total: eps.total || list.length, episodes: list, anime_title: r.title };
          const epRange = i18n('term.episodes_range') || 'episodes (EP1 to EP';
          const andMore = i18n('term.and_more') || '... and';
          const more = i18n('term.more') || 'more.';
          tp('<span class="t-green">' + current_eps.total + ' ' + epRange + current_eps.total + '):</span>');
          const show = list.slice(0, 20);
          show.forEach((e) => {
            tp('&nbsp; <span class="t-num">EP' + e.number + '</span> <span class="t-muted">' + (e.season || '') + '</span>');
          });
          if (list.length > 20) tp('<span class="t-muted">' + andMore + ' ' + (list.length - 20) + ' ' + more + '</span>');
          tp('<span class="t-muted">' + (i18n('term.play_hint') || 'Type <span class="t-accent">play &lt;ep_num&gt;</span> to resolve. Ex: <span class="t-accent">play 1</span>') + '</span>');
        } catch (e) {
          tp('<span class="t-red">' + (i18n('term.ep_error') || 'Episode error: ') + esc(e.message) + '</span>');
        }
      }
      else if (c === 'play' && current_eps && a.length) {
        const ep_num = parseInt(String(a[0]).replace(/\D+/g, ''), 10);
        if (isNaN(ep_num)) { tp('<span class="t-red">' + (i18n('term.usage_play') || 'Usage: play &lt;episode_number&gt;') + '</span>'); return; }
        tp('<span class="t-muted">' + (i18n('term.resolving') || 'Resolving EP') + ep_num + '...</span>');
        try {
          const d = await ap(API_BASE + '/api/v2/resolve-episode?source=' + current_eps.source + '&slug=' + current_eps.slug + '&num=' + ep_num);
          if (d.url) {
            const resolved = i18n('term.resolved') || '✅ ';
            const playEpisode = i18n('term.play_episode') || '▶ Play this episode';
            tp('<span class="t-green">' + resolved + esc(current_eps.anime_title) + ' EP' + ep_num + ' — ' + (d.type || 'mp4') + '</span>');
            tp('&nbsp; <a href="' + API_BASE + '/player?url=' + encodeURIComponent(d.url) + '&title=' + esc(current_eps.anime_title) + '%20EP' + ep_num + '" target="_blank" style="color:#ff4500;font-weight:600;text-decoration:underline">' + playEpisode + '</a>');
            tp('&nbsp; <span class="t-muted" style="font-size:11px;word-break:break-all">' + esc(d.url) + '</span>');
          } else tp('<span class="t-red">' + (i18n('term.cant_resolve') || 'Could not resolve EP') + ep_num + '.</span>');
        } catch (e) {
          tp('<span class="t-red">' + (i18n('term.error') || 'Error: ') + esc(e.message) + '</span>');
        }
      }
      else if (c === 'play') {
        if (!a.length) { tp('<span class="t-red">' + (i18n('term.usage_play_url') || 'Usage: play &lt;url&gt;') + '</span>'); return; }
        tp('<span class="t-muted">Resolving...</span>');
        const d = await ap(API_BASE + '/api/v2/resolve?url=' + encodeURIComponent(a[0]) + '&source=myfluneo');
        const u = d.url || d.resolved?.url;
        if (u) {
          const resolvedType = i18n('term.resolved_type') || 'Resolved: ';
          const openPlayer = i18n('term.open_player') || '▶ Open Player';
          tp('<span class="t-green">' + resolvedType + (d.type || d.resolved?.type || '?') + '</span>');
          tp('&nbsp; <a href="' + API_BASE + '/player?url=' + encodeURIComponent(u) + '&title=Anime" target="_blank" style="color:#ff4500;font-weight:600;text-decoration:underline">' + openPlayer + '</a>');
          tp('&nbsp; <span class="t-muted" style="font-size:11px;word-break:break-all">' + esc(u) + '</span>');
        } else tp('<span class="t-red">' + (i18n('term.cant_resolve_url') || 'Could not resolve.') + '</span>');
      }
      else if (c === 'sources') {
        const d = await ap(API_BASE + '/api/v2/sources');
        if (d.sources) d.sources.forEach(s => tp('&nbsp; <span class="t-green t-bold">' + esc(s.name) + '</span> <span class="t-muted">(' + s.count + ' entries, ' + s.id + ')</span>'));
      }
      else if (c === 'stats') {
        const d = await ap(API_BASE + '/api/v2/stats');
        const statsTotal = i18n('term.stats_total') || 'Total: <span class="t-bold">';
        const statsAnime = i18n('term.stats_anime') || 'anime';
        const topGenres = i18n('term.stats_top_genres') || 'Top genres: ';
        tp('<span class="t-green">📊 ' + (i18n('cmds.stats') || 'Catalog stats') + '</span>');
        tp('&nbsp; ' + statsTotal + d.total + '</span> ' + statsAnime);
        if (d.by_source) {
          Object.entries(d.by_source).forEach(([k, v]) => {
            tp('&nbsp; ' + esc(k) + ': <span class="t-bold">' + v.count + '</span> (' + v.percentage + '%)');
          });
        }
        if (d.top_genres) {
          tp('&nbsp; ' + topGenres + d.top_genres.slice(0, 5).map(g => g.name + ' (' + g.count + ')').join(', '));
        }
      }
      else if (c === 'clear') { termOut.innerHTML = ''; tp('<span class="t-muted">' + (i18n('term.cleared') || 'Terminal cleared. <span class="t-accent">help</span> for help.') + '</span>'); }
      else { tp('<span class="t-red">' + (i18n('term.unknown_cmd') || 'Unknown command: <span class="t-bold">') + esc(c) + (i18n('term.unknown_hint') || '</span>. Type <span class="t-accent">help</span>.') + '</span>'); }
    } catch (e) { tp('<span class="t-red">' + (i18n('term.error') || 'Error: ') + esc(e.message) + '</span>'); }
  }
  else if (e.key === 'ArrowUp') { e.preventDefault(); if (hi > 0) { hi--; this.value = history[hi] || ''; } }
  else if (e.key === 'ArrowDown') { e.preventDefault(); if (hi < history.length - 1) { hi++; this.value = history[hi] || ''; } else { hi = history.length; this.value = ''; } }
});

document.querySelector('.term-body')?.addEventListener('click', () => termIn.focus());

document.addEventListener('DOMContentLoaded', () => {

  document.querySelectorAll('[data-i18n]').forEach(el => {
    if (!el.hasAttribute('data-i18n-default')) {
      el.setAttribute('data-i18n-default', el.children.length > 0 ? el.innerHTML : el.textContent);
    }
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    if (!el.hasAttribute('data-i18n-placeholder-default')) {
      el.setAttribute('data-i18n-placeholder-default', el.getAttribute('placeholder') || '');
    }
  });
  applyLang();
  injectCopyButtons();
  const t = localStorage.getItem('anisama-theme');
  const label = document.getElementById('themeLabel');
  if (label) label.textContent = i18n(t === 'light' ? 'theme.dark' : 'theme.light') || (t === 'light' ? 'Dark Mode' : 'Light Mode');
});
