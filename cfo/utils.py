"""Convenience functions for interacting with the CFO catalog in the Salo Sciences REST API"""
import json
from functools import wraps
import re
import logging
import os
import sys
from getpass import getpass

import requests
from retrying import retry

# global parameters
URL = "https://api.salo.ai"
CATALOG = "cfo"

# logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format=("%(asctime)s (%(relativeCreated)d) %(levelname)s %(name)s [%(funcName)s:%(lineno)d] %(message)s"),
    stream=sys.stdout,
)
LOGGER = logging.getLogger(__name__)

# define the endpoints
ENDPOINTS = {
    "auth": "/users/auth",
    "refresh": "/users/auth/refresh",
    "search": "/data/search",
    "fetch": "/data/fetch",
    "styles": "/data/styles",
    "pixel_pick": "/data/pixel_pick",
}


def auth_required():
    """Decorator to require authorization before a request is made"""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):

            self = args[0]
            name = view.__name__
            warning = f"Authentication is required for function .{name}()"

            # first run auth
            if "Authorization" not in self._session.headers:
                status = self.authenticate()
                if status != 200:
                    LOGGER.warning(warning)
                    return None

            if not self._session.headers["Authorization"].startswith("Bearer "):
                LOGGER.warning("Authorization header is not a bearer type")
                LOGGER.warning(warning)
                return None

            matches = re.match(r"^Bearer (\S+)$", self._session.headers["Authorization"])
            if not matches:
                LOGGER.warning("Invalid bearer token format")
                LOGGER.warning(warning)
                return None

            return view(*args, **kwargs)

        return wrapper

    return decorator


# get user input for user/pass
def get_input(data_type: str):
    """
    Gets command line user input
    :param data_type: the data type to prompt the user to request
    :return user_input: the user entered content
    """
    prompt = f"CFO {data_type}: "
    try:
        if data_type.lower() == "password":
            user_input = getpass(prompt)
        else:
            user_input = input(prompt)
    except Exception as error:
        LOGGER.exception(error)

    return user_input


def get_email_pass():
    """
    Gets CFO email/password from environment variables or user input
    :return (email, password): tuple of strings for the users input email/password
    """

    # check environment variables firest
    email = os.getenv("CFO_EMAIL")
    password = os.getenv("CFO_PASS")

    # get user input otherwise
    if email is None:
        email = get_input("E-mail")

    if password is None:
        password = get_input("Password")

    return email, password


# set the API class
class API(object):
    """Utility class for Salo API requests"""

    def __init__(self):
        """API class constructor"""

        # create the REST session
        self._session = requests.Session()

        # set empty attributes to be retrieved later
        self._token = None

    def help(self):
        """Returns the docstring for the main class"""
        return self.__doc__

    def authenticate(self):
        """
        Retrieves a JWT authentication token. Requires a forestobservatory.com account.
        :return status_code: the API response status code
        """
        email, password = get_email_pass()
        token, status = self._auth_request(email, password)
        del password
        if status == 200:
            LOGGER.info("Authentication successful")
            auth = {"Authorization": f"Bearer {token}"}
            self._session.headers.update(auth)
        else:
            LOGGER.warning(f"Authentication failed with status code {status}")

        return status

    @auth_required()
    def search(
        self,
        geography: str = None,
        category: str = None,
        metric: str = None,
        year: int = None,
        timeOfYear: str = None,
        resolution: int = None,
        raw: bool = False,
    ):
        """
        Queries the CFO API for datasets
        """
        response = self._search_request()
        if raw:
            return response
        else:
            return response.json()["features"]

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def _auth_request(self, email: str, password: str):
        """
        Retrieves a JWT token for the email/password combo
        :param email: registered email address
        :param password: CFO account password
        :return: (token, status_code)
        """
        endpoint = ENDPOINTS["auth"]
        request_url = f"{URL}{endpoint}"
        body = {"email": email, "password": password}
        response = self._session.post(request_url, json=body)

        # hope for success
        if response.status_code == 200:
            token = response.json()["token"]

        else:
            token = None
            LOGGER.debug(response.content)

        return token, response.status_code

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def _search_request(
        self, catalog: str = CATALOG, asset_id: str = None, bbox: list = None, date: str = None, description: str = None
    ):
        """
        """
        endpoint = ENDPOINTS["search"]
        request_url = f"{URL}{endpoint}"
        body = {
            "catalog_list": catalog,
            "asset_id": asset_id,
            "bounding_box": bbox,
            "datetime": date,
            "description": description,
        }
        response = self._session.post(request_url, json=body)

        return response
