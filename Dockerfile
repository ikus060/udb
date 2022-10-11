FROM python:3.9

# Install project and run test
WORKDIR /tmp
COPY . .
RUN apt -yq update && \
    pip install . &&  pip install .[test] && pytest

CMD [ "python", "/usr/local/bin/udb" ]
