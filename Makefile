# SETUP

# help documentation
.DEFAULT: help
help:
	@echo "make init"
	@echo "	initialize tools for development -- conda, pip, etc"
	@echo "make update"
	@echo "	update tools for development -- conda, pip, etc"
	@echo "make docker-build"
	@echo "	build docker image for salo-data-acquisition service"
	@echo "make docker-deploy"
	@echo "	build and deploy docker image for cfo-api"
	@echo "make docker-clean"
	@echo "	clean all docker containers, images, and data"
	@echo "make test"
	@echo "   run tests"

# environment variables
CONDA_ENV=cfo
CONDA_RUN=conda run --name ${CONDA_ENV}
DOCKER_IMAGE=us.gcr.io/california-fores-1547767414612/cfo-api
DOCKER_TAG_GIT:=$(shell git rev-parse --short=12 HEAD)

# create directory for dummy files to indicate when targets need to be rerun
DIR_MAKE=.make
CONDA_UPDATED=${DIR_MAKE}/conda_updated
PIP_UPDATED=${DIR_MAKE}/pip_updated
DOCKER_INITIALIZED=${DIR_MAKE}/docker_initialized


# ENTRY POINTS

# initialize tools
init: conda-init pip-init misc-update
	@:

# update tools
update: conda-update pip-update misc-update
	@:

# run tests
test:
	${CONDA_RUN} pip install . && pytest --cov --no-cov-on-fail --cov-report=term-missing:skip-covered


# DETAILED ENTRIES

# conda
conda-init:
	@conda env list | grep -q -w ${CONDA_ENV} || conda env create --file environment-dev.yml
	@test -d ${DIR_MAKE} || mkdir ${DIR_MAKE}
	@touch ${CONDA_UPDATED}

conda-update: conda-init ${CONDA_UPDATED}
	@:
${CONDA_UPDATED}: environment.yml
	${CONDA_RUN} conda env update --file environment.yml --prune
	@test -d ${DIR_MAKE} || mkdir ${DIR_MAKE}
	@touch ${CONDA_UPDATED}

# pip -- only needed because some packages are not available via conda, need to use the conda version of pip to work correctly
pip-init: ${PIP_UPDATED}
	@:
pip-update: ${PIP_UPDATED}
	@:
${PIP_UPDATED}: requirements.txt
	${CONDA_RUN} pip install -r requirements.txt
	${CONDA_RUN} pip install --editable .
	@test -d ${DIR_MAKE} || mkdir ${DIR_MAKE}
	@touch ${PIP_UPDATED}

# misc
misc-update:
	@${CONDA_RUN} pre-commit install
	@test ! -f .gcloudignore || rm .gcloudignore
	@cp .gitignore .gcloudignore


# docker
docker-init: ${DOCKER_INITIALIZED}
	@:
${DOCKER_INITIALIZED}:
	gcloud auth configure-docker
	@test -d ${DIR_MAKE} || mkdir ${DIR_MAKE}
	@touch ${DOCKER_INITIALIZED}

docker-build: docker-init docker-clean
	@test ! -f .dockerignore || rm .dockerignore
	@cp .gitignore .dockerignore
	docker build  --tag ${DOCKER_IMAGE}:${DOCKER_TAG_GIT} .
	docker tag ${DOCKER_IMAGE}:${DOCKER_TAG_GIT} ${DOCKER_IMAGE}:testing
	docker tag ${DOCKER_IMAGE}:${DOCKER_TAG_GIT} ${DOCKER_IMAGE}:latest
	@docker system prune -f

docker-clean:
	@docker system prune -f

docker-deploy: docker-build
	docker push ${DOCKER_IMAGE}:${DOCKER_TAG_GIT}
	gcloud container images add-tag ${DOCKER_IMAGE}:${DOCKER_TAG_GIT} ${DOCKER_IMAGE}:testing -q
	gcloud container images add-tag ${DOCKER_IMAGE}:${DOCKER_TAG_GIT} ${DOCKER_IMAGE}:latest -q
