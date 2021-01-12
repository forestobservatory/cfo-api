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
    level=logging.WARNING,
    format=("%(asctime)s %(levelname)s %(name)s [%(funcName)s] | %(message)s"),
    stream=sys.stdout,
)
LOGGER = logging.getLogger(__name__)

# define the endpoints
ENDPOINTS = {
    "auth": "/users/auth",
    "refresh": "/users/auth/refresh",
    "search": "/data/search",
    "fetch": "/data/fetch",
    "pixel_pick": "/data/pixel_pick",
    "public_key": "/data/public_key",
    "styles": "/data/styles",
}

# set the path to package data
package_path = os.path.realpath(__file__)
package_dir = os.path.dirname(package_path)
json_path = os.path.join(package_dir, "data", "paths.json")
with open(json_path, "r+") as f:
    PATHS = json.loads(f.read())

# create a temp directory to store the authentication data
TMP_DIR = os.path.join(tempfile.gettempdir(), "cfo")
if not os.path.exists(TMP_DIR):
    os.mkdir(TMP_DIR)
TMP_KEY = tempfile.NamedTemporaryFile(mode="w+", dir=TMP_DIR, delete=True)
TMP_FILE = os.path.join(TMP_DIR, "token")


def auth_required():
    """Decorator to require authorization before an API request is made"""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):

            self = args[0]
            name = view.__name__
            warning = f"Authentication is required for function .{name}()"

            # first run auth
            if "Authorization" not in self._session.headers:
                status = self.authenticate(ignore_temp=False)
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
    Reads a gzipped token tempfile
    :param path: the path to the gzipped file
    :return token: a token string
    """
    with gzip.open(path, "rb") as f:
        return f.read().decode()


def write_token_file(token: str, path: str):
    """
    Writes token data to a gzipped tempfile
    :param token: a string containing the token data
    :param path: the path to the output tempfile
    :return:
    """
    with gzip.open(path, "wb") as f:
        f.write(token.encode("utf-8"))


def write_public_key(tf, data: dict):
    """
    Writes json key data to a temporary file
    :param tf: the tempfile NamedTemporaryFile object
    :param data: the public key auth data
    :return none: no object returned; an environment variable is updated
    """
    # write the json data
    tf.file.write(json.dumps(data, indent=2) + "\n")
    tf.file.flush()

    # point the google auth to this file path
    global os
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tf.name


def validate_geography(lon: float, lat: float):
    """
    Verifies that latitude and longitude values are valid
    :param lon: longitude value in degrees
    :param lat: latitude value in degrees
    :return valid: boolean for whether the lon/lat values are valid
    """
    lon_valid = lon >= -180 and lon <= 180
    lat_valid = lat >= -90 and lat <= 90
    valid = lon_valid and lat_valid
    if not valid:
        return False
    else:
        return True


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

    def list_fuel_metrics(self):
        """
        Lists the veg metrics needed to create a landscape file
        :return metrics: a list of "Vegetation" metrics used to generate landscape files
        """
        return [
            "SurfaceFuels",
            "CanopyCover",
            "CanopyHeight",
            "CanopyBaseHeight",
            "CanopyBulkDensity",
        ]

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

    def list_styles(self):
        """
        Lists the WMS styles available
        :returns styles: list of style strings
        """
        response = self._styles_request()
        success, msg = check(response)
        if success:
            styles = response.json()["styles"]
            return styles
        else:
            LOGGER.warning(msg)
            raise

    def authenticate(self, ignore_temp: bool = True):
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

                    # get the public auth key
                    response = self._public_key_request()
                    if response.status_code == 200:
                        write_public_key(TMP_KEY, response.json())

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

                # get the public auth key
                response = self._public_key_request()
                if response.status_code == 200:
                    write_public_key(TMP_KEY, response.json())

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
        just_assets: bool = True,
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
        Downloads a CFO asset to your local machine
        :param asset_id: a CFO asset ID string (often returned from search())
        :param path: the output file path. Set to ./{asset_id}.tif by default. Appends '.tif' if not set.
        :return:
        """
        if path is None:
            path = os.path.join(os.getcwd(), f"{asset_id}.tif")
        else:
            if ".tif" not in path.lower():
                path = f"{path}.tif"

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
        self,
        asset_id: str,
        dl: bool = False,
        wms: bool = False,
        gdal: bool = False,
        bucket: bool = False,
        fetch_types: list = [],
    ):
        """
        Fetches the download / map / file url for an asset
        :param asset_id: a CFO asset ID string (often returned from search() )
        :param dl: returns the asset download url (a google cloud signed url)
        :param wms: returns a wms url (for web mapping applications)
        :param gdal: returns a vsicurl address to read the data using GDAL
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
        if True not in [dl, wms, bucket, gdal] and len(fetch_types) == 0:
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
        if gdal:
            param = "gdal"
            response = self._fetch_request(asset_id, fetch_type="uri")
            success, msg = check(response)
            if success:
                uri = response.json()[link]
                vsi = f"/vsigs/{uri[5:]}"
                responses[param] = vsi
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
        if len(fetch_types) != 0:
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

    def pixel_pick(self, asset_id: str, lon: float, lat: float):
        """
        Returns the pixel value at a point coordinate from a CFO asset
        :param asset_id: a CFO asset ID string (often returned from search())
        :param lon: the longitude (x) location in decimal degrees
        :param lat: the latitude (y) location in decimal degrees
        :return response: the pixel_pick api response.
        """
        # verify the geometry is valid
        if not validate_geography(lon, lat):
            LOGGER.warning(f"Invalid longitude/latidude values: {lat:0.2f}/{lon:0.2f}")
            LOGGER.warning("Must be in range [-180, 180] and [-90, 90], respectively.")
            return None

        # verify the asset ID is valid
        response = self._search_request(asset_id=asset_id)
        success, msg = check(response)
        if not success:
            LOGGER.warning(f"Invalid asset_id: {asset_id}")
            LOGGER.warning(msg)
            return None

        # then get the dang pixel value
        response = self._pixel_pick_request(asset_id, lon, lat)
        if not success:
            LOGGER.warning(msg)
        else:
            return response.json()["val"]

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
        self,
        catalog: str = CATALOG,
        asset_id: str = None,
        bbox: list = None,
        date: str = None,
        description: str = None,
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

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def _styles_request(self):
        """
        Submits the GET request to the styles endpoint
        :return response: the request response
        """
        endpoint = ENDPOINTS["styles"]
        request_url = f"{URL}{endpoint}"
        response = self._session.get(request_url)

        return response

    @auth_required()
    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def _public_key_request(self):
        """
        Submits the GET request to the public_key endpoint
        :return response: the request response
        """
        endpoint = ENDPOINTS["public_key"]
        request_url = f"{URL}{endpoint}"
        response = self._session.get(request_url)

        return response

    def _pixel_pick_request(self, asset_id: str, lon: float, lat: float, catalog: str = CATALOG):
        """
        Submits the POST request to the pixel_pick endpoint
        :param asset_id: a full cfo asset id to request pixel values from
        :param lon: the longitude location to request pixel values from
        :param lat: the latitude location to request pixel values from
        :param catalog: the data catalog to query
        :return response: the request response
        """
        endpoint = ENDPOINTS["pixel_pick"]
        request_url = f"{URL}{endpoint}"
        body = {
            "catalog": catalog,
            "asset_id": asset_id,
            "lng": lon,
            "lat": lat,
        }
        response = self._session.post(request_url, json=body)

        return response
