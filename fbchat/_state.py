import attr
import bs4
import re
import random
import asyncio
import aiohttp
from yarl import URL

from . import _graphql, _util, _exception

FB_DTSG_REGEX = re.compile(r'name="fb_dtsg" value="(.*?)"')


def get_user_id(session):
    try:
        rtn = session.cookie_jar._cookies["facebook.com"].get("c_user")
    except (AttributeError, KeyError):
        raise _exception.FBchatException("Could not find user id")
    if rtn is None:
        raise _exception.FBchatException("Could not find user id")
    return str(rtn.value)


def find_input_fields(html):
    return bs4.BeautifulSoup(html, "html.parser", parse_only=bs4.SoupStrainer("input"))


def session_factory(loop=None, user_agent=None):
    return aiohttp.ClientSession(loop=loop or asyncio.get_event_loop(), headers={
        "User-Agent": user_agent or random.choice(_util.USER_AGENTS),
        "Referer": "https://www.facebook.com",
        "Origin": "https://www.facebook.com",
    })


def client_id_factory():
    return hex(int(random.random() * 2 ** 31))[2:]


def is_home(url):
    path = URL(url).path
    # Check the urls `/home.php` and `/`
    return "home" in path or "/" == path


async def _2fa_helper(session, code, resp, log):
    soup = find_input_fields(await resp.text())
    data = dict()

    url = "https://m.facebook.com/login/checkpoint/"

    data["approvals_code"] = code
    data["fb_dtsg"] = soup.find("input", {"name": "fb_dtsg"})["value"]
    data["nh"] = soup.find("input", {"name": "nh"})["value"]
    data["submit[Submit Code]"] = "Submit Code"
    data["codes_submitted"] = 0
    log.info("Submitting 2FA code.")

    resp = await session.post(url, data=data)

    if is_home(resp.url):
        return resp

    del data["approvals_code"]
    del data["submit[Submit Code]"]
    del data["codes_submitted"]

    data["name_action_selected"] = "save_device"
    data["submit[Continue]"] = "Continue"
    log.info("Saving browser.")
    # At this stage, we have dtsg, nh, name_action_selected, submit[Continue]
    resp = await session.post(url, data=data)

    if is_home(resp.url):
        return resp

    del data["name_action_selected"]
    log.info("Starting Facebook checkup flow.")
    # At this stage, we have dtsg, nh, submit[Continue]
    resp = await session.post(url, data=data)

    if is_home(resp.url):
        return resp

    del data["submit[Continue]"]
    data["submit[This was me]"] = "This Was Me"
    log.info("Verifying login attempt.")
    # At this stage, we have dtsg, nh, submit[This was me]
    resp = await session.post(url, data=data)

    if is_home(resp.url):
        return resp

    del data["submit[This was me]"]
    data["submit[Continue]"] = "Continue"
    data["name_action_selected"] = "save_device"
    log.info("Saving device again.")
    # At this stage, we have dtsg, nh, submit[Continue], name_action_selected
    resp = await session.post(url, data=data)
    return resp


@attr.s(slots=True)  # TODO i Python 3: Add kw_only=True
class State:
    """Stores and manages state required for most Facebook requests."""

    user_id = attr.ib()
    _fb_dtsg = attr.ib()
    _revision = attr.ib()
    _session: aiohttp.ClientSession = attr.ib()
    _client_id = attr.ib(factory=client_id_factory)
    _counter = attr.ib(default=0)
    _logout_h = attr.ib(default=None)

    def get_params(self):
        self._counter += 1
        return {
            "__a": 1,
            "__req": _util.str_base(self._counter, 36),
            "__rev": self._revision,
            "fb_dtsg": self._fb_dtsg,
        }

    @classmethod
    async def login(cls, email, password, on_2fa_callback, user_agent=None, loop=None, log=None):
        session = session_factory(loop, user_agent)

        resp = await session.get("https://m.facebook.com/")
        soup = find_input_fields(await resp.text())
        data = dict(
            (elem["name"], elem["value"])
            for elem in soup
            if elem.has_attr("value") and elem.has_attr("name")
        )
        data["email"] = email
        data["pass"] = password
        data["login"] = "Log In"

        resp = await session.post("https://m.facebook.com/login.php?login_attempt=1", data=data)
        text = await resp.text()

        # Usually, 'Checkpoint' will refer to 2FA
        if "checkpoint" in resp.url.path and ('id="approvals_code"' in text.lower()):
            code = await on_2fa_callback()
            resp = await _2fa_helper(session, code, resp, log)

        # Sometimes Facebook tries to show the user a "Save Device" dialog
        if "save-device" in resp.url.path:
            resp = await session.get("https://m.facebook.com/login/save-device/cancel/")

        if is_home(resp.url):
            return await cls.from_session(session=session)
        else:
            raise _exception.FBchatException(
                "Login failed. Check email/password. "
                "(Failed on url: {})".format(resp.url)
            )

    async def is_logged_in(self):
        # Send a request to the login url, to see if we're directed to the home page
        url = "https://m.facebook.com/login.php?login_attempt=1"
        resp = await self._session.get(url, allow_redirects=False)
        return "Location" in resp.headers and is_home(resp.headers["Location"])

    async def logout(self):
        logout_h = self._logout_h
        if not logout_h:
            url = _util.prefix_url("/bluebar/modern_settings_menu/")
            h_r = await self._session.post(url, data={"pmid": "4"})
            logout_h = re.search(r'name=\\"h\\" value=\\"(.*?)\\"', await h_r.text()).group(1)

        url = _util.prefix_url("/logout.php")
        resp = await self._session.get(url, params={"ref": "mb", "h": logout_h})
        return resp.status == 200

    @classmethod
    async def from_session(cls, session):
        # TODO: Automatically set user_id when the cookie changes in the session
        user_id = get_user_id(session)

        resp = await session.get(_util.prefix_url("/"))

        text = await resp.text()
        soup = find_input_fields(text)

        fb_dtsg_element = soup.find("input", {"name": "fb_dtsg"})
        if fb_dtsg_element:
            fb_dtsg = fb_dtsg_element["value"]
        else:
            # Fall back to searching with a regex
            fb_dtsg = FB_DTSG_REGEX.search(text).group(1)

        revision = int(text.split('"client_revision":', 1)[1].split(",", 1)[0])

        logout_h_element = soup.find("input", {"name": "h"})
        logout_h = logout_h_element["value"] if logout_h_element else None

        return cls(
            user_id=user_id,
            fb_dtsg=fb_dtsg,
            revision=revision,
            session=session,
            logout_h=logout_h,
        )

    def get_cookies(self):
        try:
            return self._session.cookie_jar._cookies["facebook.com"]
        except (AttributeError, KeyError):
            return None

    @classmethod
    async def from_cookies(cls, cookies, user_agent=None, loop: asyncio.AbstractEventLoop = None):
        session = session_factory(loop, user_agent)
        session.cookie_jar._cookies["facebook.com"] = cookies
        return await cls.from_session(session=session)

    def _generate_payload(self, query):
        if not query:
            query = {}
        query.update(self.get_params())
        return {key: str(value) for key, value in query.items() if value is not None}

    async def _get(self, url, params, error_retries=3, req_log=None, util_log=None):
        params = self._generate_payload(params)
        req_log.debug(f"GET {url}?{URL().with_query(params).query_string}")
        resp = await self._session.get(_util.prefix_url(url), params=params)
        content = await _util.check_request(resp)
        return _util.to_json(content, log=util_log)

    async def _post(self, url, data, files=None, as_graphql=False, req_log=None, util_log=None):
        if files:
            payload = aiohttp.FormData()
            for key, value in self._generate_payload(data).items():
                payload.add_field(key, str(value))
            for key, (name, file, content_type) in files.items():
                payload.add_field(key, file, filename=name, content_type=content_type)
            req_log.debug(f"POST {url} (files)")
        else:
            payload = self._generate_payload(data)
            req_log.debug(f"POST {url}?{URL().with_query(payload).query_string}")
        resp = await self._session.post(_util.prefix_url(url), data=payload)
        content = await _util.check_request(resp)
        if as_graphql:
            return _graphql.response_to_json(content)
        else:
            return _util.to_json(content, log=util_log)

    async def _payload_post(self, url, data, files=None, req_log=None, util_log=None):
        j = await self._post(url, data, files=files, req_log=req_log, util_log=util_log)
        _util.handle_payload_error(j)
        try:
            return j["payload"]
        except (KeyError, TypeError):
            raise _exception.FBchatException("Missing payload: {}".format(j))

    async def _graphql_requests(self, *queries, req_log=None, util_log=None):
        data = {
            "method": "GET",
            "response_format": "json",
            "queries": _graphql.queries_to_json(*queries),
        }
        return await self._post("/api/graphqlbatch/", data, as_graphql=True,
                                req_log=req_log, util_log=util_log)

    async def _upload(self, files, voice_clip=False, req_log=None, util_log=None):
        """Upload files to Facebook.

        `files` should be a list of files that requests can upload, see
        `requests.request <https://docs.python-requests.org/en/master/api/#requests.request>`_.

        Return a list of tuples with a file's ID and mimetype.
        """
        file_dict = {"upload_{}".format(i): f for i, f in enumerate(files)}

        data = {"voice_clip": voice_clip}

        j = await self._payload_post(
            "https://upload.facebook.com/ajax/mercury/upload.php", data, files=file_dict,
            req_log=req_log, util_log=util_log
        )

        if len(j["metadata"]) != len(files):
            raise _exception.FBchatException(
                "Some files could not be uploaded: {}, {}".format(j, files)
            )

        return [
            (data[_util.mimetype_to_key(data["filetype"])], data["filetype"])
            for data in j["metadata"]
        ]

    async def _do_send_request(self, data, req_log=None, util_log=None):
        offline_threading_id = _util.generate_offline_threading_id()
        data["client"] = "mercury"
        data["author"] = "fbid:{}".format(self.user_id)
        data["timestamp"] = _util.now()
        data["source"] = "source:chat:web"
        data["offline_threading_id"] = offline_threading_id
        data["message_id"] = offline_threading_id
        data["threading_id"] = _util.generate_message_id(self._client_id)
        data["ephemeral_ttl_mode:"] = "0"
        j = await self._post("/messaging/send/", data, req_log=req_log, util_log=util_log)

        # update JS token if received in response
        fb_dtsg = _util.get_jsmods_require(j, 2, log=util_log)
        if fb_dtsg is not None:
            self._fb_dtsg = fb_dtsg

        try:
            message_ids = [
                (action["message_id"], action["thread_fbid"])
                for action in j["payload"]["actions"]
                if "message_id" in action
            ]
            if len(message_ids) != 1:
                util_log.warning("Got multiple message ids' back: {}".format(message_ids))
            return message_ids[0]
        except (KeyError, IndexError, TypeError) as e:
            raise _exception.FBchatException(
                "Error when sending message: "
                "No message IDs could be found: {}".format(j)
            )
