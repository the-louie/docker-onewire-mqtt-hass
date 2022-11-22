FROM debian:latest

# install dependencies
RUN apt-get update
RUN apt-get -y install python3 python3-pip python3-dev build-essential
RUN pip install --upgrade setuptools
RUN pip install paho-mqtt==1.3.1 pyownet==0.10.0 setproctitle==1.1.10 configparser

# cleanup
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /tmp/*

# copy files
RUN mkdir /app
COPY ./app/config.cfg /app/
COPY ./app/script.py /app/
WORKDIR /app

# entry point
CMD /usr/bin/python3 /app/script.py /app/config.cfg