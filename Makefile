# Everything runs in Docker: nothing is installed on your machine (except optional `make venv`).
COMPOSE = docker compose
PROD    = docker compose -f docker-compose.yml -f docker-compose.prod.yml
FILE   ?= data/dev/sample.jsonl

.PHONY: help up down logs sh run load db reset venv prod prod-logs prod-down deploy

help:            ## list commands
	@grep -E '^[a-z-]+:.*## ' Makefile | sed 's/:.*## /\t/'

up:              ## start db + api with live reload on http://localhost:8000/docs
	@test -f .env || (echo "Missing .env: run  cp .env.example .env  and fill it in" && exit 1)
	$(COMPOSE) up -d --build

down:            ## stop everything (keeps the database)
	$(COMPOSE) down

logs:            ## follow api logs
	$(COMPOSE) logs -f api

sh:              ## shell inside the app container
	$(COMPOSE) run --rm api bash

run:             ## run any command in the container: make run CMD="python -m detect.cluster"
	$(COMPOSE) run --rm api $(CMD)

load:            ## embed and load a JSONL file: make load FILE=data/dev/planted_swarms.jsonl
	$(COMPOSE) run --rm api python -m ingest.load_jsonl $(FILE)

db:              ## MariaDB console
	$(COMPOSE) exec db sh -c 'mariadb -u"$$MARIADB_USER" -p"$$MARIADB_PASSWORD" "$$MARIADB_DATABASE"'

reset:           ## wipe the database and re-run db/schema.sql
	$(COMPOSE) down -v
	$(COMPOSE) up -d

venv:            ## optional local .venv (inside this folder) for editor autocompletion only
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

prod:            ## VPS: build and start with HTTPS (Caddy)
	@test -f .env || (echo "Missing .env: run  cp .env.example .env  and fill it in" && exit 1)
	$(PROD) up -d --build

prod-logs:       ## VPS: follow all logs
	$(PROD) logs -f

prod-down:       ## VPS: stop everything (keeps the database)
	$(PROD) down

deploy:          ## VPS: pull the latest code and restart
	git pull
	$(PROD) up -d --build
