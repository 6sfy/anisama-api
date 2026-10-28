# anime-engine — moteur d'extraction Anime-Sama + FRAnime

Moteur Python autonome : recherche, saisons, épisodes, résolution de liens.
Aucune dépendance lourde : `requests` uniquement (pas de bs4, pas de Playwright).

```
anime_engine/
├── net.py          session requests + retries + proxy optionnel
├── anime_sama.py   scraper anime-sama.to  (liens d'embed directs)
├── franime.py      client api.franime.fr  (API JSON)
├── engine.py       façade unifiée
├── cli.py          interface ligne de commande
└── api_server.py   serveur HTTP JSON (zéro dépendance)
```

---

## 1. Anime-Sama — API extraite

Base : `https://anime-sama.to` (miroirs : `.tv`, `.si`, `.org`)

### Recherche
```
POST /template-php/defaut/fetch.php
Content-Type: application/x-www-form-urlencoded
Body: query=naruto
```
Réponse HTML, un résultat par `<a class="asn-search-result" href="...">`
contenant un `<h3 class="asn-search-result-title">`. Le `href` donne le slug :
`https://anime-sama.to/catalogue/naruto/`.

### Saisons
```
GET /catalogue/{slug}/
```
Les saisons sont déclarées en JavaScript dans la page :
```js
panneauAnime("Avec Fillers", "saison1/vostfr")
panneauAnime("Sans Fillers", "saison1hs/vostfr")
panneauAnime("Film", "film/vostfr")
panneauAnime("Kai", "kai/vostfr")
```
Regex : `panneau(?:Anime|Film|Scan|Visual)\s*\(\s*["'](.+?)["']\s*,\s*["'](.+?)["']\s*\)`
Filtrer les entrées `("nom","url")` (template) et les mots-clés
`scan|manhwa|webtoon|manhua|manga|novel`.

### Épisodes — le cœur
```
GET /catalogue/{slug}/{saison}/episodes.js
```
Exemple de contenu :
```js
var eps1 = ['https://lpayer.embed4me.com/#sat5e', 'https://lpayer.embed4me.com/#z9j18', ...];
var eps2 = ['https://ansembed.net/embed-y2dfh1ndem54.html', ...];
```
**Un tableau = un lecteur.** L'épisode *i* (1-based) a pour miroirs
`{eps1: T1[i-1], eps2: T2[i-1], ...}`. Aucune clé, aucun token : les URLs
sont utilisables directement (yt-dlp, mpv, iframe).

La page saison expose aussi `lecteursInfos`, utile pour filtrer les hôtes morts :
```js
var lecteursInfos = {"ansembed.net":{"nom":"Vidmoly","pub":1,"hd":true},
                     "sibnet.ru":{"nom":"Sibnet","pub":0,"hd":false,"mort":true}, ...}
```

Hôtes rencontrés : `lpayer.embed4me.com`, `ansembed.net` (Vidmoly),
`vidmoly.to/.net/.biz`, `smoothpre.com`, `sendvid.com`, `sibnet.ru`,
`uqload.vc/.net`, `movearnpre.com`, `vk`.

### Cas vus
| Anime | Saison | Épisodes | Lecteurs |
|---|---|---|---|
| naruto | Avec Fillers | 220 | embed4me, ansembed |
| naruto | Sans Fillers | 220 | — |

⚠️ `episodes.js` est servi avec un paramètre de version (`?filever=18916`) :
il faut lire l'URL exacte dans le HTML, ne pas la coder en dur.

---

## 2. FRAnime — API extraite

Base : `https://api.franime.fr/api/`

En-têtes attendus : `Origin: https://franime.fr`, `Referer: https://franime.fr/`

### Catalogue
```
GET /animes
```
→ 2 553 entrées, ~11,4 Mo. Champs : `id`, `title`, `titleO`, `titles{}`,
`description`, `note`, `themes`, `format`, `status`, `nsfw`, `startDate`,
`endDate`, `affiche`, `banner`, `updatedDate`, `saisons[]`.

`saisons[]` contient déjà la structure complète :
```json
{"title": "Saison 1",
 "episodes": [
   {"title": "Épisode 1",
    "lang": {"vo": {"lecteurs": ["vidmoly","sendvid","filemoon","sibnet"]},
             "vf": {"lecteurs": [...]}}}
 ]}
```
→ pas besoin de requête supplémentaire pour connaître les lecteurs disponibles.

### Épisodes détaillés
```
GET /anime-seasons/{anime_id}/{season_number}
```
`season_number` est **1-based** ici. Retourne :
```json
{"kitsuId": 13051,
 "episodes": [{"number": 1, "title": "Boruto Uzumaki !",
               "thumbnail": "https://media.kitsu.app/...",
               "airDate": "2017-04-05",
               "_id": "67defcd1f2a104c85435b999"}]}
```

### Résolution — attention aux INDEX
```
GET /anime/{anime_id}/{season_index}/{episode_index}/{lang}/{lecteur_index}
```
Découvert dans le bundle du site :
```js
GET_LECTEUR: (e,t,s,i,a) => "anime/"+e+"/"+t+"/"+s+"/"+i+"/"+a
// appelé avec {animeId, saisonIndex, episodeIndex, lang, lecteurIndex}
```
**Les trois derniers numéros sont des positions 0-based, pas des numéros.**
`lang` ∈ `vo` (VOSTFR) | `vf`.

Exemples validés :
```
/api/anime/48834/0/0/vo/0   -> 200
/api/anime/48834/1/0/vf/1   -> 200
/api/anime/48834/1/1/vo/2   -> 200
```

Réponse : du texte brut, une URL
`https://franime.fr/watch2/?a=<b64>&b=<b64>&...&o=<b64>`

### La limite : le blob watch2
Les 15 paramètres `a`…`o` sont un payload binaire : chaque paramètre est
`base64(blob)`. Le décodage donne, selon le paramètre, du texte décalé ou des
octets bruts (`m` fait 48 octets). Le lien final (sibnet/vidmoly…) est décodé
côté navigateur par le bundle de la route `/watch2`, derrière un challenge
Cloudflare (« Just a moment… », 403 en curl).

Deux options pour le contourner :
1. iframe vers l'URL `watch2` — lecture OK, pas d'URL directe ;
2. navigateur headless avec challenge résolu → lire `iframe.src` après décodage.

`watchable_in_iframe: True` est renvoyé par `resolve()` pour distinguer ce cas.

---

## 3. Utilisation

```bash
pip install requests
export PYTHONPATH=/chemin/vers/parent   # dossier contenant anime_engine/
```

```python
from anime_engine import Engine
e = Engine()

# recherche (les deux sources, dédoublonnées)
e.search("naruto")

# anime-sama
ss = e.seasons("anime-sama", "naruto")
eps = e.episodes("anime-sama", "naruto", ss[0]["url"])
print(eps[0]["mirrors"])            # {'eps1': 'https://...', 'eps2': 'https://...'}
e.resolve("anime-sama", "naruto", 5, ss[0]["url"])

# franime
e.seasons("franime", "13051")
eps = e.episodes("franime", "13051", season_index=0)
e.resolve("franime", "13051", 1, season_index=0, lang="vo")
```

### CLI
```bash
python -m anime_engine.cli search "dragon ball"
python -m anime_engine.cli seasons anime-sama naruto
python -m anime_engine.cli episodes anime-sama naruto
python -m anime_engine.cli resolve anime-sama naruto 5
python -m anime_engine.cli hosts anime-sama naruto
python -m anime_engine.cli seasons franime 13051
python -m anime_engine.cli resolve franime 13051 1 --lang vo
```

### Serveur HTTP JSON
```bash
python -m anime_engine.api_server          # PORT=8080 par défaut
```
```
GET /search?q=&source=
GET /seasons?source=&slug=
GET /episodes?source=&slug=&season_index=
GET /resolve?source=&slug=&number=&lang=
GET /hosts?slug=&season_url=
```

### Proxy (optionnel)
```bash
export ENGINE_PROXY=http://host:port
```
S'applique à toutes les requêtes (utile si l'IP serveur est bloquée).

---

## 4. Pièges rencontrés

- **`http.py` interdit comme nom de fichier** dans un package : masque le module
  stdlib `http`, ce qui casse `requests`/`urllib3` (`six.moves.http_client`).
  Le module réseau s'appelle donc `net.py`.
- Anime-Sama : le `<script src=` de `episodes.js` utilise des **quotes simples**
  et un `?filever=`, un regex à quotes doubles échoue silencieusement.
- Anime-Sama : la recherche renvoie aussi des entrées manga/scan — filtrer.
- FRAnime : passer des numéros au lieu d'index renvoie
  `404 {"msg":"Aucun lecteur disponible pour cette épisode"}` — message trompeur,
  ce n'est pas une absence de source mais un mauvais index.
- FRAnime : `/animes` pèse 11 Mo → mettre en cache, ne pas rappeler par requête.
- FRAnime : en rafale, l'API renvoie un challenge Cloudflare au lieu de JSON ;
  3 retries avec backoff dans `net.py`.

## 5. Découverte du domaine actif (anime-sama)

L'URL canonique est **`https://anime-sama.to/`**. Pour récupérer le bon
domaine à tout moment, le moteur interroge la page de statut officielle
**`https://anime-sama.pw`** : son endpoint `?check=<domaine>` teste le
domaine CÔTÉ SERVEUR (fonctionne même si l'IP du client est bloquée par
Cloudflare).

```
GET https://anime-sama.pw/?check=anime-sama.to&_<timestamp>
-> {"status":"online","code":200}     (ou "redirect"/"offline")
```

Ordre de résolution dans `_pick_domain()` :
1. `?check=` sur la liste `DOMAINS` — premier domaine "online" ;
2. essai direct rapide (si notre IP passe) ;
3. fallback `anime-sama.to`.
