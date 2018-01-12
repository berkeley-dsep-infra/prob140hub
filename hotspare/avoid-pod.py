#!/usr/bin/python3

# wait for a singleuser server pods to appear on our node, then kill our pod

import os
from kubernetes import client, config, watch

POD_LABEL_K = 'component'
POD_LABEL_V = 'singleuser-server'

def pod_is_encroaching(pod, node_name):
	print('checking ' + pod.metadata.name)
	if pod.status.phase != 'Running':
		return False
	if POD_LABEL_K not in pod.metadata.labels:
		return False
	if pod.metadata.labels[POD_LABEL_K] != POD_LABEL_V:
		return False
	if pod.spec.node_name != node_name:
		print('pod {} is not running on our node'.format(pod.metadata.name))
		return False

	print("pod {} with {}:{} is running on our node {}".format(
		pod.metadata.name, POD_LABEL_K, POD_LABEL_V, pod.spec.node_name
	))
	return True
	
# main

# environment seeded by the job template
my_node_name = os.environ['MY_NODE_NAME']
my_pod_name = os.environ['MY_POD_NAME']
my_pod_namespace = os.environ['MY_POD_NAMESPACE']

config.load_incluster_config()
#config.load_kube_config()

v1 = client.CoreV1Api()

w = watch.Watch()

for event in w.stream(v1.list_pod_for_all_namespaces):
	# given list_pod_, stream will return objects of type Pod
	if pod_is_encroaching(event['object'], my_node_name):
		w.stop()

print("deleting our pod")
v1.delete_namespaced_pod(my_pod_name, my_pod_namespace,
	client.V1DeleteOptions())
