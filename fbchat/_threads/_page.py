import attr
import datetime
from ._abc import ThreadABC
from .._common import attrs_default
from .. import _session, _models

from typing import Optional


@attrs_default
class Page(ThreadABC):
    """Represents a Facebook page. Implements `ThreadABC`.

    Example:
        >>> page = fbchat.Page(session=session, id="1234")
    """

    # TODO: Implement pages properly, the implementation is lacking in a lot of places!

    #: The session to use when making requests.
    session: _session.Session
    #: The unique identifier of the page.
    id: str = attr.ib(converter=str)

    def _to_send_data(self):
        return {"other_user_fbid": self.id}

    def _copy(self) -> "Page":
        return Page(session=self.session, id=self.id)


@attrs_default
class PageData(Page):
    """Represents data about a Facebook page.

    Inherits `Page`, and implements `ThreadABC`.
    """

    #: The page's picture
    photo: _models.Image
    #: The name of the page
    name: str
    #: When the thread was last active / when the last message was sent
    last_active: Optional[datetime.datetime] = None
    #: Number of messages in the thread
    message_count: Optional[int] = None
    #: Set `Plan`
    plan: Optional[_models.PlanData] = None
    #: The page's custom URL
    url: Optional[str] = None
    #: The name of the page's location city
    city: Optional[str] = None
    #: Amount of likes the page has
    likes: Optional[int] = None
    #: Some extra information about the page
    sub_title: Optional[str] = None
    #: The page's category
    category: Optional[str] = None

    @classmethod
    def _from_graphql(cls, session, data):
        if data.get("profile_picture") is None:
            data["profile_picture"] = {}
        if data.get("city") is None:
            data["city"] = {}
        plan = None
        if data.get("event_reminders") and data["event_reminders"].get("nodes"):
            plan = _models.PlanData._from_graphql(
                session, data["event_reminders"]["nodes"][0]
            )

        return cls(
            session=session,
            id=data["id"],
            url=data.get("url"),
            city=data.get("city").get("name"),
            category=data.get("category_type"),
            photo=_models.Image._from_uri(data["profile_picture"]),
            name=data["name"],
            message_count=data.get("messages_count"),
            plan=plan,
        )
