FROM python:3.9

# Install JVM
RUN pip install pytest

# Install project and run test
WORKDIR /tmp
COPY . .
RUN pip install . && pytest

CMD [ "python", "/usr/local/bin/cmdb" ]
