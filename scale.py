#!/usr/bin/env python3
# vim: set nonumber et sw=4 ts=4:

import argparse
import multiprocessing
import subprocess
import sys
import yaml

from kubernetes import client, config, watch

def get_pods_with_selector(context, namespace, selector='name=hub'):
    '''Return the name of the hub pod.'''
    cmd = ['kubectl', '--context='+context,
        '--namespace='+namespace, 'get', 'pods', '--no-headers', 
        '-o=custom-columns=NAME:.metadata.name',
        '--selector={}'.format(selector),
    ]
    out = subprocess.check_output(cmd)
    return out.decode().strip().split()

def count_pods(context, namespace, selector):
    '''Count all "jupyter-" pods in a namespace.'''
    pods = get_pods_with_selector(context, namespace, selector)
    return len(pods)

def count_singleuser_pods(context, namespace):
    return count_pods(context, namespace,
        selector='component=singleuser-server')

def get_hub_pod(context, namespace, selector='name=hub'):
    return get_pods_with_selector(context, namespace, 'name=hub')[0]

def get_all_nodes(context):
    cmd = ['kubectl', '--context='+context, 'get', 'node',
        '--no-headers', '--output=custom-columns=NAME:.metadata.name']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE).stdout
    buf = p.read()
    p.close()
    nodes = buf.split()
    return nodes

def get_singleuser_image(context, namespace, hub_pod):
    '''Return the name:tag of the hub's singleuser image.'''
    cmd = ['kubectl', '--context='+context,
        '--namespace='+namespace, 'get', 'pod', '-o=yaml',
        hub_pod]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE).stdout
    buf = p.read()
    p.close()
    description = yaml.load(buf)
    image = ''
    for env in description['spec']['containers'][0]['env']:
        if env['name'] == 'SINGLEUSER_IMAGE':
            image = env['value']
            break
    return image

def docker_pull(args):
    (zone, node, image) = args
    cmd = ['gcloud', 'compute', 'ssh', node, '--zone='+zone, '--',
         'docker-credential-gcr configure-docker && docker pull ' + image]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE).stdout
    buf = p.read()
    p.close()
    return buf

def resize_cluster(cluster, node_pool, new_node_count):
    cmd = ['gcloud', '--quiet', 'container', 'clusters', 'resize', cluster,
        '--node-pool='+node_pool, '--size', str(new_node_count)]
    print(' '.join(cmd))
    p = subprocess.run(cmd)

## MAIN
project = 'project-name-goes-here'
zone = 'us-central1-a'
node_pool = 'default-pool'
POD_THRESHOLD = 0.9
BUMP_INCREMENT = 2

clusters = {
    'prob140-staging':{
        'namespace': 'staging',
        'users_per_node': 5
    },
    'prob140-prod':{
        'namespace': 'default',
        'users_per_node': 22
    },
}

parser = argparse.ArgumentParser(description='Scale JupyterHub nodes.')
parser.add_argument('-c', dest='clusters', nargs='+',
    default=list(clusters.keys()), help='Kubernetes cluster.')
parser.add_argument('-p', dest='pool_size', type=int,
    help='Manually scale to this many nodes.')
args = parser.parse_args()

for cluster in args.clusters: 
    namespace = clusters[cluster]['namespace']
    context = 'gke_{}_{}_{}'.format(project, zone, cluster)

    if args.pool_size:
        new_pool_size = args.pool_size

    else:
        # How many nodes do we have?
        nodes = get_all_nodes(context)
        node_count = len(nodes)

        # How many pods does that accommodate?
        max_pods = node_count * clusters[cluster]['users_per_node']

        # How many pods are active?
        cur_pods = count_singleuser_pods(context, namespace)

        threshold = POD_THRESHOLD * max_pods
        print('cluster: {}\tnodes: {}\tnum pods: {}/{} max({})'.format(
            cluster, node_count, cur_pods, threshold, max_pods)
        )
        if cur_pods < threshold:
            continue
        new_pool_size = node_count + BUMP_INCREMENT

    resize_cluster(cluster, node_pool, new_pool_size)

    # Populate latest singleuser image on all nodes
    hub_pod = get_hub_pod(context, namespace)
    image = get_singleuser_image(context, namespace, hub_pod)
    if not image:
        print("Could not identify singleuser image.")
        sys.exit(1)

    # Pull this container in all of the nodes in current kubernetes context
    args = map(lambda x: (zone, x, image), nodes)
    with multiprocessing.Pool(processes=16) as pool:
        pool.map(docker_pull, args)
