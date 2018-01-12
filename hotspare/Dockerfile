FROM ubuntu:17.04

RUN apt-get update && \
	apt-get -y install python3-pip vim

RUN pip3 install kubernetes==4.0.0

ADD avoid-pod.py /srv/

RUN apt-get clean

CMD /srv/avoid-pod.py
