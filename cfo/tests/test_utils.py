import os
import builtins
import mock
import requests

from cfo import utils

# get authentication inputs
try:
    email = os.environ["CFO_EMAIL"]
    password = os.environ["CFO_PASS"]
except KeyError:
    email = "bad@example.com"
    password = "badpassword"


def test_connection():
    """Test internet connectivity"""
    url = "http://httpbin.org/get"
    body = {"content": "testing"}
    response = requests.get(url, body)
    assert response.status_code == 200
    assert response.json()["args"] == body


def test_endpoints():
    """Tests connections to API endpoints"""
    entries = list(utils.ENDPOINTS.keys())
    for entry in entries:
        url = "{host}{endpoint}".format(host=utils.URL, endpoint=utils.ENDPOINTS[entry])
        response = requests.get(url)
        assert response.status_code != 404


def test_get_input():
    """Tests user input"""
    with mock.patch.object(builtins, "input", lambda _: email):
        assert utils.get_input(email) == email
        assert utils.get_input(email) != password


def test_get_email_pass():
    """Tests retreival of email/password combo"""
    e, p = utils.get_email_pass()
    assert e == email
    assert p == password
    assert e != password
    assert p != email
