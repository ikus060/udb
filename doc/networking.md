# How to configure a reverse Proxy

## Configure Universal Database behind Apache Reverse Proxy with SSL

This documentation explains how to configure Universal Database behind an Apache reverse proxy with SSL. The Apache server will act as a gateway for requests to Universal Database, and SSL will provide additional security. The following steps can be used as a guide:

1. Install Apache and the required modules:

        sudo apt-get install apache2 python3-certbot-apache
        sudo a2enmod rewrite
        sudo a2enmod proxy
        sudo a2enmod ssl
        sudo a2enmod proxy_http
        sudo a2enmod headers

2. Request an SSL certificate for your domain

        sudo certbot certonly --expand -d udb.mydomain.com

    Follow the on-screen instructions to provide your email address, agree to the terms of service, and choose whether to share your email address with the EFF. Certbot will create certificates for you.

3. Basic configuration

    Add the following to your Apache configuration file:

        <VirtualHost *:80>
            ServerName udb.mydomain.com
            ProxyPass / http://localhost:8080/ retry=5
            ProxyPassReverse / http://localhost:8080/
            RequestHeader set X-Real-IP %{REMOTE_ADDR}s
        </VirtualHost>

    This will configure Apache to redirect requests to Universal Database, which is running on `localhost:8080`. The `RequestHeader` is used to set the `X-Real-IP` header, which is used by Universal Database to identify the client's IP address.

4. SSL configuration:

    Add the following to your Apache configuration file:

        <VirtualHost *:80>
            ServerName udb.mydomain.com
            ServerAdmin me@mydomain.com
            # Redirect HTTP to HTTPS
            RewriteEngine on
            RewriteRule ^(.*)$ https://udb.mydomain.com$1 [L,R=301]
            <Location />
                Order Allow,deny
                Allow from all
            </Location>
        </VirtualHost>

        <VirtualHost *:443>
            ServerName udb.mydomain.com
            ServerAdmin me@mydomain.com

            ProxyRequests Off
            ProxyPreserveHost On
            ProxyPass / http://localhost:8080/ retry=5
            ProxyPassReverse / http://localhost:8080/
            RequestHeader set X-Forwarded-Proto https
            RequestHeader set X-Real-IP %{REMOTE_ADDR}s

            # SSL Configuration
            SSLEngine on
            SSLCertificateFile    /etc/letsencrypt/live/udb.mydomain.com/cert.pem
            SSLCertificateKeyFile /etc/letsencrypt/live/udb.mydomain.com/privkey.pem
            SSLCertificateChainFile /etc/letsencrypt/live/udb.mydomain.com/fullchain.pem
            <Location />
                Order Allow,deny
                Allow from all
            </Location>
        </VirtualHost>

    This will configure Apache to listen on both port 80 and 443. The first virtual host redirects HTTP requests to HTTPS. The second virtual host proxies requests to Universal Database, preserves the original host header, and sets the `X-Forwarded-Proto` and `X-Real-IP` headers. The SSL certificate files must be specified in the configuration.

5. Define the external URL in Universal Database configuration:

    Edit `/etc/udb/udb.conf` and add the following line:

        server-host=127.0.0.1
        external-url=https://udb.mydomain.com/

    This tells Universal Database that it is running on localhost and that the external URL is `https://udb.mydomain.com/`. This is used for email notifications and to redirect the user to the correct URL.

## Configure Universal Database behind nginx reverse proxy

You may need a nginx server in case:

* you need to serve multiple web services from the same IP;
* you need more security (like HTTP + SSL).

This section doesn't explain how to install and configure your nginx server.
This is out-of-scope. The following is only provided as a suggestion and is in
no way a complete reference.

**Basic configuration**

        location / {
                # Define proxy header for cherrypy logging.
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Host $server_name;
                proxy_set_header X-Forwarded-Proto $scheme;
                # Proxy
                proxy_pass http://127.0.0.1:8080/;
        }

Make sure you set `X-Real-IP` so that Universal Database knows the real IP address of the client. This is used in the rate limit to identify the client.

Make sure you set `X-Forwarded-Proto` correctly so that Universal Database knows that access is being made using the `https` scheme. This is used to correctly create the URL on the page.
