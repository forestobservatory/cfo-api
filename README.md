# California Forest Observatory API

Python wrappers and a command line executable for accessing Forest Observatory data via the Salo API

# Introduction

The [California Forest Observatory][cfo-web] (CFO) is a data-driven forest monitoring system that maps the drivers of wildfire behavior across the state—including vegetation fuels, weather, topography & infrastructure—from space.

CFO data are available for free for non-commercial use. You must have a CFO account, which you can create by visiting [the web map][cfo-web], clicking the menu and clicking "Create an account." Please keep track of the e-mail address and password you used to create your Forest Observatory account; you'll need them to authenticate your API access.

### Table of contents

- [Installation](#installation)
- [Authentication](#authentication)
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

Once the library is installed, you should be able to load the `cfo` module in python. Instatiate the `API` class to begin working with the Forest Observatory API.

```python
import cfo
firetower = cfo.API()
```

# Authentication

There are two methods for authentication: setting environment variables or passing your CFO account's email/password. 

### Setting environment variables 

This is the lowest friction but least secure approach. You'll set the following two variables in your `.bashrc` profile or elsewhere.

```bash
export CFO_EMAIL=slug@forest.net
export CFO_PASS=mytypedpassword
```

### Passing your credentials at runtime

Instead, you can enter your CFO account's email/password as you instatiate the API.

```python
import cfo
firetower = cfo.API()
firetower.authenticate()
```

You'll be prompted to enter the following:

```
>>> CFO E-mail: slug@forest.net
>>> CFO Password: **********
```

# Contact

The California Forest Observatory API is developed and maintained by [Salo Sciences][salo-web].


[cfo-web]: https://forestobservatory.com
[salo-web]: https://salo.ai
