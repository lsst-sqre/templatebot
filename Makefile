.PHONY: install
install:
	pip install -e ".[dev]"

.PHONY: test
test:
	pytest

.PHONY: dev
dev:
	adev runserver --app-factory create_app templatebot/app.py

.PHONY: image
image:
	python setup.py sdist
	docker build --build-arg VERSION=`templatebot --version` -t lsstsqre/templatebot:build .

.PHONY: travis-docker-deploy
travis-docker-deploy:
	./bin/travis-docker-deploy.sh lsstsqre/templatebot build

.PHONY: version
version:
	templatebot --version
