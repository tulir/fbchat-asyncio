import attr
from . import Image, Attachment
from .._common import attrs_default

from typing import Optional


@attrs_default
class Sticker(Attachment):
    """Represents a Facebook sticker that has been sent to a thread as an attachment."""

    #: The sticker-pack's ID
    pack: Optional[str] = None
    #: Whether the sticker is animated
    is_animated: bool = False

    # If the sticker is animated, the following should be present
    #: URL to a medium spritemap
    medium_sprite_image: Optional[str] = None
    #: URL to a large spritemap
    large_sprite_image: Optional[str] = None
    #: The amount of frames present in the spritemap pr. row
    frames_per_row: Optional[int] = None
    #: The amount of frames present in the spritemap pr. column
    frames_per_col: Optional[int] = None
    #: The total amount of frames in the spritemap
    frame_count: Optional[int] = None
    #: The frame rate the spritemap is intended to be played in
    frame_rate: Optional[int] = None

    #: The sticker's image
    image: Optional[Image] = None
    #: The sticker's label/name
    label: Optional[str] = None

    @classmethod
    def _from_graphql(cls, data):
        if not data:
            return None

        return cls(
            id=data["id"],
            pack=data["pack"].get("id") if data.get("pack") else None,
            is_animated=bool(data.get("sprite_image")),
            medium_sprite_image=data["sprite_image"].get("uri")
            if data.get("sprite_image")
            else None,
            large_sprite_image=data["sprite_image_2x"].get("uri")
            if data.get("sprite_image_2x")
            else None,
            frames_per_row=data.get("frames_per_row"),
            frames_per_col=data.get("frames_per_column"),
            frame_count=data.get("frame_count"),
            frame_rate=data.get("frame_rate"),
            image=Image._from_url_or_none(data),
            label=data["label"] if data.get("label") else None,
        )
