from pydantic import BaseModel, EmailStr, Field, field_validator

from zgrader.models import ContactTopic

# Length caps are the first line of spam defence and the reason the columns
# are sized the way they are. The message cap is generous enough for a real
# enquiry about a card and far short of what a link-stuffing bot wants.
_NAME = Field(min_length=1, max_length=200)
_SUBJECT = Field(min_length=1, max_length=200)
_MESSAGE = Field(min_length=10, max_length=5000)


class ContactMessageRequest(BaseModel):
    name: str = _NAME
    email: EmailStr
    topic: ContactTopic = ContactTopic.other
    subject: str = _SUBJECT
    message: str = _MESSAGE
    # Two letters, matching the frontend's locale codes. Anything else falls
    # back to English rather than rejecting an otherwise valid enquiry.
    language: str = Field(default="en", max_length=5)
    submission_code: str | None = Field(default=None, max_length=20)

    # The honeypot. Hidden from real users by CSS and left empty by them;
    # bots fill every field they find. Named `website` rather than something
    # like `honeypot` because the name is visible in the markup and the whole
    # trick depends on it looking worth filling in.
    #
    # A filled honeypot is *not* rejected with an error -- see the router.
    website: str = ""

    @field_validator("name", "subject", "message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        """Reject whitespace-only input.

        min_length alone counts characters, so a subject of five spaces passes
        it and then renders as an empty line in the operator's inbox.
        """
        stripped = value.strip()
        if not stripped:
            raise ValueError("This field cannot be empty.")
        return stripped

    @field_validator("submission_code")
    @classmethod
    def _blank_code_is_none(cls, value: str | None) -> str | None:
        """An untouched optional field arrives as "", which is not a code."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ContactMessageResponse(BaseModel):
    """Deliberately says nothing about what happened to the message.

    A spam submission caught by the honeypot gets exactly this response too, so
    the reply cannot be used to work out what tripped the filter.
    """

    received: bool = True
