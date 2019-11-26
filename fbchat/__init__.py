"""Facebook Messenger library for Python/Asyncio

:copyright: (c) 2015 - 2019 Taehoon Kim
:copyright: (c) 2019 Tulir Asokan
:license: BSD 3-Clause, see LICENSE for more details.
"""

import logging as _logging

# Set default logging handler to avoid "No handler found" warnings.
_logging.getLogger(__name__).addHandler(_logging.NullHandler())

# The order of these is somewhat significant, e.g. User has to be imported after Thread!
from . import _core, _util
from ._exception import FBchatException, FBchatFacebookError
from ._thread import ThreadType, ThreadLocation, ThreadColor, Thread
from ._user import TypingStatus, User, ActiveStatus
from ._group import Group
from ._page import Page
from ._message import EmojiSize, MessageReaction, Mention, Message
from ._attachment import Attachment, UnsentMessage, ShareAttachment
from ._sticker import Sticker
from ._location import LocationAttachment, LiveLocationAttachment
from ._file import FileAttachment, AudioAttachment, ImageAttachment, VideoAttachment
from ._quick_reply import (
    QuickReply,
    QuickReplyText,
    QuickReplyLocation,
    QuickReplyPhoneNumber,
    QuickReplyEmail,
)
from ._poll import Poll, PollOption
from ._plan import GuestStatus, Plan

from ._client import Client

__title__ = "fbchat-asyncio"
__version__ = "0.3.0"
__description__ = "Facebook Messenger library for Python/Asyncio."

__copyright__ = "Copyright 2015 - 2019 by Taehoon Kim"
__license__ = "BSD 3-Clause"

__author__ = "Tulir Asokan"
__email__ = "tulir@maunium.net"
