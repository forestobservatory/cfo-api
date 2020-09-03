"""Convenience functions for interacting with the CFO catalog in the Salo Sciences REST API"""
from functools import wraps
import re
import logging
import json
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
    level=logging.WARNING,
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

# set the path to package data
package_path = os.path.realpath(__file__)
package_dir = os.path.dirname(package_path)
json_path = os.path.join(package_dir, "data", "paths.json")
with open(json_path, "r+") as f:
    PATHS = json.loads(f.read())


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

        return user_input

    except Exception as error:
        LOGGER.exception(error)


def get_email_pass():
    """
    Gets CFO email/password from environment variables or user input
    :return (email, password): tuple of strings for the users input email/password
    """

    # check environment variables first
    email = os.getenv("CFO_EMAIL")
    password = os.getenv("CFO_PASS")

    # get user input otherwise
    if email is None:
        email = get_input("E-mail")

    if password is None:
        password = get_input("Password")

    return email, password


def construct_asset_id(
    geography: str = None,
    category: str = None,
    metric: str = None,
    year: int = None,
    timeOfYear: str = None,
    resolution: int = None,
):
    """
    Constructs a CFO-format asset id string
    :param geography: see list from API.list_geographies()
    :param category: see list from API.list_categories()
    :param metric: see list from API.list_metrics()
    :param year: julian year
    :param timeOfYear: can be a date ('0825') or more general ('Fall')
    :param resolution: the spatial resolution in meters
    :return asset_id: a formatted string
    """
    # handle None
    if geography is None:
        geography = "*"
    if category is None:
        category = "*"
    if metric is None:
        metric = "*"
    if timeOfYear is None:
        timeOfYear = "*"

    # handle numerical cases
    if year is None:
        year = "*"
    else:
        year = f"{year:04d}"

    if resolution is None:
        resolution = "*"
    else:
        resolution = f"{resolution:05d}m"

    # join everything together
    asset_id = "-".join([geography, category, metric, year, timeOfYear, resolution])

    # replace common wildcards with the sql format wildcard
    wildcard = "%"
    finders = ["*", "?"]
    for finder in finders:
        asset_id = asset_id.replace(finder, wildcard)

    return asset_id


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

    def list_categories(self):
        """
        Lists the different categories of data available
        :return categories: list
        """
        return PATHS["category"]

    def list_metrics(self, category: str = None):
        """
        Lists the metrics available by category
        :param category: the category of data for each metric (see .list_categories())
        :return metrics: a list if category is specified, a dictionary with each metric if not
        """
        if category is None:
            return PATHS["metric"]
        else:
            try:
                return PATHS["metric"][category]
            except KeyError:
                LOGGER.warning(f"Unsupported category: {category}")
                LOGGER.warning(f"Must be one of {', '.join(self.list_categories())}")
                return None

    def list_geography_types(self):
        """
        Lists the broad geography classes (state, watershed, etc.)
        :return types: list
        """
        return list(PATHS["geography"].keys())

    def list_geographies(self, gtype: str = None):
        """
        Lists the specific geographic areas available
        :param gtype: the type of geography to list (see .list_geography_types())
        :return geographies: a list of type is specified, a dictionary with each geography if not
        """
        if type is None:
            return PATHS["geography"]
        else:
            try:
                return PATHS["geography"][gtype]
            except KeyError:
                LOGGER.warning(f"Unsupported category: {gtype}")
                LOGGER.warning(f"Must be one of {', '.join(self.list_geography_types())}")
                return None

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
        asset_id: str = None,
        bbox: list = None,
        description: str = None,
        raw: bool = False,
        just_assets: bool = False,
    ):
        """
        Queries the CFO API for datasets.
        :param geography: see list from API.list_geographies()
        :param category: see list from API.list_categories()
        :param metric: see list from API.list_metrics()
        :param year: julian year
        :param timeOfYear: can be a date ('0825') or more general ('Fall')
        :param resolution: the spatial resolution in meters
        :param asset_id: an asset id to search by. this is constructed by the above if not passed
        :param bbox: returns only results that intersect this box [xmin, ymin, xmax, ymax] (in lat/lon)
        :param description: a string that may match the dataset description
        :param raw: specifies whether to return the full response object. default is just json
        :param just_assets: specified whether to return just the asset IDs of the search result.
        :return response: the api search result
        """
        # construct an asset ID if not explicitly passed
        if asset_id is None:
            asset_id = construct_asset_id(
                geography=geography,
                category=category,
                metric=metric,
                year=year,
                timeOfYear=timeOfYear,
                resolution=resolution,
            )

        # send the request
        response = self._search_request(asset_id=asset_id, bbox=bbox, description=description)

        # and return the data
        if raw:
            return response
        elif just_assets:
            features = response.json()["features"]
            asset_ids = [feature["asset_id"] for feature in features]
            return asset_ids
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
