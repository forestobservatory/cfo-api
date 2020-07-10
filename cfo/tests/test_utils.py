import requests

from cfo import utils


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
