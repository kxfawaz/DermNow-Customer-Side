from unittest.mock import patch
from app import send_mailgun_email

@patch("requests.post")
def test_mailgun_send(mock_post):
    mock_post.return_value.status_code = 200
    ok, msg = send_mailgun_email("test@test.com", "Hello", "Test Body")

    assert ok is True
    assert mock_post.called
