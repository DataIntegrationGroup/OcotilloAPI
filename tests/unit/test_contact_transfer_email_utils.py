from transfers.contact_transfer import _looks_like_phone_in_email_field, _make_email


def test_make_email_strips_email_prefix_and_trailing_punctuation():
    email = _make_email(
        "first",
        "owner",
        email="Email: dlglnd@verizon.net.",
        email_type="Primary",
        release_status="private",
    )
    assert email is not None
    assert email.email == "dlglnd@verizon.net"


def test_phone_like_email_field_detection():
    assert _looks_like_phone_in_email_field("(505)-470-5877") is True
    assert _looks_like_phone_in_email_field("(505) 259-1757") is True
    assert _looks_like_phone_in_email_field("francisco_rael@hotmail.com") is False
