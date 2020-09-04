"""Convenience functions for interacting with the CFO catalog in the Salo Sciences REST API"""
from functools import wraps
import re
import logging
import tempfile
import json
import gzip
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
    level=logging.INFO, format=("%(asctime)s %(levelname)s %(name)s [%(funcName)s] %(message)s"), stream=sys.stdout,
)
LOGGER = logging.getLogger(__name__)

# define the endpoints
ENDPOINTS = {
    "auth": "/users/auth",
    "refresh": "/users/auth/refresh",
    "search": "/data/search",
    "fetch": "/data/fetch",
    "pixel_pick": "/data/pixel_pick",
}

# set the path to package data
package_path = os.path.realpath(__file__)
package_dir = os.path.dirname(package_path)
json_path = os.path.join(package_dir, "data", "paths.json")
with open(json_path, "r+") as f:
    PATHS = json.loads(f.read())

# create a temp directory to store the jwt token
TMP_DIR = os.path.join(tempfile.gettempdir(), "cfo")
TMP_FILE = os.path.join(TMP_DIR, "token")
if not os.path.exists(TMP_DIR):
    os.mkdir(TMP_DIR)


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


def check(response: object):
    """
    Evaluates the response code and message returned by a search request
    :return [success, msg]: a boolean success/fail on the request and the response message
    """
    if response.status_code == 200:
        success = True
        msg = "slugs rule"
    else:
        success = False
        msg = response.content

    return [success, msg]


def read_token_file(path: str):
    """
    """
    with gzip.open(path, "rb") as f:
        return f.read().decode()


def write_token_file(token: str, path: str):
    """
    """
    with gzip.open(path, "wb") as f:
        f.write(token.encode("utf-8"))


class API(object):
    """Utility class for Salo API requests"""

    def __init__(self):
        """API class constructor"""

        # create the REST session
        self._session = requests.Session()

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

    def list_geographies(self, by: str = None):
        """
        Lists the specific geographic areas available
        :param by: the type of geography to list (see .list_geography_types())
        :return geographies: a list if type is specified, a dictionary with each geography if not
        """
        if type is None:
            return PATHS["geography"]
        else:
            try:
                return PATHS["geography"][by]
            except KeyError:
                LOGGER.warning(f"Unsupported category: {by}")
                LOGGER.warning(f"Must be one of {', '.join(self.list_geography_types())}")
                return None

    def list_fetch_types(self):
        """
        Lists the different link types that can be retrieved from the fetch() routine
        :returns fetch_types: list of strings
        """
        return ["wms", "signed_url", "uri", "url", "wms_preview"]

    def authenticate(self, ignore_temp: bool = False):
        """
        Retrieves a JWT authentication token. Requires a forestobservatory.com account.
        :return status_code: the API response status code
        """
        # check for a stored token
        login = True
        if not ignore_temp:
            if os.path.exists(TMP_FILE):
                try:
                    token = read_token_file(TMP_FILE)
                    LOGGER.info("Loaded cfo token")
                    auth = {"Authorization": f"Bearer {token}"}
                    self._session.headers.update(auth)
                    login = False
                    status = 200
                except PermissionError:
                    LOGGER.warning("Unable to read token from temp file")

        # otherwise
        if login:
            email, password = get_email_pass()
            token, status = self._auth_request(email, password)
            del password
            if status == 200:
                LOGGER.info("Authentication successful")
                auth = {"Authorization": f"Bearer {token}"}
                self._session.headers.update(auth)

                # write it to a temp file for convenience
                try:
                    write_token_file(token, TMP_FILE)
                except PermissionError:
                    pass

            else:
                LOGGER.warning(f"Authentication failed with status code {status}")

        return status

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

        # check for failures
        success, msg = check(response)

        # return the data on a success
        if success:
            if raw:
                return response
            elif just_assets:
                features = response.json()["features"]
                asset_ids = [feature["asset_id"] for feature in features]
                return asset_ids
            else:
                return response.json()["features"]

        # otherwise, debug
        else:
            LOGGER.warning(msg)
            return msg

    def download(self, asset_id: str, path: str = None):
        """
        Downloads an asset ID to your local machine
        :param asset_id: a CFO asset ID string (often returned from search() )
        :param path: the output file path. Set to ./{asset_id}.tif by default. Appends '.tif' if not set.
        :return:
        """
        # set default messages/params
        err = f"Failed to download asset: {asset_id}"

        # set default path behavior
        if path is None:
            path = f"{asset_id}.tif"
        else:
            if ".tif" not in path.lower():
                path = f"{path}.tif"

        # check that it's writeable
        if not os.access(path, os.W_OK):
            LOGGER.warning(err)
            LOGGER.warning(f"Unable to write to file: {path}")
            pass

        # fetch the url by asset ID
        url = self.fetch(asset_id, dl=True)

        # then stream the file to disk
        r = requests.get(url, stream=True)
        if r.ok:
            LOGGER.info(f"Beginning download for: {asset_id}")
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=128):
                    f.write(chunk)

            # check that it worked
            if os.stat(path).st_size > 0:
                LOGGER.info(f"Successfully downloaded {asset_id} to file: {path}")

    def fetch(
        self, asset_id: str, dl: bool = False, wms: bool = False, bucket: bool = False, fetch_types: list = None,
    ):
        """
        Fetches the download / map / file url for an asset
        :param asset_id: a CFO asset ID string (often returned from search() )
        :param dl: specifies whether to return the asset download url (a google cloud signed url)
        :param wms: specifies whether to return a wms url (for web mapping applications)
        :param bucket: returns a google cloud bucket url to the asset id
        :param fetch_types: the full range of fetch options accepted by the API (from get_fetch_types())
        :return response: the api fetch result. returns a string if only one boolean parameter passed, otherwise a dict.
        """
        # handle multiple pathways of parameter setting
        responses = dict()
        params = list()
        n_params = 0
        link = "link"

        # make sure something is set
        if True not in [dl, wms, bucket] and True not in fetch_types:
            # set a default option
            dl = True

        # check each fetch type
        if dl:
            param = "dl"
            response = self._fetch_request(asset_id, fetch_type="signed_url")
            success, msg = check(response)
            if success:
                responses[param] = response.json()[link]
                params.append(param)
                n_params += 1
            else:
                LOGGER.warning(msg)
                raise
        if wms:
            param = "wms"
            response = self._fetch_request(asset_id, fetch_type="wms")
            success, msg = check(response)
            if success:
                responses[param] = response.json()[link]
                params.append(param)
                n_params += 1
            else:
                LOGGER.warning(msg)
                raise
        if bucket:
            param = "bucket"
            response = self._fetch_request(asset_id, fetch_type="uri")
            success, msg = check(response)
            if success:
                responses[param] = response.json()[link]
                params.append(param)
                n_params += 1
            else:
                LOGGER.warning(msg)
                raise

        # run through types last
        if fetch_types is not None:
            supported = set(self.list_fetch_types())
            if supported.intersection(set(fetch_types)) != supported:
                LOGGER.warning(f"Unsupported type parameter passed: [{', '.join(fetch_types)}]")
                LOGGER.warning(f"Supported type parameters: [{', '.join(supported)}]")
                return None
            else:
                for fetch_type in fetch_types:
                    response = self._fetch_request(asset_id, fetch_type)
                    success, msg = check(response)
                    if success:
                        responses[fetch_type] = response.json()[link]
                        n_params += 1
                    else:
                        LOGGER.warning(msg)
                        raise

        # determine what you return based on the number of passed options
        if n_params == 1:
            return responses[params[0]]  # just the link url
        else:
            return responses  # the multi-param dictionary

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
            LOGGER.warning("Authentication failed. Try and run .authenticate(ignore_temp=True)")
            LOGGER.warning(response.content)

        return token, response.status_code

    @auth_required()
    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def _search_request(
        self, catalog: str = CATALOG, asset_id: str = None, bbox: list = None, date: str = None, description: str = None
    ):
        """
        Submits the POST request to the search endpoint
        :param catalog: the data catalog to query
        :param asset_id: a partial/full cfo asset id to search for
        :param bbox: a lat/lon bounding box of [xmin, ymin, xmax, ymax] extent
        :param date: a utc datetime to query by
        :param description: a partial/full dataset description to search by
        :return response: the request response
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

    @auth_required()
    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def _fetch_request(self, asset_id: str, fetch_type: str, catalog: str = CATALOG):
        """
        Submits the POST request to the search endpoint
        :param asset_id: a full cfo asset id to fetch
        :param fetch_type: the type of url to return
        :param catalog: the data catalog to query
        :return response: the request response
        """
        endpoint = ENDPOINTS["fetch"]
        request_url = f"{URL}{endpoint}"
        body = {
            "catalog": catalog,
            "asset_id": asset_id,
            "type": fetch_type,
        }
        response = self._session.post(request_url, json=body)

        return response
