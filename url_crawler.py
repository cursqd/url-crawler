from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from urllib.parse import urlparse, urljoin
import random, re, socket, sys, threading, warnings

import requests
from bs4 import BeautifulSoup, Comment, FeatureNotFound, XMLParsedAsHTMLWarning

try:
    import chardet
except ImportError:
    chardet = None

from colorama import Fore, Style, init
init(autoreset=True)
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


ABS_URL = re.compile(r"""https?://[^\s"'`<>(){}\[\]\\^|]+""", re.I)
Q_DBL = re.compile(r'"((?:https?:)?//[^\s"<>]{4,400}|/[a-zA-Z0-9_][\w\-./~?&=%+#:@,;]{1,400})"')
Q_SGL = re.compile(r"'((?:https?:)?//[^\s'<>]{4,400}|/[a-zA-Z0-9_][\w\-./~?&=%+#:@,;]{1,400})'")
Q_TCK = re.compile(r"`((?:https?:)?//[^`]{4,400}|/[^`]{1,400})`")
CSS_URL = re.compile(r"""url\(\s*['"]?([^'")\s]+)['"]?\s*\)""", re.I)
API_RE = re.compile(r"/(?:api|graphql|gql|rest|rpc|webhook|hook|v\d+)(?:/|\?|$)", re.I)
LIB_JS = re.compile(
    r"(?:^|/)(?:jquery|bootstrap|react|react-dom|vue|angular|ember|lodash|underscore"
    r"|moment|dayjs|three|d3|chart|highcharts|echarts|pixi|phaser|mathjax|katex|prism"
    r"|googletagmanager|ga|gtag|gtm|fbevents|hotjar|mixpanel|segment|optimizely"
    r"|recaptcha|hcaptcha|stripe|paypal|adsbygoogle|tinymce|ckeditor|monaco)"
    r"[\w.\-]*\.js$", re.I)
FILE_RE = re.compile(
    r".+\.(pdf|zip|jpe?g|gif|webp|png|ico|svg|bmp|tiff?|docx?|xlsx?|pptx?|odt|ods|odp|rtf|txt"
    r"|mp3|wav|flac|ogg|m4a|aac|mp4|m4v|webm|avi|mkv|mov|wmv|flv"
    r"|exe|msi|deb|rpm|dmg|pkg|apk|appimage|tar|gz|bz2|xz|rar|7z|tgz"
    r"|csv|tsv|json|xml|yaml|yml|toml|css|js|mjs|map|ts|tsx|jsx|py|sh|bat|ps1|rb|php"
    r"|woff2?|ttf|otf|eot)$", re.I)


PROBES = [
    "/robots.txt", "/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml",
    "/sitemap.xml.gz", "/humans.txt", "/security.txt",
    "/.well-known/security.txt", "/.well-known/change-password",
    "/.well-known/openid-configuration", "/.well-known/oauth-authorization-server",
    "/.well-known/assetlinks.json", "/.well-known/apple-app-site-association",
    "/favicon.ico", "/manifest.json", "/manifest.webmanifest", "/browserconfig.xml",
    "/crossdomain.xml", "/clientaccesspolicy.xml", "/ads.txt", "/app-ads.txt",
    "/admin", "/admin/", "/admin/login", "/administrator", "/login", "/signin",
    "/sign-in", "/auth", "/auth/login", "/logout", "/dashboard", "/portal",
    "/console", "/cpanel", "/control", "/manage", "/management",
    "/wp-admin/", "/wp-login.php", "/user/login", "/users/sign_in",
    "/api", "/api/", "/api/v1", "/api/v1/", "/api/v2", "/api/v2/", "/api/v3",
    "/api/health", "/api/status", "/api/version", "/api/docs", "/api/swagger",
    "/openapi.json", "/openapi.yaml", "/openapi.yml",
    "/swagger.json", "/swagger.yaml", "/swagger-ui", "/swagger-ui.html",
    "/swagger-ui/", "/api-docs", "/api-docs/", "/api/explorer",
    "/graphql", "/graphiql", "/playground", "/altair", "/rest", "/jsonrpc",
    "/wp-json/", "/wp-json/wp/v2/users", "/wp-content/", "/wp-includes/",
    "/xmlrpc.php", "/?author=1",
    "/health", "/healthz", "/healthcheck", "/livez", "/readyz",
    "/status", "/ping", "/version", "/build", "/info",
    "/actuator", "/actuator/health", "/actuator/info", "/actuator/env",
    "/actuator/metrics", "/actuator/mappings", "/actuator/beans",
    "/metrics", "/prometheus", "/server-status", "/server-info",
    "/.env", "/.env.local", "/.env.production", "/.env.development",
    "/.git/config", "/.git/HEAD", "/.git/index",
    "/.svn/entries", "/.hg/", "/.bzr/", "/.DS_Store", "/Thumbs.db",
    "/config.json", "/config.yml", "/settings.json", "/appsettings.json",
    "/package.json", "/composer.json", "/yarn.lock", "/package-lock.json",
    "/backup", "/backup.zip", "/backup.tar.gz", "/backup.sql",
    "/dump.sql", "/db.sql", "/database.sql",
    "/phpinfo.php", "/info.php", "/test.php", "/debug",
    "/register", "/signup", "/profile", "/settings", "/account",
    "/upload", "/uploads", "/files", "/download", "/downloads",
    "/search", "/feed", "/rss", "/atom", "/feed.xml", "/rss.xml",
]


SUBS = """
www www1 www2 www3 ww1 ww2 web web1 web2 web3 site sites home homepage main default index
mail mail1 mail2 mail3 smtp smtp1 smtp2 pop pop3 imap imap1 imap2 webmail email mx mx1 mx2 mx3
exchange owa autodiscover autoconfig relay mta newsletter marketing-mail bounce lists list
ns ns1 ns2 ns3 ns4 ns5 dns dns1 dns2 dns3 resolver whois rdns
ftp ftp1 ftp2 sftp ssh telnet vpn vpn1 vpn2 rdp remote remote1 remote2 gateway proxy proxy1
proxy2 socks tunnel wg wireguard openvpn
cdn cdn1 cdn2 cdn3 static static1 static2 assets asset media media1 media2 images image img
img1 img2 img3 pics photos thumbs video videos vid audio music files file downloads download
dl upload uploads cache fonts
api api1 api2 api3 api4 apiv1 apiv2 apiv3 v1 v2 v3 v4 rest graphql gql grpc rpc ws wss
socket sockets stream streaming live broadcast rtmp app apps application
admin admins administrator panel cpanel whm directadmin plesk ispmanager dashboard portal
portal1 portal2 control controlpanel manage management console manager secure login logon
signin sign-in auth oauth oauth2 sso saml ldap ad id identity account accounts user users
my myaccount profile register signup sign-up verify activate reset forgot password 2fa mfa
session
dev dev1 dev2 dev3 development developer developers stage stg staging staging1 staging2 test
tests testing test1 test2 test3 test4 qa qa1 qa2 uat preprod pre-prod prod production demo
demos sandbox preview beta beta1 beta2 alpha rc experimental lab labs
git gitlab github bitbucket svn code source repo repos repository build builds ci ci-cd cicd
jenkins travis circle drone teamcity bamboo deploy deployment release releases artifact
artifacts nexus harbor registry docker docker-registry
chat talk meet meeting conference calls voice voicemail fax sms push notify notifications
alerts irc
docs doc documentation wiki kb knowledge knowledgebase help helpdesk support support1 support2
ticket tickets feedback faq forum forums community discuss discussion answers
shop store stores buy sell cart checkout pay payment payments billing invoice invoices order
orders customer customers client clients partner partners vendor vendors affiliate affiliates
merchant merchants marketplace
blog blogs news press tv radio podcast podcasts content cms wp wp-admin wordpress drupal
joomla ghost search find explore discover
mkt marketing promo promotions campaign campaigns ads advertising track tracker tracking
analytics stats metrics ga matomo piwik
monitor monitoring status statuspage health healthcheck uptime logs log logger logging syslog
kibana elk grafana prometheus graph graphite datadog newrelic sentry rollbar splunk zabbix
nagios
cloud k8s kube kubernetes rancher openshift container containers swarm s3 blob storage
object-storage minio fs nfs backup backups archive archives restore db db1 db2 database
databases mysql mariadb postgres postgresql pg mongo mongodb redis memcached elastic
elasticsearch es opensearch solr kafka rabbit rabbitmq queue queues broker mq nats couch
couchdb cassandra influx influxdb
ssl tls cert certs ca pki vault secret secrets firewall waf ids ips siem soc honeypot csp
m mobile mobi ios android iot device devices embed
us uk eu ca au de fr es it jp cn in br mx ru kr sg hk nl se no fi dk pl tr za ae
north south east west europe asia americas
office office365 o365 exchange1 sharepoint intranet internal private public external ext int
corp corporate company enterprise
hr jobs careers people team teams staff directory training learn learning edu education
academy university
events event calendar schedule booking reservations
old new legacy tmp temp current
host host1 host2 host3 srv srv1 srv2 srv3 server server1 server2 server3 node node1 node2
node3 edge edge1 edge2 origin origin1 origin2
zoom slack salesforce hubspot jira confluence trello asana notion monday linear
go link links url urls redirect out in share shared
tools tool utils utility research feed feeds rss atom webhook webhooks callback callbacks
hook hooks ping test-domain internal-api private-api
""".split()


UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class urlcrawler:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": random.choice(UAS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self.internal = set()
        self.external = set()
        self.hidden = set()
        self.files = set()
        self.apis = set()
        self.bad = set()
        self.js_seen = set()
        self._done = set()
        self.subs = list(dict.fromkeys(SUBS))
        self._wc = set()
        self._lk = threading.Lock()
        self._plk = threading.Lock()

    def out(self, msg):
        with self._plk:
            print(msg)

    def enc(self, r):
        ct = r.headers.get('Content-Type', '').lower()
        if 'charset=' in ct:
            e = ct.split('charset=')[-1].split(';')[0].strip().strip('"\'')
            if e: return e
        if chardet:
            try:
                d = chardet.detect(r.content[:4096])
                if d and d.get('encoding'): return d['encoding']
            except Exception:
                pass
        return getattr(r, 'apparent_encoding', None) or 'utf-8'

    def valid(self, url):
        try:
            p = urlparse(url)
            return bool(p.netloc) and p.scheme in ('http', 'https')
        except Exception:
            return False

    def dom(self, url):
        return urlparse(url).netloc

    def norm(self, url):
        url = url.strip()
        p = urlparse(url)
        if not p.scheme and not p.netloc and p.path:
            p = urlparse("http://" + url)
        return f"{p.scheme or 'http'}://{p.netloc or p.path}{p.path if p.netloc else ''}"

    def is_sub(self, dom, c):
        return c == dom or c.endswith("." + dom)

    def resolve(self, h):
        try:
            return socket.gethostbyname(h)
        except (socket.gaierror, socket.herror, socket.timeout, UnicodeError, OSError):
            return None

    def wildcard(self, d):
        # probe random hosts; any ip they hit = wildcard, filter later
        ips = set()
        for _ in range(3):
            ip = self.resolve(f"nonexistent-{random.randint(10**9, 10**10)}.{d}")
            if ip: ips.add(ip)
        if ips:
            self.out(f"{Fore.YELLOW}[!] wildcard dns on {d} (ips: {', '.join(sorted(ips))}){Fore.RESET}")
        self._wc = ips
        return ips

    def paths_in(self, text, base):
        out = set()
        if not text: return out
        if len(text) > 3_000_000: text = text[:3_000_000]
        for m in ABS_URL.findall(text):
            c = m.rstrip(",.;:!?)\"'`")
            if c: out.add(c)
        for pat, tpl in ((Q_DBL, False), (Q_SGL, False), (Q_TCK, True)):
            for m in pat.findall(text):
                if tpl and "${" in m:
                    m = m.split("${", 1)[0]
                m = m.strip().rstrip("/")
                if not m or (not m.startswith("/") and not m.startswith("http")): continue
                try: full = urljoin(base, m)
                except Exception: continue
                if self.valid(full): out.add(full)
        for m in CSS_URL.findall(text):
            try: full = urljoin(base, m)
            except Exception: continue
            if self.valid(full): out.add(full)
        return out

    def record(self, path, src):
        if not path: return False
        try: p = urlparse(path)
        except Exception: return False
        n = f"{p.scheme}://{p.netloc}{p.path}"
        if not self.valid(n): return False
        is_file = bool(FILE_RE.search(n))
        if is_file:
            with self._lk:
                new = n not in self.files
                if new: self.files.add(n)
            if new: self.out(f"{Fore.LIGHTBLACK_EX}[!] file: {n}{Fore.RESET}")
        sd = self.dom(src) if src else ""
        if sd and sd not in n:
            with self._lk:
                new = n not in self.external
                if new: self.external.add(n)
            if new: self.out(f"{Fore.LIGHTBLACK_EX}[!] external: {n}{Fore.RESET}")
            return False
        if is_file: return False
        is_api = bool(API_RE.search(p.path))
        with self._lk:
            new = n not in self.internal
            if new:
                self.internal.add(n)
                if is_api: self.apis.add(n)
        if new:
            if is_api:
                self.out(f"{Fore.CYAN}{Style.BRIGHT}[+] api: {n}{Style.RESET_ALL}")
            else:
                self.out(f"{Fore.GREEN}[*] internal: {n}{Fore.RESET}")
        return new

    def robots(self, base):
        u = urljoin(base, "/robots.txt")
        paths, sms = set(), set()
        try: r = self.s.get(u, timeout=10)
        except requests.exceptions.RequestException: return paths, sms
        if r.status_code != 200 or not r.text: return paths, sms
        self.out(f"{Fore.MAGENTA}[*] robots: {u}{Fore.RESET}")
        for line in r.text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line: continue
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            if not v: continue
            if k in ("disallow", "allow"):
                c = v.split("*")[0].split("$")[0]
                if not c: continue
                f = urljoin(base, c)
                if self.valid(f): paths.add(f)
            elif k == "sitemap":
                sms.add(v)
        return paths, sms

    def sitemap(self, u, seen=None, depth=0):
        if seen is None: seen = set()
        if u in seen or depth > 3: return set()
        seen.add(u)
        out = set()
        try: r = self.s.get(u, timeout=15)
        except requests.exceptions.RequestException: return out
        if r.status_code != 200 or not r.text: return out
        try: soup = BeautifulSoup(r.text, "xml")
        except Exception:
            try: soup = BeautifulSoup(r.text, "html.parser")
            except Exception: return out
        for sm in soup.find_all("sitemap"):
            loc = sm.find("loc")
            if loc and loc.text:
                out.update(self.sitemap(loc.text.strip(), seen, depth + 1))
        for el in soup.find_all("url"):
            loc = el.find("loc")
            if loc and loc.text:
                t = loc.text.strip()
                if self.valid(t): out.add(t)
        return out

    def probe(self, base, workers=20):
        out = set()
        self.out(f"{Fore.MAGENTA}[*] probing {len(PROBES)} paths on {base}{Fore.RESET}")
        def check(p):
            u = urljoin(base, p)
            try: r = self.s.head(u, timeout=5, allow_redirects=True)
            except requests.exceptions.RequestException: return None
            sc = r.status_code
            if sc < 400 or sc in (401, 403, 405): return u, sc
            return None
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for res in ex.map(check, PROBES):
                if not res: continue
                u, sc = res
                if sc < 400:
                    self.out(f"{Fore.GREEN}[+] hit ({sc}): {u}{Fore.RESET}")
                else:
                    self.out(f"{Fore.YELLOW}[?] protected ({sc}): {u}{Fore.RESET}")
                out.add(u)
        return out

    def js_scan(self, u, base):
        with self._lk:
            if u in self.js_seen: return set()
            self.js_seen.add(u)
        if LIB_JS.search(u): return set()
        try: r = self.s.get(u, timeout=15)
        except requests.exceptions.RequestException: return set()
        if r.status_code != 200 or not r.text: return set()
        text = r.text if len(r.text) <= 5_000_000 else r.text[:5_000_000]
        cands = self.paths_in(text, base)
        n = 0
        for p in cands:
            if self.record(p, base): n += 1
        if n: self.out(f"{Fore.CYAN}[*] js {u}: +{n}{Fore.RESET}")
        return cands

    def js_from_page(self, base, limit=30):
        try: r = self.s.get(base, timeout=10)
        except requests.exceptions.RequestException: return
        if r.status_code >= 400 or not r.text: return
        try: soup = BeautifulSoup(r.text, "html.parser")
        except Exception: return
        d = self.dom(base)
        js = []
        for s in soup.find_all("script", src=True):
            src = urljoin(base, s["src"])
            if not self.valid(src) or (d and d not in src) or LIB_JS.search(src): continue
            if src not in js: js.append(src)
            if len(js) >= limit: break
        if not js: return
        self.out(f"{Fore.CYAN}[*] scanning {len(js)} js file(s){Fore.RESET}")
        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(lambda x: self.js_scan(x, base), js))

    def discover(self, base, js=True, js_limit=30):
        if not urlparse(base).scheme: base = "https://" + base
        d = self.dom(base)
        if not d: return
        with self._lk:
            if d in self._done: return
            self._done.add(d)
        self.out(f"\n{Fore.CYAN}{Style.BRIGHT}[*] discover: {base}{Style.RESET_ALL}")
        rp, sms = self.robots(base)
        for p in rp: self.record(p, base)
        if not sms:
            sms = {urljoin(base, "/sitemap.xml"), urljoin(base, "/sitemap_index.xml")}
        smu = set()
        for sm in sms: smu.update(self.sitemap(sm))
        if smu: self.out(f"{Fore.MAGENTA}[+] sitemap: {len(smu)} url(s){Fore.RESET}")
        for u in smu: self.record(u, base)
        for u in self.probe(base): self.record(u, base)
        if js: self.js_from_page(base, limit=js_limit)

    def paths(self, url, hidden=True):
        out = set()
        try:
            r = self.s.get(url, timeout=10)
            r.encoding = self.enc(r)
            ct = r.headers.get('Content-Type', '').lower()
            try:
                soup = BeautifulSoup(r.text, 'lxml' if 'xml' in ct else 'html.parser')
            except Exception as e:
                self.out(f"{Fore.YELLOW}[!] parse: {url}: {e}{Fore.RESET}")
                return set()
            tags = [
                ('a', 'href', None, None), ('img', 'src', None, None),
                ('img', 'data-src', None, None), ('link', 'href', None, None),
                ('script', 'src', None, None), ('source', 'src', None, None),
                ('source', 'srcset', None, None), ('video', 'src', None, None),
                ('audio', 'src', None, None), ('iframe', 'src', None, None),
                ('form', 'action', None, None),
                ('meta', 'content', {'http-equiv': 'refresh'}, None),
                ('object', 'data', None, None), ('embed', 'src', None, None),
                ('applet', 'codebase', None, None),
                ('param', 'value', None, 'object > param[value]'),
                ('param', 'value', None, 'applet > param[value]'),
            ]
            for tag, attr, attrs, sel in tags:
                elems = soup.select(sel) if sel else soup.find_all(tag, **(attrs or {}))
                for e in elems:
                    if attr not in e.attrs: continue
                    raw = e[attr]
                    cands = [raw.split()[0]] if attr == 'srcset' and raw else [raw]
                    for c in cands:
                        p = urljoin(url, c)
                        out.add(p)
                        self.record(p, url)
            for sc in soup.find_all('script'):
                if sc.get('src'): continue
                body = sc.string or sc.get_text() or ''
                if body:
                    for p in self.paths_in(body, url):
                        self.record(p, url); out.add(p)
            for st in soup.find_all('style'):
                body = st.string or st.get_text() or ''
                if body:
                    for m in CSS_URL.findall(body):
                        f = urljoin(url, m); self.record(f, url); out.add(f)
            for el in soup.find_all(style=True):
                for m in CSS_URL.findall(el.get('style', '')):
                    f = urljoin(url, m); self.record(f, url); out.add(f)
            for cm in soup.find_all(string=lambda s: isinstance(s, Comment)):
                for p in self.paths_in(str(cm), url):
                    self.record(p, url); out.add(p)
            if hidden:
                for h in soup.find_all(attrs={"type": "hidden"}):
                    if 'formaction' in h.attrs:
                        hp = urljoin(url, h['formaction'])
                        with self._lk:
                            new = hp not in self.hidden
                            self.hidden.add(hp)
                        if new: self.out(f"{Fore.LIGHTBLACK_EX}[!] hidden: {hp}{Fore.RESET}")
                        out.add(hp)
                for h in soup.find_all('a', href=True, style=lambda s: s and 'display:none' in s.lower()):
                    hp = urljoin(url, h['href'])
                    with self._lk:
                        new = hp not in self.hidden
                        self.hidden.add(hp)
                    if new: self.out(f"{Fore.LIGHTBLACK_EX}[!] hidden: {hp}{Fore.RESET}")
                    out.add(hp)
            return out
        except requests.exceptions.ConnectionError:
            return set()
        except requests.exceptions.Timeout:
            self.out(f"{Fore.YELLOW}[!] timeout: {url}{Fore.RESET}")
            return set()
        except requests.exceptions.RequestException as e:
            self.out(f"{Fore.LIGHTBLACK_EX}[!] req: {url}: {e}{Fore.RESET}")
            return set()
        except Exception as e:
            self.out(f"{Fore.RED}[!] err: {url}: {e}{Fore.RESET}")
            return set()

    def walk(self, base, max_depth=5, hidden=True, max_urls=1000, do_discover=True):
        if not urlparse(base).scheme: base = "https://" + base
        if do_discover: self.discover(base)
        seen = set()
        q = deque([(base, 0)])
        dn = self.dom(base)
        with self._lk:
            seeds = [u for u in self.internal if dn and dn in u]
        for s in seeds: q.append((s, 1))
        n = 0
        while q and n < max_urls:
            url, depth = q.popleft()
            if url in seen or depth > max_depth: continue
            seen.add(url)
            if FILE_RE.search(url) or '/_next/image' in url or '/_next/static' in url:
                continue
            self.out(f"{Fore.YELLOW}[*] walk: {url}{Fore.RESET}")
            for p in self.paths(url, hidden):
                if p not in seen and self.valid(p) and dn in p:
                    q.append((p, depth + 1))
            n += 1

    def links(self, url):
        dn = self.dom(url)
        out = set()
        try:
            r = self.s.get(url, timeout=10)
            try:
                txt = r.content.decode(self.enc(r), errors='ignore')
            except (LookupError, TypeError) as e:
                self.out(f"{Fore.YELLOW}[!] decode: {url}: {e}{Fore.RESET}")
                with self._lk: self.bad.add(url)
                return out
            ct = r.headers.get('Content-Type', '').lower()
            try:
                soup = BeautifulSoup(txt, "lxml" if 'xml' in ct else "html.parser")
            except (FeatureNotFound, Exception) as e:
                self.out(f"{Fore.YELLOW}[!] parser: {url}: {e}{Fore.RESET}")
                with self._lk: self.files.add(url); self.bad.add(url)
                return out
            if r.status_code == 404:
                self.out(f"{Fore.RED}[!] 404: {url}{Fore.RESET}")
                with self._lk: self.bad.add(url)
                return out
        except requests.exceptions.RequestException:
            self.out(f"{Fore.LIGHTBLACK_EX}[!] conn: {url}{Fore.RESET}")
            with self._lk: self.bad.add(url)
            return out
        if FILE_RE.search(url):
            self.out(f"{Fore.LIGHTBLACK_EX}[!] file: {url}{Fore.RESET}")
            with self._lk: self.files.add(url)
            return out
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a.attrs.get("href"))
            p = urlparse(href)
            href = f"{p.scheme}://{p.netloc}{p.path}"
            if not self.valid(href): continue
            if dn and dn not in href:
                with self._lk:
                    new = href not in self.external
                    if new: self.external.add(href)
                if new: self.out(f"{Fore.LIGHTBLACK_EX}[!] external: {href}{Fore.RESET}")
            else:
                with self._lk:
                    new = href not in self.internal
                    if new:
                        self.internal.add(href)
                        out.add(href)
                if new: self.out(f"{Fore.GREEN}[*] internal: {href}{Fore.RESET}")
        return out

    def crawl(self, base, workers=10):
        q = Queue()
        q.put(base)
        with self._lk: self.internal.add(base)
        STOP = object()
        stop = threading.Event()

        def w():
            while True:
                url = q.get()
                try:
                    if url is STOP or stop.is_set(): return
                    with self._lk: dead = url in self.bad
                    if dead: continue
                    self.out(f"{Fore.YELLOW}[*] crawl: {url}{Fore.RESET}")
                    for link in self.links(url):
                        with self._lk: dead = link in self.bad
                        if not dead: q.put(link)
                finally:
                    q.task_done()

        ts = [threading.Thread(target=w, daemon=True) for _ in range(workers)]
        for t in ts: t.start()
        try:
            q.join()
        except KeyboardInterrupt:
            self.out(f"{Fore.RED}[!] interrupted{Fore.RESET}")
            stop.set()
        for _ in range(workers): q.put(STOP)
        for t in ts: t.join(timeout=5)

    def brute(self, d, workers=50):
        out = []
        self.out(f"{Fore.YELLOW}[*] brute (dns): {d}{Fore.RESET}")
        p = urlparse(d if "://" in d else "http://" + d)
        base = (p.netloc or p.path).strip("/").lower()
        if not base:
            self.out(f"{Fore.RED}[!] bad domain: {d!r}{Fore.RESET}")
            return out
        wc = self.wildcard(base)
        n = len(self.subs)
        done = [0]
        lk = threading.Lock()
        def check(s):
            h = f"{s}.{base}"
            ip = self.resolve(h)
            with lk:
                done[0] += 1; i = done[0]
            if ip and ip not in wc:
                self.out(f"{Fore.GREEN}[+] ({i}/{n}) {h} -> {ip}{Fore.RESET}")
                return h
            return None
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for f in as_completed([ex.submit(check, s) for s in self.subs]):
                try: r = f.result()
                except Exception: r = None
                if r: out.append(r)
        self.out(f"{Fore.GREEN}[*] brute done: {len(out)} found{Fore.RESET}")
        return sorted(set(out))

    def crtsh(self, d):
        try:
            r = self.s.get(f"https://crt.sh/?q=%25.{d}&output=json", timeout=15)
            r.raise_for_status()
            res = r.json()
        except Exception:
            return []
        out = set()
        for x in res:
            for n in x.get('name_value', '').split('\n'):
                out.add(n.strip())
        return list(out)

    def hkr(self, d):
        try:
            r = self.s.get(f"https://api.hackertarget.com/hostsearch/?q={d}", timeout=15)
            r.raise_for_status()
            t = r.text or ""
        except Exception:
            return []
        if t.lower().startswith("error") or "API count exceeded" in t:
            return []
        out = set()
        for line in t.splitlines():
            h = line.split(",", 1)[0].strip().lower()
            if h: out.add(h)
        return list(out)

    def vt(self, d):
        key = 'api key here'
        if not key or key == 'key': return []
        try:
            j = self.s.get(
                f'https://www.virustotal.com/vtapi/v2/domain/report?apikey={key}&domain={d}',
                timeout=15
            ).json()
            return list(set(j.get('subdomains', [])))
        except Exception:
            return []

    def otx(self, d):
        try:
            r = self.s.get(
                f"https://otx.alienvault.com/api/v1/indicators/domain/{d}/passive_dns",
                headers={'Content-Type': 'application/json'}, timeout=15
            )
            r.raise_for_status()
            j = r.json()
        except Exception:
            return []
        out = set()
        for x in j.get('passive_dns', []):
            h = (x.get('hostname') or '').strip()
            if h: out.add(h)
        return list(out)

    def urlscan(self, d):
        try:
            r = self.s.get(f"https://urlscan.io/api/v1/search/?q=domain:{d}", timeout=15)
            r.raise_for_status()
            j = r.json()
        except Exception:
            return []
        out = set()
        for res in j.get('results', []):
            for k in ('task', 'page'):
                u = res.get(k, {}).get('url', '')
                if not u: continue
                try:
                    h = urlparse(u).hostname
                    if h: out.add(h)
                except Exception:
                    pass
        return list(out)

    def wb(self, d):
        try:
            r = self.s.get(
                f"http://web.archive.org/cdx/search/cdx?url=*.{d}/*&output=json&collapse=urlkey",
                timeout=20
            )
            r.raise_for_status()
            j = r.json()
        except Exception:
            return []
        out = set()
        skip = True
        for x in j:
            if skip: skip = False; continue
            if len(x) < 3: continue
            try:
                h = urlparse(x[2]).hostname
                if h: out.add(h)
            except Exception:
                continue
        return list(out)

    def find_subs(self, d):
        out = []
        skip = {"www", ""}
        srcs = [("crt.sh", self.crtsh), ("hackertarget", self.hkr), ("otx", self.otx),
                ("urlscan", self.urlscan), ("wayback", self.wb)]
        self.out(f"{Fore.YELLOW}[*] passive: {len(srcs)} src for {d}{Fore.RESET}")
        results = []
        with ThreadPoolExecutor(max_workers=len(srcs)) as ex:
            futs = {ex.submit(fn, d): name for name, fn in srcs}
            for f in as_completed(futs):
                name = futs[f]
                try:
                    res = f.result() or []
                    self.out(f"{Fore.LIGHTBLACK_EX}[*] {name}: {len(res)}{Fore.RESET}")
                    results.append(res)
                except Exception as e:
                    self.out(f"{Fore.YELLOW}[!] {name}: {e}{Fore.RESET}")
        seen = set()
        for lst in results:
            for raw in lst:
                s = raw.strip(".").strip().lower()
                if s.startswith("*."): s = s[2:]
                if s.endswith("." + d):
                    pref = s[:-(len(d) + 1)]
                elif s == d:
                    pref = ""
                else:
                    continue
                if pref in skip or s in seen or not self.is_sub(d, s): continue
                seen.add(s)
                self.out(f"{Fore.GREEN}[+] {s}{Fore.RESET}")
                out.append(s)
        return sorted(out)

    def summary(self):
        ln = "=" * 62
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{ln}\n  SUMMARY\n{ln}{Style.RESET_ALL}")
        print(f"  {Fore.GREEN}internal : {len(self.internal)}")
        print(f"  {Fore.CYAN}apis     : {len(self.apis)}")
        print(f"  {Fore.LIGHTBLACK_EX}external : {len(self.external)}")
        print(f"  {Fore.MAGENTA}hidden   : {len(self.hidden)}")
        print(f"  {Fore.LIGHTBLACK_EX}files    : {len(self.files)}")
        print(f"  {Fore.LIGHTBLACK_EX}js seen  : {len(self.js_seen)}")
        print(f"{Fore.CYAN}{Style.BRIGHT}{ln}{Style.RESET_ALL}")

    def save(self, subs, kind, path="found_urls.txt"):
        with open(path, "w", encoding="utf-8") as f:
            def sec(title, items):
                if not items: return
                f.write(f"\n{title}\n" + "-" * 62 + "\n")
                for i in sorted(items): f.write(f"{i}\n")
                f.write("-" * 62 + "\n")
            sec("API Endpoints:", self.apis)
            sec("Internal URLs:", self.internal)
            sec("External URLs:", self.external)
            sec("Hidden URLs:", self.hidden)
            if subs: sec(f"Subdomains ({kind}):", subs)
            sec("Files:", self.files)
        print(f"{Fore.GREEN}[*] saved -> {path}{Fore.RESET}")

    def ask(self, prompt, choices=None, default=None):
        while True:
            try:
                v = input(prompt).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print(); sys.exit(0)
            if not v and default is not None: return default
            if choices is None or v in choices: return v
            print(f"{Fore.YELLOW}[!] pick: {', '.join(choices)}{Fore.RESET}")

    def run(self):
        try:
            raw = input('url: ').strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not raw:
            print(f"{Fore.RED}[!] no url{Fore.RESET}"); return self.wait()
        url = self.norm(raw)
        d = self.dom(url)
        if not d:
            print(f"{Fore.RED}[!] bad url: {raw!r}{Fore.RESET}"); return self.wait()
        ext = self.ask('extract subdomains? [y/n] (n): ', {'y','n','yes','no',''}, 'n')
        do_crawl = self.ask('crawl? [y/n] (y): ', {'y','n','yes','no',''}, 'y')
        method = ''
        if ext in ('y', 'yes'):
            method = self.ask('method [bruteforce/finder] (finder): ',
                              {'bruteforce','b','finder','f',''}, 'finder')
        subs, kind = [], None
        try:
            if do_crawl in ('y', 'yes'):
                start = url if url.startswith(('http://', 'https://')) else 'https://' + url
                self.crawl(start, workers=10)
                self.walk(d)
            if ext in ('y', 'yes'):
                if method in ('bruteforce', 'b'):
                    subs, kind = self.brute(d), "bruteforced"
                else:
                    subs, kind = self.find_subs(d), "dumped"
                for s in subs:
                    print(f"\n{Fore.GREEN}[*] sub: {s}{Fore.RESET}")
                    cs = s if s.startswith(('http://', 'https://')) else 'https://' + s
                    self.crawl(cs, workers=10)
                    self.walk(cs)
        except KeyboardInterrupt:
            print(f"\n{Fore.RED}[!] interrupted, saving partial{Fore.RESET}")
        self.save(subs, kind)
        self.summary()
        self.wait()

    def wait(self):
        try: input(f"\n{Fore.CYAN}done. press ENTER to exit...{Fore.RESET}")
        except (EOFError, KeyboardInterrupt): pass

if __name__ == "__main__":
    try:
        urlcrawler().run()
    except KeyboardInterrupt:
        print(f"\n{Fore.RED}[!] bye{Fore.RESET}")
