#!/bin/bash
# This script is used by travis to trigger deployments or builds

# .travis.yml env vars:
# - DOCKER_USERNAME
# - DOCKER_PASSWORD
# - GCLOUD_PROJECT
# travis project env vars:
# - encrypted_0f80927fa736_key
# - encrypted_0f80927fa736_iv

set -euo pipefail

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

ACTION="${1}"
PUSH=''
if [[ ${ACTION} == 'build' ]]; then
    if [[ ${TRAVIS_PULL_REQUEST} == 'false' ]]; then
        PUSH='--push'
        # Assume we're in master and have secrets!
        docker login -u $DOCKER_USERNAME -p "$DOCKER_PASSWORD"
    fi

    # Attempt to improve relability of pip installs:
    # https://github.com/travis-ci/travis-ci/issues/2389
    sudo sysctl net.ipv4.tcp_ecn=0

    ./deploy.py build --commit-range ${TRAVIS_COMMIT_RANGE} ${PUSH}
elif [[ ${ACTION} == 'deploy' ]]; then
    echo "Starting deploy..."
    REPO="https://github.com/${TRAVIS_REPO_SLUG}"
    REMOTE_CHECKOUT_DIR="/tmp/${TRAVIS_BUILD_NUMBER}"
    COMMIT="${TRAVIS_COMMIT}"
    MASTER_HOST="datahub-fa17-${TRAVIS_BRANCH}.westus2.cloudapp.azure.com"
	GCLOUD_CREDS="prob140/secrets/gcloud-creds.json"

	prepare_gcloud
    
    echo "Fetching gcloud service account credentials..."
    # Travis only allows encrypting one file per repo. LAME
    openssl aes-256-cbc \
		-K $encrypted_0f80927fa736_key \
		-iv $encrypted_0f80927fa736_iv \
		-in ${GCLOUD_CREDS}.enc -out ${GCLOUD_CREDS} -d
    chmod 0400 ${GCLOUD_CREDS}

	gcloud auth activate-service-account --key-file ${GCLOUD_CREDS}
    gcloud config set project ${GCLOUD_PROJECT}

    gcloud container clusters get-credentials $CLOUDSDK_CORE_PROJECT

    echo "SSHing..."
	gcloud compute ssh ${MASTER_HOST} \
        "rm -rf ${REMOTE_CHECKOUT_DIR} && git clone ${REPO} ${REMOTE_CHECKOUT_DIR} && cd ${CHECKOUT_DIR} && git checkout ${COMMIT} && git crypt unlock /etc/deploy-secret-keyfile && ./deploy.py deploy ${TRAVIS_BRANCH} && rm -rf ${REMOTE_CHECKOUT_DIR}"

    echo "Done!"
fi
