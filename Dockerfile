FROM python:3.9

# Install project and run test
WORKDIR /tmp
COPY . .
RUN pip install . &&  pip install .[test] && pytest && rm -Rf /tmp /root/.cache

CMD [ "python", "/usr/local/bin/udb" ]
