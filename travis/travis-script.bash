#!/bin/bash
# This script is used by travis to trigger deployments or builds

# .travis.yml env vars:
# - DOCKER_USERNAME
# - DOCKER_PASSWORD
# - GCLOUD_PROJECT
# - HUB_COURSE
# travis project env vars:
# - encrypted_b00c78b73ea7_key (created by 'travis encrypt-file')
# - encrypted_b00c78b73ea7_iv  (created by 'travis encrypt-file')

set -euo pipefail

CLUSTER="${HUB_COURSE}-${TRAVIS_BRANCH}"

openssl_key=${encrypted_b00c78b73ea7_key}
openssl_iv=${encrypted_b00c78b73ea7_iv}

function prepare_gcloud {
    # Install gcloud
	if [ ! -d "$HOME/google-cloud-sdk/bin" ]; then
        rm -rf $HOME/google-cloud-sdk
        export CLOUDSDK_CORE_DISABLE_PROMPTS=1
        curl https://sdk.cloud.google.com | bash
    fi
    source ${HOME}/google-cloud-sdk/path.bash.inc
    gcloud --quiet components update kubectl
}

function build {
	echo "Starting build..."
	PUSH=''
	if [[ ${TRAVIS_PULL_REQUEST} == 'false' ]]; then
		PUSH='--push'
		# Assume we're in master and have secrets!
		docker login -u $DOCKER_USERNAME -p "$DOCKER_PASSWORD"
	fi

	# Attempt to improve relability of pip installs:
	# https://github.com/travis-ci/travis-ci/issues/2389
	sudo sysctl net.ipv4.tcp_ecn=0

	./deploy.py build --commit-range ${TRAVIS_COMMIT_RANGE} ${PUSH}
}

function deploy {
	echo "Starting deploy..."

	prepare_gcloud
	
	echo "Fetching gcloud service account credentials..."
	openssl aes-256-cbc \
		-K ${openssl_key} -iv ${openssl_iv} \
		-in git-crypt.key.enc -out git-crypt.key -d
	chmod 0400 git-crypt.key

	git-crypt unlock git-crypt.key

	gcloud auth activate-service-account \
		--key-file hub/secrets/gcloud-creds.json
	gcloud config set project ${GCLOUD_PROJECT}

	gcloud container clusters get-credentials ${CLUSTER}

	./deploy.py deploy ${TRAVIS_BRANCH}

	echo "Done!"
}

# main
case $1 in
	build)  build ;;
	deploy) deploy ;;
esac
