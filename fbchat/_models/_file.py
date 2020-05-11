import attr
import datetime
from . import Image, Attachment
from .._common import attrs_default
from .. import _util

from typing import Set, Optional


@attrs_default
class FileAttachment(Attachment):
    """Represents a file that has been sent as a Facebook attachment."""

    #: URL where you can download the file
    url: Optional[str] = None
    #: Size of the file in bytes
    size: Optional[int] = None
    #: Name of the file
    name: Optional[str] = None
    #: Whether Facebook determines that this file may be harmful
    is_malicious: Optional[bool] = None

    @classmethod
    def _from_graphql(cls, data, size=None):
        return cls(
            url=data.get("url"),
            size=size,
            name=data.get("filename"),
            is_malicious=data.get("is_malicious"),
            id=data.get("message_file_fbid"),
        )


@attrs_default
class AudioAttachment(Attachment):
    """Represents an audio file that has been sent as a Facebook attachment."""

    #: Name of the file
    filename: Optional[str] = None
    #: URL of the audio file
    url: Optional[str] = None
    #: Duration of the audio clip
    duration: Optional[datetime.timedelta] = None
    #: Audio type
    audio_type: Optional[str] = None

    @classmethod
    def _from_graphql(cls, data):
        return cls(
            filename=data.get("filename"),
            url=data.get("playable_url"),
            duration=_util.millis_to_timedelta(data.get("playable_duration_in_ms")),
            audio_type=data.get("audio_type"),
        )


@attrs_default
class ImageAttachment(Attachment):
    """Represents an image that has been sent as a Facebook attachment.

    To retrieve the full image URL, use: `Client.fetch_image_url`, and pass it the id of
    the image attachment.
    """

    #: The extension of the original image (e.g. ``png``)
    original_extension: Optional[str] = None
    #: Width of original image
    width: Optional[int] = attr.ib(default=None, converter=_util.int_or_none)
    #: Height of original image
    height: Optional[int] = attr.ib(default=None, converter=_util.int_or_none)
    #: Whether the image is animated
    is_animated: Optional[bool] = None
    #: A set, containing variously sized / various types of previews of the image
    previews: Set[Image] = attr.ib(factory=set)

    @classmethod
    def _from_graphql(cls, data):
        previews = {
            Image._from_uri_or_none(data.get("thumbnail")),
            Image._from_uri_or_none(data.get("preview") or data.get("preview_image")),
            Image._from_uri_or_none(data.get("large_preview")),
            Image._from_uri_or_none(data.get("animated_image")),
        }

        return cls(
            original_extension=data.get("original_extension")
            or (data["filename"].split("-")[0] if data.get("filename") else None),
            width=data.get("original_dimensions", {}).get("width"),
            height=data.get("original_dimensions", {}).get("height"),
            is_animated=data["__typename"] == "MessageAnimatedImage",
            previews={p for p in previews if p},
            id=data.get("legacy_attachment_id"),
        )

    @classmethod
    def _from_list(cls, data):
        previews = {
            Image._from_uri_or_none(data["image"]),
            Image._from_uri(data["image1"]),
            Image._from_uri(data["image2"]),
        }

        return cls(
            width=data["original_dimensions"].get("x"),
            height=data["original_dimensions"].get("y"),
            previews={p for p in previews if p},
            id=data["legacy_attachment_id"],
        )


@attrs_default
class VideoAttachment(Attachment):
    """Represents a video that has been sent as a Facebook attachment."""

    #: Size of the original video in bytes
    size: Optional[int] = None
    #: Width of original video
    width: Optional[int] = None
    #: Height of original video
    height: Optional[int] = None
    #: Length of video
    duration: Optional[datetime.timedelta] = None
    #: URL to very compressed preview video
    preview_url: Optional[str] = None
    #: A set, containing variously sized previews of the video
    previews: Set[Image] = attr.ib(factory=set)

    @classmethod
    def _from_graphql(cls, data, size=None):
        previews = {
            Image._from_uri_or_none(data.get("chat_image")),
            Image._from_uri_or_none(data.get("inbox_image")),
            Image._from_uri_or_none(data.get("large_image")),
        }

        return cls(
            size=size,
            width=data.get("original_dimensions", {}).get("width"),
            height=data.get("original_dimensions", {}).get("height"),
            duration=_util.millis_to_timedelta(data.get("playable_duration_in_ms")),
            preview_url=data.get("playable_url"),
            previews={p for p in previews if p},
            id=data.get("legacy_attachment_id"),
        )

    @classmethod
    def _from_subattachment(cls, data):
        media = data["media"]
        image = Image._from_uri_or_none(media.get("image"))

        return cls(
            duration=_util.millis_to_timedelta(media.get("playable_duration_in_ms")),
            preview_url=media.get("playable_url"),
            previews={image} if image else {},
            id=data["target"].get("video_id"),
        )

    @classmethod
    def _from_list(cls, data):
        previews = {
            Image._from_uri(data["image"]),
            Image._from_uri(data["image1"]),
            Image._from_uri(data["image2"]),
        }

        return cls(
            width=data["original_dimensions"].get("x"),
            height=data["original_dimensions"].get("y"),
            previews=previews,
            id=data["legacy_attachment_id"],
        )


def graphql_to_attachment(data, size=None):
    _type = data["__typename"]
    if _type in ["MessageImage", "MessageAnimatedImage"]:
        return ImageAttachment._from_graphql(data)
    elif _type == "MessageVideo":
        return VideoAttachment._from_graphql(data, size=size)
    elif _type == "MessageAudio":
        return AudioAttachment._from_graphql(data)
    elif _type == "MessageFile":
        return FileAttachment._from_graphql(data, size=size)

    return Attachment(id=data.get("legacy_attachment_id"))


def graphql_to_subattachment(data):
    target = data.get("target")
    type_ = target.get("__typename") if target else None

    if type_ == "Video":
        return VideoAttachment._from_subattachment(data)

    return None
