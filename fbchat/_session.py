import attr
import datetime
import aiohttp
import random
import re
import json
import os
import time
import errno
import string
import urllib.request
from yarl import URL
from http.cookies import SimpleCookie, BaseCookie

# TODO: Only import when required
# Or maybe just replace usage with `html.parser`?
import bs4

from ._common import log, kw_only
from . import _graphql, _util, _exception

from typing import Optional, Mapping, Callable, Any, Awaitable, Dict, List, NamedTuple

try:
    from aiohttp_socks import ProxyType, ProxyConnector
except ImportError:
    ProxyType = None
    ProxyConnector = None

SERVER_JS_DEFINE_REGEX = re.compile(r'(?:'
                                    r'\(new ServerJS\(\)\)(?:;s)?'
                                    r'|\(require\("ServerJS(?:Define)?"\)\)\(\)'
                                    r').handle(?:Defines|WithCustomApplyEach)?\('
                                    r'(?:ScheduledApplyEach,)?')
SERVER_JS_DEFINE_JSON_DECODER = json.JSONDecoder()


def write_html_to_temp(html: str) -> str:
    random_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    file_path = f"/tmp/fbchat-debug/serverjsdefine-{int(time.time())}-{random_id}"
    try:
        os.makedirs(os.path.dirname(file_path))
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
    with open(file_path, "w") as file:
        file.write(html)
    return file_path


def parse_server_js_define(html: str) -> Mapping[str, Any]:
    """Parse ``ServerJSDefine`` entries from a HTML document."""
    # Find points where we should start parsing
    define_splits = SERVER_JS_DEFINE_REGEX.split(html)

    # TODO: Extract jsmods "require" and "define" from `bigPipe.onPageletArrive`?

    # Skip leading entry
    _, *define_splits = define_splits

    if not define_splits:
        file_name = write_html_to_temp(html)
        raise _exception.ParseError("Could not find any ServerJSDefine", data_file=file_name)
    # if len(define_splits) > 2:
    #     file_name = write_html_to_temp(html)
    #     raise _exception.ParseError("Found too many ServerJSDefine", data_file=file_name)
    try:
        parsed, _ = SERVER_JS_DEFINE_JSON_DECODER.raw_decode(define_splits[0], idx=0)
    except json.JSONDecodeError as e:
        file_name = write_html_to_temp(html)
        raise _exception.ParseError("Invalid ServerJSDefine: not json", data_file=file_name) from e
    try:
        rtn = parsed["define"]
    except KeyError:
        file_name = write_html_to_temp(html)
        raise _exception.ParseError("Invalid ServerJSDefine: missing define key",
                                    data_file=file_name)

    if not isinstance(rtn, list):
        file_name = write_html_to_temp(html)
        raise _exception.ParseError("Invalid ServerJSDefine: define value is not a list",
                                    data_file=file_name)

    # Convert to a dict
    return _util.get_jsmods_define(rtn)


def parse_kv(vals: List[str]) -> Dict[str, str]:
    kv = {}
    for val in vals:
        split = val.strip().split("=", 1)
        if len(split) == 1:
            kv[split[0]] = True
        else:
            kv[split[0]] = split[1]
    return kv


class AltSvc(NamedTuple):
    alt_authority: str
    max_age: int
    persist: bool
    extra_meta: Dict[str, str]


def parse_alt_svc(r: aiohttp.ClientResponse) -> Dict[str, AltSvc]:
    try:
        header = r.headers["Alt-Svc"]
    except KeyError:
        return {}
    if header.lower() == "clear":
        return {}
    services = {}
    for service in header.split(","):
        vals = service.split(";")
        try:
            protocol_id, alt_authority = vals[0].split("=")
        except ValueError:
            continue
        alt_authority: str = alt_authority.strip('"')
        kv = parse_kv(vals[1:])
        try:
            max_age = int(kv.pop("max_age"))
        except (KeyError, ValueError):
            max_age = 86400
        try:
            persist = kv.pop("persist") == "1"
        except KeyError:
            persist = False
        services[protocol_id] = AltSvc(alt_authority, max_age, persist, extra_meta=kv)
    return services


def base36encode(number: int) -> str:
    """Convert from Base10 to Base36."""
    # Taken from https://en.wikipedia.org/wiki/Base36#Python_implementation
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"

    sign = "-" if number < 0 else ""
    number = abs(number)
    result = ""

    while number > 0:
        number, remainder = divmod(number, 36)
        result = chars[remainder] + result

    return sign + result


def generate_message_id(now: datetime.datetime, client_id: str) -> str:
    k = _util.datetime_to_millis(now)
    l = int(random.random() * 4294967295)
    return "<{}:{}-{}@mail.projektitan.com>".format(k, l, client_id)


def get_user_id(domain: str, session: aiohttp.ClientSession) -> str:
    try:
        rtn = session.cookie_jar.filter_cookies(URL(f"https://{domain}")).get("c_user")
    except (AttributeError, KeyError):
        raise _exception.ParseError("Could not find user id", data=session.cookie_jar._cookies)
    if rtn is None:
        raise _exception.ParseError("Could not find user id", data=session.cookie_jar._cookies)
    return rtn if isinstance(rtn, str) else str(rtn.value)


def session_factory(domain: str, user_agent: Optional[str] = None) -> aiohttp.ClientSession:
    from . import __version__
    try:
        http_proxy = urllib.request.getproxies()["http"]
    except KeyError:
        http_proxy = None
    return aiohttp.ClientSession(connector=(ProxyConnector.from_url(http_proxy)
                                            if ProxyConnector and http_proxy
                                            else None),
                                 headers={
                                     "Referer": f"https://www.{domain}/",
                                     "User-Agent": user_agent or f"fbchat-asyncio/{__version__}",
                                 })


def login_cookies(at: datetime.datetime):
    return {"act": "{}/0".format(_util.datetime_to_millis(at))}


def client_id_factory() -> str:
    return hex(int(random.random() * 2 ** 31))[2:]


def find_form_request(html: str):
    soup = bs4.BeautifulSoup(html, "html.parser", parse_only=bs4.SoupStrainer("form"))

    form = soup.form
    if not form:
        raise _exception.ParseError("Could not find form to submit", data=html)

    url = form.get("action")
    if not url:
        raise _exception.ParseError("Could not find url to submit to", data=form)

    # From what I've seen, it'll always do this!
    if url.startswith("/"):
        url = "https://www.facebook.com" + url

    # It's okay to set missing values to something crap, the values are localized, and
    # hence are not available in the raw HTML
    data = {
        x["name"]: x.get("value", "[missing]")
        for x in form.find_all(["input", "button"])
    }
    return url, data


async def two_factor_helper(session: aiohttp.ClientSession, r: aiohttp.ClientResponse,
                            on_2fa_callback: Callable[[], Awaitable[int]]) -> str:
    url, data = find_form_request(await r.text())

    # You don't have to type a code if your device is already saved
    # Repeats if you get the code wrong
    while "approvals_code" in data:
        data["approvals_code"] = await on_2fa_callback()
        log.info("Submitting 2FA code")
        r = await session.post(url, data=data, allow_redirects=False,
                               cookies=login_cookies(_util.now()))
        log.debug("2FA location: %s", r.headers.get("Location"))
        url, data = find_form_request(await r.text())

    # TODO: Can be missing if checkup flow was done on another device in the meantime?
    if "name_action_selected" in data:
        data["name_action_selected"] = "save_device"
        log.info("Saving browser")
        r = await session.post(url, data=data, allow_redirects=False,
                               cookies=login_cookies(_util.now()))
        log.debug("2FA location: %s", r.headers.get("Location"))
        url = r.headers.get("Location")
        if url and url.startswith("https://www.messenger.com/login/auth_token/"):
            return url
        url, data = find_form_request(await r.text())

    log.info("Starting Facebook checkup flow")
    r = await session.post(url, data=data, allow_redirects=False,
                           cookies=login_cookies(_util.now()))
    log.debug("2FA location: %s", r.headers.get("Location"))

    url, data = find_form_request(await r.text())
    if "verification_method" in data:
        raise _exception.NotLoggedIn(
            "Your account is locked, and you need to log in using a browser, and verify it there!"
        )
    if "submit[This was me]" not in data or "submit[This wasn't me]" not in data:
        raise _exception.ParseError("Could not fill out form properly (2)", data=data)
    data["submit[This was me]"] = "[any value]"
    del data["submit[This wasn't me]"]
    log.info("Verifying login attempt")

    r = await session.post(url, data=data, allow_redirects=False,
                           cookies=login_cookies(_util.now()))
    log.debug("2FA location: %s", r.headers.get("Location"))

    url, data = find_form_request(await r.text())
    if "name_action_selected" not in data:
        raise _exception.ParseError("Could not fill out form properly (3)", data=data)
    data["name_action_selected"] = "save_device"
    log.info("Saving device again")

    r = await session.post(url, data=data, allow_redirects=False,
                           cookies=login_cookies(_util.now()))
    log.debug("2FA location: %s", r.headers.get("Location"))
    return r.headers.get("Location")


def get_error_data(html: str) -> Optional[str]:
    """Get error message from a request."""
    soup = bs4.BeautifulSoup(
        html, "html.parser", parse_only=bs4.SoupStrainer("form", id="login_form")
    )
    # Attempt to extract and format the error string
    # The error message is in the user's own language!
    return " ".join(list(soup.stripped_strings)[1:3]) or None


def get_fb_dtsg(define) -> Optional[str]:
    if "DTSGInitData" in define:
        return define["DTSGInitData"]["token"]
    elif "DTSGInitialData" in define:
        return define["DTSGInitialData"]["token"]
    elif "MRequestConfig" in define and "dtsg" in define["MRequestConfig"]:
        return define["MRequestConfig"]["dtsg"]["token"]
    return None


def prefix_url(domain: str, path: str) -> URL:
    if path.startswith("/"):
        return URL(f"https://www.{domain}" + path)
    return URL(path)


@attr.s(slots=True, kw_only=kw_only, repr=False, eq=False, auto_attribs=True)
class Session:
    """Stores and manages state required for most Facebook requests.

    This is the main class, which is used to login to Facebook.
    """

    _user_id: str
    _fb_dtsg: str
    _revision: int
    domain: str
    _onion: Optional[str] = None
    _session: aiohttp.ClientSession = attr.ib(factory=session_factory)
    _counter: int = 0
    _client_id: str = attr.ib(factory=client_id_factory)

    def _prefix_url(self, path: str) -> URL:
        return prefix_url(self.domain, path)

    @property
    def user(self):
        """The logged in user."""
        from . import _threads

        # TODO: Consider caching the result

        return _threads.User(session=self, id=self._user_id)

    def __repr__(self) -> str:
        # An alternative repr, to illustrate that you can't create the class directly
        return "<fbchat.Session user_id={}>".format(self._user_id)

    def _get_params(self):
        self._counter += 1
        return {
            "__a": 1,
            "__req": base36encode(self._counter),
            "__rev": self._revision,
            "fb_dtsg": self._fb_dtsg,
        }

    @classmethod
    async def login(cls, email: str, password: str,
                    on_2fa_callback: Callable[[], Awaitable[int]] = None,
                    user_agent: Optional[str] = None) -> 'Session':
        """Login the user, using ``email`` and ``password``.

        Args:
            email: Facebook ``email``, ``id`` or ``phone number``
            password: Facebook account password
            on_2fa_callback: Function that will be called, in case a two factor
                authentication code is needed. This should return the requested code.

                Tested using SMS and authentication applications. If you have both
                enabled, you might not receive an SMS code, and you'll have to use the
                authentication application.

                Note: Facebook limits the amount of codes they will give you, so if you
                don't receive a code, be patient, and try again later!
            user_agent: The user agent to send to Facebook

        Example:
            >>> import fbchat
            >>> import getpass
            >>> session = fbchat.Session.login(
            ...     input("Email: "),
            ...     getpass.getpass(),
            ...     on_2fa_callback=lambda: input("2FA Code: ")
            ... )
            Email: abc@gmail.com
            Password: ****
            2FA Code: 123456
            >>> session.user.id
            "1234"
        """
        session = session_factory(domain="messenger.com", user_agent=user_agent)

        data = {
            # "jazoest": "2754",
            # "lsd": "AVqqqRUa",
            "initial_request_id": "x",  # any, just has to be present
            # "timezone": "-120",
            # "lgndim": "eyJ3IjoxNDQwLCJoIjo5MDAsImF3IjoxNDQwLCJhaCI6ODc3LCJjIjoyNH0=",
            # "lgnrnd": "044039_RGm9",
            "lgnjs": "n",
            "email": email,
            "pass": password,
            "login": "1",
            "persistent": "1",  # Changes the cookie type to have a long "expires"
            "default_persistent": "0",
        }

        try:
            # Should hit a redirect to https://www.messenger.com/
            # If this does happen, the session is logged in!
            r = await session.post(
                "https://www.messenger.com/login/password/",
                data=data,
                allow_redirects=False,
                cookies=login_cookies(_util.now()),
            )
        except aiohttp.ClientError as e:
            _exception.handle_requests_error(e)
            raise Exception("handle_requests_error did not raise exception")
        _exception.handle_http_error(r.status)

        url = r.headers.get("Location")

        # We weren't redirected, hence the email or password was wrong
        if not url:
            error = get_error_data(await r.text())
            raise _exception.NotLoggedIn(error)

        if "checkpoint" in url:
            if not on_2fa_callback:
                raise _exception.NotLoggedIn(
                    "2FA code required! Please supply `on_2fa_callback` to .login"
                )
            # Get a facebook.com/checkpoint/start url that handles the 2FA flow
            # This probably works differently for Messenger-only accounts
            url = _util.get_url_parameter(url, "next")
            if not url.startswith("https://www.facebook.com/checkpoint/start/"):
                raise _exception.ParseError("Failed 2fa flow (1)", data=url)

            r = await session.get(url, allow_redirects=False, cookies=login_cookies(_util.now()))
            url = r.headers.get("Location")
            if not url or not url.startswith("https://www.facebook.com/checkpoint/"):
                raise _exception.ParseError("Failed 2fa flow (2)", data=url)

            r = await session.get(url, allow_redirects=False, cookies=login_cookies(_util.now()))
            url = await two_factor_helper(session, r, on_2fa_callback)

            if not url.startswith("https://www.messenger.com/login/auth_token/"):
                raise _exception.ParseError("Failed 2fa flow (3)", data=url)

            r = await session.get(url, allow_redirects=False, cookies=login_cookies(_util.now()))
            url = r.headers.get("Location")

        if url != "https://www.messenger.com/":
            error = get_error_data(await r.text())
            raise _exception.NotLoggedIn("Failed logging in: {}, {}".format(url, error))

        try:
            return await cls._from_session(session=session, domain="messenger.com")
        except _exception.NotLoggedIn as e:
            raise _exception.ParseError("Failed loading session", data=r) from e

    async def is_logged_in(self) -> bool:
        """Send a request to Facebook to check the login status.

        Returns:
            Whether the user is still logged in

        Example:
            >>> assert session.is_logged_in()
        """
        # Send a request to the login url, to see if we're directed to the home page
        try:
            r = await self._session.get(self._prefix_url("/login/"), allow_redirects=False)
        except aiohttp.ClientError as e:
            _exception.handle_requests_error(e)
            raise Exception("handle_requests_error did not raise exception")
        _exception.handle_http_error(r.status)
        location = r.headers.get("Location")
        return location in (f"https://www.{self.domain}/",
                            # We include this as a "logged in" status, since the user is logged in,
                            # but needs to verify the session elsewhere
                            f"https://www.{self.domain}/checkpoint/block/")

    async def logout(self) -> None:
        """Safely log out the user.

        The session object must not be used after this action has been performed!

        Example:
            >>> session.logout()
        """
        if self.domain != "messenger.com":
            log.warning("session.logout() is only supported on messenger.com")
            return
        data = {"fb_dtsg": self._fb_dtsg}
        try:
            r = await self._session.post(
                self._prefix_url("/logout/"), data=data, allow_redirects=False
            )
        except aiohttp.ClientError as e:
            _exception.handle_requests_error(e)
            raise Exception("handle_requests_error did not raise exception")
        _exception.handle_http_error(r.status)

        if "Location" not in r.headers:
            raise _exception.FacebookError("Failed logging out, was not redirected!")
        if "https://www.messenger.com/login/" != r.headers["Location"]:
            raise _exception.FacebookError(
                "Failed logging out, got bad redirect: {}".format(r.headers["Location"])
            )

    @classmethod
    async def _from_session(cls, session: aiohttp.ClientSession, domain: str
                            ) -> Optional['Session']:
        # TODO: Automatically set user_id when the cookie changes in the session
        user_id = get_user_id(domain, session)

        # Make a request to the main page to retrieve ServerJSDefine entries
        try:
            r = await session.get(prefix_url(domain, "/"), allow_redirects=False, headers={
                "Accept": "text/html",
            })
        except aiohttp.ClientError as e:
            _exception.handle_requests_error(e)
            raise Exception("handle_requests_error did not raise exception")
        _exception.handle_http_error(r.status)

        html = await r.text()
        if len(html) == 0:
            raise _exception.FacebookError("Got empty response when trying to check login")

        define = parse_server_js_define(html)

        fb_dtsg = get_fb_dtsg(define)
        if fb_dtsg is None:
            raise _exception.ParseError("Could not find fb_dtsg", data=define)
        if not fb_dtsg:
            # Happens when the client is not actually logged in
            raise _exception.NotLoggedIn(
                "Found empty fb_dtsg, the session was probably invalid."
            )
        try:
            revision = int(define["SiteData"]["client_revision"])
        except TypeError:
            raise _exception.ParseError("Could not find client revision", data=define)
        onion = None
        alt_svc_data = parse_alt_svc(r)
        if "h2" in alt_svc_data and alt_svc_data["h2"].alt_authority.endswith(".onion:443"):
            # TODO remember expiry too?
            onion = alt_svc_data["h2"].alt_authority
            log.info("Got onion alt-svc %s", onion)

        return cls(user_id=user_id, fb_dtsg=fb_dtsg, revision=revision, session=session,
                   domain=domain, onion=onion)

    def get_cookies(self) -> Optional[Mapping[str, str]]:
        """Retrieve session cookies, that can later be used in `from_cookies`.

        Returns:
            A dictionary containing session cookies

        Example:
            >>> cookies = session.get_cookies()
        """
        cookie = self._session.cookie_jar.filter_cookies(URL(f"https://{self.domain}"))
        return {key: morsel.value for key, morsel in cookie.items()}

    @classmethod
    async def from_cookies(cls, cookies: Mapping[str, str], user_agent: Optional[str] = None,
                           domain: str = "messenger.com") -> 'Session':
        """Load a session from session cookies.

        Args:
            cookies: A dictionary containing session cookies

        Example:
            >>> cookies = session.get_cookies()
            >>> # Store cookies somewhere, and then subsequently
            >>> session = fbchat.Session.from_cookies(cookies)
        """
        session = session_factory(domain=domain, user_agent=user_agent)

        if isinstance(cookies, BaseCookie):
            cookie = cookies
        else:
            cookie = SimpleCookie()
            for key, value in cookies.items():
                cookie[key] = value
                cookie[key].update({"domain": domain, "path": "/"})
        session.cookie_jar.update_cookies(cookie, URL(f"https://{domain}"))

        return await cls._from_session(session=session, domain=domain)

    async def _post(self, url, data, files=None, as_graphql=False):
        data.update(self._get_params())
        if files:
            payload = aiohttp.FormData()
            for key, value in data.items():
                payload.add_field(key, str(value))
            for key, (name, file, content_type) in files.items():
                payload.add_field(key, file, filename=name, content_type=content_type)
            data = payload
        real_url = self._prefix_url(url)
        kwargs = {}
        if self._onion:
            # TODO is there some way to change the host aiohttp connects to without changing the
            #      domain it uses for TLS, cookies and the Host header?
            kwargs["ssl"] = False
            kwargs["headers"] = {"Host": real_url.host}
            kwargs["cookies"] = self._session.cookie_jar.filter_cookies(real_url)
            real_url = real_url.with_host(real_url.host.replace(self.domain, self._onion))
        try:
            r = await self._session.post(real_url, data=data, **kwargs)
        except aiohttp.ClientError as e:
            _exception.handle_requests_error(e)
            raise Exception("handle_requests_error did not raise exception")
        _exception.handle_http_error(r.status)
        text = await r.text()
        if text is None or len(text) == 0:
            raise _exception.HTTPError("Error when sending request: Got empty response")
        if as_graphql:
            return _graphql.response_to_json(text)
        else:
            text = _util.strip_json_cruft(text)
            j = _util.parse_json(text)
            log.debug(j)
            return j

    async def _payload_post(self, url, data, files=None):
        j = await self._post(url, data, files=files)
        _exception.handle_payload_error(j)

        # update fb_dtsg token if received in response
        if "jsmods" in j:
            define = _util.get_jsmods_define(j["jsmods"]["define"])
            fb_dtsg = get_fb_dtsg(define)
            if fb_dtsg:
                self._fb_dtsg = fb_dtsg

        try:
            return j["payload"]
        except (KeyError, TypeError) as e:
            raise _exception.ParseError("Missing payload", data=j) from e

    async def _graphql_requests(self, *queries):
        # TODO: Explain usage of GraphQL, probably in the docs
        # Perhaps provide this API as public?
        data = {
            "method": "GET",
            "response_format": "json",
            "queries": _graphql.queries_to_json(*queries),
        }
        return await self._post("/api/graphqlbatch/", data, as_graphql=True)

    async def _do_send_request(self, data):
        now = _util.now()
        offline_threading_id = _util.generate_offline_threading_id()
        data["client"] = "mercury"
        data["author"] = "fbid:{}".format(self._user_id)
        data["timestamp"] = _util.datetime_to_millis(now)
        data["source"] = "source:chat:web"
        data["offline_threading_id"] = offline_threading_id
        data["message_id"] = offline_threading_id
        data["threading_id"] = generate_message_id(now, self._client_id)
        data["ephemeral_ttl_mode:"] = "0"
        j = await self._post("/messaging/send/", data)

        _exception.handle_payload_error(j)

        try:
            message_ids = [
                (action["message_id"], action["thread_fbid"])
                for action in j["payload"]["actions"]
                if "message_id" in action
            ]
            if len(message_ids) != 1:
                log.warning("Got multiple message ids' back: {}".format(message_ids))
            return message_ids[0]
        except (KeyError, IndexError, TypeError) as e:
            raise _exception.ParseError("No message IDs could be found", data=j) from e
