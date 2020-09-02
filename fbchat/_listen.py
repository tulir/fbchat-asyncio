import attr
import random
import paho.mqtt.client
import urllib.request
import asyncio
import aiohttp
from ._common import log, kw_only
from . import _util, _exception, _session, _events

from typing import AsyncGenerator, Optional, List

from yarl import URL

try:
    import socks
except ImportError:
    socks = None

TOPICS = [
    # Things that happen in chats (e.g. messages)
    "/t_ms",
    # Group typing notifications
    "/thread_typing",
    # Private chat typing notifications
    "/orca_typing_notifications",
    # Active notifications
    "/orca_presence",
    # Other notifications not related to chats (e.g. friend requests)
    "/legacy_web",
    # Facebook's continuous error reporting/logging?
    "/br_sr",
    # Response to /br_sr
    "/sr_res",
    # Data about user-to-user calls
    # TODO: Investigate the response from this! (A bunch of binary data)
    # "/t_rtc",
    # TODO: Find out what this does!
    # TODO: Investigate the response from this! (A bunch of binary data)
    # "/t_p",
    # TODO: Find out what this does!
    "/webrtc",
    # TODO: Find out what this does!
    "/onevc",
    # TODO: Find out what this does!
    "/notify_disconnect",
    # Old, no longer active topics
    # These are here just in case something interesting pops up
    "/inbox",
    "/mercury",
    "/messaging_events",
    "/orca_message_notifications",
    "/pp",
    "/webrtc_response",
]


def get_cookie_header(session: aiohttp.ClientSession, url: str) -> str:
    """Extract a cookie header from a requests session."""
    # The cookies are extracted this way to make sure they're escaped correctly
    return session.cookie_jar.filter_cookies(URL(url)).output(header="", sep=";").lstrip()


def generate_session_id() -> int:
    """Generate a random session ID between 1 and 9007199254740991."""
    return random.randint(1, 2 ** 53)


def mqtt_factory(domain: str) -> paho.mqtt.client.Client:
    # Configure internal MQTT handler
    mqtt = paho.mqtt.client.Client(
        client_id="mqttwsclient",
        clean_session=True,
        protocol=paho.mqtt.client.MQTTv31,
        transport="websockets",
    )
    try:
        http_proxy = urllib.request.getproxies()["http"]
    except KeyError:
        http_proxy = None
    if http_proxy and socks and URL:
        proxy_url = URL(http_proxy)
        proxy_type = {
            "http": socks.HTTP,
            "https": socks.HTTP,
            "socks": socks.SOCKS5,
            "socks5": socks.SOCKS5,
            "socks4": socks.SOCKS4,
        }[proxy_url.scheme]
        mqtt.proxy_set(proxy_type=proxy_type, proxy_addr=proxy_url.host, proxy_port=proxy_url.port,
                       proxy_username=proxy_url.user, proxy_password=proxy_url.password)
    mqtt.enable_logger()
    # mqtt.max_inflight_messages_set(20)  # The rest will get queued
    # mqtt.max_queued_messages_set(0)  # Unlimited messages can be queued
    # mqtt.message_retry_set(20)  # Retry sending for at least 20 seconds
    # mqtt.reconnect_delay_set(min_delay=1, max_delay=120)
    mqtt.tls_set()
    mqtt.connect_async(f"edge-chat.{domain}", 443, keepalive=10)
    return mqtt


@attr.s(slots=True, kw_only=kw_only, eq=False, auto_attribs=True)
class Listener:
    """Listen to incoming Facebook events.

    Initialize a connection to the Facebook MQTT service.

    Args:
        session: The session to use when making requests.
        chat_on: Whether ...
        foreground: Whether ...

    Example:
        >>> listener = fbchat.Listener(session, chat_on=True, foreground=True)
    """

    session: _session.Session
    _chat_on: bool
    _foreground: bool
    _loop: asyncio.AbstractEventLoop = attr.ib(factory=asyncio.get_event_loop)
    _mqtt: paho.mqtt.client.Client = None
    _disconnect_error: Optional[Exception] = None
    _sync_token: Optional[str] = None
    _sequence_id: Optional[int] = None
    _sequence_id_wait: Optional[asyncio.Future] = None
    _tmp_events: List[_events.Event] = attr.ib(factory=list)
    _message_queue: asyncio.Queue = attr.ib(factory=lambda: asyncio.Queue(maxsize=64))

    def __attrs_post_init__(self):
        self._mqtt = mqtt_factory(self.session.domain)
        self._mqtt.on_message = self._on_message_handler
        self._mqtt.on_connect = self._on_connect_handler
        self._mqtt.on_socket_open = self.on_socket_open
        self._mqtt.on_socket_close = self.on_socket_close
        self._mqtt.on_socket_register_write = self.on_socket_register_write
        self._mqtt.on_socket_unregister_write = self.on_socket_unregister_write

    def on_socket_open(self, client, userdata, sock):
        self._loop.add_reader(sock, client.loop_read)

    def on_socket_close(self, client, userdata, sock):
        self._loop.remove_reader(sock)

    def on_socket_register_write(self, client, userdata, sock):
        self._loop.add_writer(sock, client.loop_write)

    def on_socket_unregister_write(self, client, userdata, sock):
        self._loop.remove_writer(sock)

    def _handle_ms(self, j):
        """Handle /t_ms special logic.

        Returns whether to continue parsing the message.
        """
        # TODO: Merge this with the parsing in _events

        # Update sync_token when received
        # This is received in the first message after we've created a messenger
        # sync queue.
        if "syncToken" in j and "firstDeltaSeqId" in j:
            self._sync_token = j["syncToken"]
            self._sequence_id = j["firstDeltaSeqId"]
            return False

        if "errorCode" in j:
            error = j["errorCode"]
            # TODO: 'F\xfa\x84\x8c\x85\xf8\xbc-\x88 FB_PAGES_INSUFFICIENT_PERMISSION\x00'
            if error in ("ERROR_QUEUE_NOT_FOUND", "ERROR_QUEUE_OVERFLOW"):
                # ERROR_QUEUE_NOT_FOUND means that the queue was deleted, since too
                # much time passed, or that it was simply missing
                # ERROR_QUEUE_OVERFLOW means that the sequence id was too small, so
                # the desired events could not be retrieved
                log.warning(
                    "The MQTT listener was disconnected for too long,"
                    " events may have been lost"
                )
                self._sync_token = None
                self._sequence_id = None
                return False
            log.error("MQTT error code %s received", error)
            return False

        # Update last sequence id
        # Except for the two cases above, this is always received
        self._sequence_id = j["lastIssuedSeqId"]
        return True

    def _on_message_handler(self, client, userdata, message):
        # Parse payload JSON
        try:
            j = _util.parse_json(message.payload.decode("utf-8"))
        except (_exception.FacebookError, UnicodeDecodeError):
            log.debug(message.payload)
            log.exception("Failed parsing MQTT data on %s as JSON", message.topic)
            return

        log.debug("MQTT payload: %s, %s", message.topic, j)

        if message.topic == "/t_ms":
            if not self._handle_ms(j):
                return

        try:
            for event in _events.parse_events(self.session, message.topic, j):
                self._message_queue.put_nowait(event)
        except _exception.ParseError:
            log.exception("Failed parsing MQTT data")

    def _on_connect_handler(self, client, userdata, flags, rc):
        if rc == 21:
            log.info("Return code 21 in connect handler, disconnecting and throwing error")
            self.disconnect()
            self._disconnect_error = _exception.NotConnected(
                "Failed connecting. Maybe your cookies are wrong?"
            )
            return
        if rc != 0:
            err = paho.mqtt.client.connack_string(rc)
            log.error("MQTT Connection Error: %s", err)
            return  # Don't try to send publish if the connection failed

        self._messenger_queue_publish()

    def _messenger_queue_publish(self):
        # configure receiving messages.
        payload = {
            "sync_api_version": 10,
            "max_deltas_able_to_process": 1000,
            "delta_batch_size": 500,
            "encoding": "JSON",
            "entity_fbid": self.session.user.id,
        }

        # If we don't have a sync_token, create a new messenger queue
        # This is done so that across reconnects, if we've received a sync token, we
        # SHOULD receive a piece of data in /t_ms exactly once!
        if self._sync_token is None:
            topic = "/messenger_sync_create_queue"
            payload["initial_titan_sequence_id"] = str(self._sequence_id)
            payload["device_params"] = None
        else:
            topic = "/messenger_sync_get_diffs"
            payload["last_seq_id"] = str(self._sequence_id)
            payload["sync_token"] = self._sync_token

        self._mqtt.publish(topic, _util.json_minimal(payload), qos=1)

    def _configure_connect_options(self):
        # Generate a new session ID on each reconnect
        session_id = generate_session_id()

        username = {
            # The user ID
            "u": self.session.user.id,
            # Session ID
            "s": session_id,
            # Active status setting
            "chat_on": self._chat_on,
            # foreground_state - Whether the window is focused
            "fg": self._foreground,
            # Can be any random ID
            "d": self.session._client_id,
            # Application ID, taken from facebook.com
            "aid": 219994525426954,
            # MQTT extension by FB, allows making a SUBSCRIBE while CONNECTing
            "st": TOPICS,
            # MQTT extension by FB, allows making a PUBLISH while CONNECTing
            # Using this is more efficient, but the same can be acheived with:
            #     def on_connect(*args):
            #         mqtt.publish(topic, payload, qos=1)
            #     mqtt.on_connect = on_connect
            # TODO: For some reason this doesn't work!
            "pm": [
                # {
                #     "topic": topic,
                #     "payload": payload,
                #     "qos": 1,
                #     "messageId": 65536,
                # }
            ],
            # Unknown parameters
            "cp": 3,
            "ecp": 10,
            "ct": "websocket",
            "mqtt_sid": "",
            "dc": "",
            "no_auto_fg": True,
            "gas": None,
            "pack": [],
        }

        self._mqtt.username_pw_set(_util.json_minimal(username))

        headers = {
            "Cookie": get_cookie_header(
                self.session._session, f"https://edge-chat.{self.session.domain}/chat"
            ),
            "User-Agent": self.session._session._default_headers["User-Agent"],
            "Origin": f"https://www.{self.session.domain}",
            "Host": f"edge-chat.{self.session.domain}",
        }

        # TODO: Is region (lla | atn | odn | others?) important?
        self._mqtt.ws_set_options(
            path="/chat?sid={}".format(session_id), headers=headers
        )

    async def _reconnect(self) -> None:
        # Try reconnecting
        self._configure_connect_options()
        try:
            self._mqtt.reconnect()
        except (
            # Taken from .loop_forever
            paho.mqtt.client.socket.error,
            OSError,
            paho.mqtt.client.WebsocketConnectionError,
        ) as e:
            raise _exception.NotLoggedIn("MQTT reconnection failed") from e

    def set_sequence_id(self, sequence_id: int) -> None:
        if self._sequence_id_wait:
            log.debug("Got expected set_sequence_id call, waking up listener")
            self._sequence_id_wait.set_result(sequence_id)
            self._sequence_id_wait = None
        else:
            log.debug("Got unexpected set_sequence_id call")

    async def listen(self) -> AsyncGenerator[_events.Event, Optional[bool]]:
        """Run the listening loop continually.

        This is a blocking call, that will yield events as they arrive.

        Example:
            Print events continually.

            >>> listener = Listener(session)
            >>> async for event in listener.listen():
            ...     print(event)
        """
        if self._sequence_id is None:
            fut = self._sequence_id_wait = self._loop.create_future()
            log.debug("Waiting for sequence ID...")
            self._sequence_id = await fut
            log.debug("Got sequence ID: %d", self._sequence_id)

        await self._reconnect()
        yield _events.Connect()
        exit_if_not_connected = False

        while True:
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                self.disconnect()
                # this might not be necessary
                self._mqtt.loop_misc()
                break
            rc = self._mqtt.loop_misc()

            # The sequence ID was reset in _handle_ms
            if self._sequence_id is None:
                fut = self._sequence_id_wait = self._loop.create_future()
                self._messenger_queue_publish()
                yield _events.Resync()
                log.debug("Waiting for sequence ID after resync...")
                self._sequence_id = await fut
                log.debug("Got sequence ID: %d", self._sequence_id)

            # If disconnect() has been called
            # Beware, internal API, may have to change this to something more stable!
            if self._mqtt._state == paho.mqtt.client.mqtt_cs_disconnecting:
                break  # Stop listening

            if rc != paho.mqtt.client.MQTT_ERR_SUCCESS:
                # If known/expected error
                if rc == paho.mqtt.client.MQTT_ERR_CONN_LOST:
                    yield _events.Disconnect(reason="Connection lost, retrying")
                elif rc == paho.mqtt.client.MQTT_ERR_NOMEM:
                    # This error is wrongly classified
                    # See https://github.com/eclipse/paho.mqtt.python/issues/340
                    yield _events.Disconnect(reason="Connection error, retrying")
                elif rc == paho.mqtt.client.MQTT_ERR_CONN_REFUSED:
                    raise _exception.NotLoggedIn("MQTT connection refused")
                elif rc == paho.mqtt.client.MQTT_ERR_NO_CONN:
                    if exit_if_not_connected:
                        raise _exception.NotConnected("MQTT error: no connection")
                    yield _events.Disconnect(reason="MQTT Error: no connection, retrying")
                else:
                    err = paho.mqtt.client.error_string(rc)
                    log.error("MQTT Error: %s", err)
                    yield _events.Disconnect(reason=f"MQTT Error: {err}, retrying")

                await self._reconnect()
                exit_if_not_connected = True
                yield _events.Connect()
                self._mqtt.subscribe([(topic, 0) for topic in TOPICS])
            else:
                exit_if_not_connected = False

            while True:
                try:
                    yield self._message_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
        if self._disconnect_error:
            log.info("disconnect_error is set, raising and clearing variable")
            err = self._disconnect_error
            self._disconnect_error = None
            raise err

    def disconnect(self) -> None:
        """Disconnect the MQTT listener.

        Can be called while listening, which will stop the listening loop.

        The `Listener` object should not be used after this is called!

        Example:
            Stop the listener when receiving a message with the text "/stop"

            >>> for event in listener.listen():
            ...     if isinstance(event, fbchat.MessageEvent):
            ...         if event.message.text == "/stop":
            ...             listener.disconnect()  # Almost the same "break"
        """
        self._mqtt.disconnect()

    def set_foreground(self, value: bool) -> None:
        """Set the ``foreground`` value while listening."""
        # TODO: Document what this actually does!
        payload = _util.json_minimal({"foreground": value})
        info = self._mqtt.publish("/foreground_state", payload=payload, qos=1)
        self._foreground = value
        # TODO: We can't wait for this, since the loop is running within the same thread
        # info.wait_for_publish()

    def set_chat_on(self, value: bool) -> None:
        """Set the ``chat_on`` value while listening."""
        # TODO: Document what this actually does!
        # TODO: Is this the right request to make?
        data = {"make_user_available_when_in_foreground": value}
        payload = _util.json_minimal(data)
        info = self._mqtt.publish("/set_client_settings", payload=payload, qos=1)
        self._chat_on = value
        # TODO: We can't wait for this, since the loop is running within the same thread
        # info.wait_for_publish()

    # def send_additional_contacts(self, additional_contacts):
    #     payload = _util.json_minimal({"additional_contacts": additional_contacts})
    #     info = self._mqtt.publish("/send_additional_contacts", payload=payload, qos=1)
    #
    # def browser_close(self):
    #     info = self._mqtt.publish("/browser_close", payload=b"{}", qos=1)
