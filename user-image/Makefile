VERSION=$(shell git rev-parse --short HEAD)
IMAGE=berkeleydsep/singleuser-prob140

release: VERSION=$(shell git tag -l --points-at HEAD)

build:
	docker build -t $(IMAGE):$(VERSION) .

push:
	docker push $(IMAGE):$(VERSION)

release: build push
