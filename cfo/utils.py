"""Convenience functions for interacting with the CFO catalog in the Salo Sciences REST API"""
import json
import logging
import os
import sys
from getpass import getpass

import requests
from retrying import retry

# global parameters
REQUEST_TIMEOUT = 1.72  # seconds to wait for a response
URL = "https://api.salo.ai"

# logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format=("%(asctime)s (%(relativeCreated)d) %(levelname)s %(name)s [%(funcName)s:%(lineno)d] %(message)s"),
    stream=sys.stdout,
)
LOGGER = logging.getLogger(__name__)


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

    def get_token(self, email: str, password: str):
        """
        """
        endpoint = "/users/auth"
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

    def authenticate(self):
        """
        """
        email, password = get_email_pass()
        token, status = self.get_token(email, password)
        del password
        if status == 200:
            LOGGER.info("Authentication successful")
            self._token = token
        else:
            LOGGER.debug("Authentication failed with status code %s", status)
