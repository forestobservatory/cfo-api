<img src="cfo-logo.png" alt="California Forest Observatory" style="display: block; float: left; margin-right: 10px;"/>

Python wrappers and a command line executable for accessing Forest Observatory data via the Salo API.

# Introduction

The [California Forest Observatory][cfo-web] (CFO) is a data-driven forest monitoring system that maps the drivers of wildfire behavior across the state—including vegetation fuels, weather, topography & infrastructure—from space.

The `cfo` python library was designed to provide easy access to CFO datasets. Each dataset has a unique `asset_id`, and the `search` and `fetch` workflows were designed to query and download these assets. You can search for asset IDs by geography, data type, and time of year (`forest.search(geography="SantaCruzCounty", metric="CanopyHeight", year=2020)`), then fetch a URL to download the file (`forest.fetch(asset_id, dl=True)`) or a WMS URL to for web mapping (e.g. `forest.fetch(asset_id, wms=True)`). There's also a function to directly download the data to your loacal machine (`forest.download(asset_id, output_file)`). All CFO assets are stored and downloaded as GeoTIFFs.

CFO data are available for free for non-commercial use. You must have a CFO account, which you can create by visiting [the web map][cfo-web], clicking the menu in the top right corner and selecting "Create an account." Please keep track of the e-mail address and password you used to create your Forest Observatory account, as you'll need them to authenticate API access.

You can find support for the CFO API at the [community forum][cfo-forum] and in-depth documentation at [ReadTheDocs][cfo-rtd].

### Table of contents

- [Installation](#installation)
- [Authentication](#authentication)
- [Searching for data](#searching-for-data)
- [Downloading and visualizing data](#downloading-and-visualizing-data)
- [Contact](#contact)

# Installation

This library can be installed via `pip` directly from Github.

```bash
pip install git+https://github.com/forestobservatory/cfo-api.git
```

If you don't have `pip` you could also clone the repository locally and install using python's `setuptools`

```bash
git clone https://github.com/forestobservatory/cfo-api.git
cd cfo-api
python setup.py install
```

Once installed, you should be able to load the `cfo` module in python. Instatiate the `api` class to begin working with the Forest Observatory API.

```python
import cfo
forest = cfo.api()
```

# Authentication

A Forest Observatory account is required to use the API (sign up free at [forestobservatory.com][cfo-web]).

There are two authentication methods: entering your CFO account's email/password at runtime or setting environment variables.

### Passing your credentials at runtime

Using any API call (`forest.search()`, `forest.fetch()`, `forest.download()`) will prompt you to enter the following authentication information:

```python
>>> CFO E-mail: slug@forest.net
>>> CFO Password: **********
```

You can also authenticate directly with `forest.authenticate()`.

This retrieves an authentication token from the API, which is stored as a temp file for future access (this does not store your e-mail/password). The API reads this stored token and means you won't have to pass your email/password during each session.

### Setting environment variables 

You can forego runtime credential entry by setting environment variables. This is the lowest friction, least secure approach. You'll set the following variables in your `.bashrc` profile or elsewhere.

```bash
export CFO_EMAIL=slug@forest.net
export CFO_PASS=ari0limax
```

### Restoring a botched authentication

The temp file that stores your authentication credentials can sometimes get donked up. To re-authenticate, use the following command to pass your credentials and overwrite the temporary token data.

```python
forest.authenticate(ignore_temp=True)
```

# Searching for data

CFO data are organized by `asset_id`. These IDs contain information on the spatial extent of the data, the category and name of the data, the time of collection, and the spatial resolution with the following format:

```python
asset_id = {geography}-{category}-{metric}-{year}-{timeOfYear}-{resolution}
```

Some examples:

- A statewide vegetation fuels dateset that's rendered in the `layers` tab: `California-Vegetation-CanopyHeight-2020-Summer-00010m`.
- A statewide weather dataset queried in the `trends` tab: `California-Weather-WindSpeed-2020-0601-03000m`.
- A county-level dataset accessed in the `download` tab: `Marin-Vegetation-SurfaceFuels-2020-Spring-00010m`.

The `forest.search()` function queries the API and returns the assets that match the search terms.

```python
>>> import cfo
>>> forest = cfo.api()
>>> forest.search(geography="MendocinoCounty", metric="CanopyCover")
2020-09-07 13:53:47,028 INFO cfo.utils [authenticate] Loaded cfo token
['MendocinoCounty-Vegetation-CanopyCover-2020-Fall-00010m']
```

The default behavior of this function is to only return the asset IDs as a list.

You can instead return the API JSON data, including asset ID, the spatial extent (`bbox`) of the data, the catalog its stored in, etc. by setting `just_assets=False`.

```python
>>> forest.search(geography="MendocinoCounty", metric="CanopyCover", just_assets=False)
[{'asset_id': 'MendocinoCounty-Vegetation-CanopyCover-2020-Fall-00010m', 'attribute_dict': {}, 'bbox': [-124.022978699284, -122.814767867036, 38.7548320538975, 40.0060478879686], 'catalog': 'cfo', 'description': 'CanopyCover', 'expiration_utc_datetime': '', 'utc_datetime': '2020-07-09 09:52:42.292286+00:00'}]
```

And to examine the full response from the `requests` library, use `forest.search(raw=True)`.

But with over 17,000 published assets it's not easy to know just what to search by. So we wrote some functions to simplify your searches.

### Convenience functions

Based on the asset ID naming convention above, we've provided some `list` functions as a guide to what's available.

- `geography` - CFO datasets have been clipped to different spatial extents: statewide, by county, by municipality, by watershed.
  - `forest.list_geographies()` - returns the different geographic extents. Use `list_geographies(by="County")` to narrow return just the unique counties.
  - `forest.list_geography_types()` - returns the categories of geographical clipping available.
- `category` - We currently provide three categories of data.
  - `forest.list_categories()` - returns [`Vegetation`, `Weather` and `Wildfire`]
- `metric` - each category of data contains a list of different data types
  - `forest.list_metrics()` - returns the unique metrics for each category. Run `list_metrics(category="Weather")` to return only weather-specific metrics.

Use these metrics as keywords in searching for data: `id_list = forest.search(geography="FresnoCounty", category="Vegetation")`.

### A note on availabile datasets

Even though we have a range of geographic extents, resolutions, and metrics, it is **not** the case that we provide all permutations of extent/resolution/metric. For example, we clip all `Vegetation` data to the county level, but we do not clip any `Weather` data that fine. All weather data are only available at the state level. This means you don't really need to specify the geographic extent in your search, and you'll get pretty far with `weather_ids = forest.seearch(metric="WindSpeed")`.

# Downloading and visualizing data


# Contact

Issue tracking isn't set up for this repository. Please visit the [Forest Observatory Community Forum][cfo-forum] for technical support. To get in touch directly or to inquire about commercial API access, contact [tech@forestobservatory.com](mailto:tech@forestobservatory.com).

The California Forest Observatory API is developed and maintained by [Salo Sciences][salo-web].


[cfo-web]: https://forestobservatory.com
[cfo-forum]: https://groups.google.com/a/forestobservatory.com/g/community
[cfo-rtd]: 
[salo-web]: https://salo.ai
