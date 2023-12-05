# Configuration

There are several entry points available for administrator to manage the configuration of Universal Database. This section aims to outline those configurations and explain each option available and what it does.

You may configure every option using the configuration file, command line argument or environment variable.

Take note that configuration options are distinct from the runtime setting, available from the web interface. The configuration options here usually meant to be static and set before starting the server. You may get the list of configuration options by calling `udb --help`.

Note: If an option is specified in more than one place, the command line arguments override the environment variable, environment variables override config files, and config files override default value.

## Configuration file

To use configuration files, you may call `udb` with `-f` or `--config` to define the configuration file location. When not defined, Universal Database loads all configuration files from these locations by default:

* /etc/udb/udb.conf
* /etc/udb/udb.conf.d/*.conf

Configuration file syntax must define a key and a value. The key is case-sensitive, and you may use underscore (_) or dash (-) seemlessly. All lines beginning with '#' are comments and are intended for you to read. All other lines are configuration for udb.

E.g.:

    # This is a comment
    server_port=8081
    log_level=DEBUG

## Environment variables

In addition to configuration files, you may pass environment variables. The options name must be uppercase and prefixed with `UDB_`. As an example, if you want to change the port used to listen for HTTP request for 8081, you must define `server-port` option as follow.

    UDB_SERVER_PORT=8081

## Command line arguments

When launching `udb` executable, you may pass as many arguments as you want on the command line. The options must be prefixed with double dash (`--`) and you must single dash (-) to separate words.

E.g. `--server-port 8081` or `--server-port=8081` are valid

## Configure listening port and interface

For security reasons, Universal Database listen on port `8080` for HTTP request on loopback interface (127.0.0.1) by default. Consider configuring a reverse proxy like Nginx or Apache2 if you want to make Universal Database listen on port 80 for HTTP and port 443 for HTTPS request.

| Option | Description | Example |
| --- | --- | --- |
| server-host | Define the IP address to listen to. Use `0.0.0.0` to listen on all interfaces. Use `127.0.0.1` to listen on loopback interface. | 0.0.0.0 |
| server-port | Define the port to listen for HTTP request. Default to `8080` | 9090 |

## Configure External URL

To display the correct URL when sending email notification to UDB users,
you must provide it with the URL your users use to reach the web application.
You can use the IP of your server, but a Fully Qualified Domain Name (FQDN) is preferred.

| Option | Description | Example |
| --- | --- | --- |
| external-url | Define the base URL used to reach your Universal Database application | `https://udb.mycompagny.com` |

## Configure administrator username and password

Using configuration file, you may setup a special administrator which cannot be
deleted or renamed from the web interface. You may also configure a specific
password for this user that cannot be updated from the web interface either.

In addition, you may also create other administrator users to manage Universal Database.

| Parameter | Description | Example |
| --- | --- | --- |
| admin-user | Define the name of the default admin user to be created | admin |
| admin-password | administrator encrypted password as SSHA. Read online documentation to know more about how to encrypt your password into SSHA or use <http://projects.marsching.org/weave4j/util/genpassword.php> When defined, administrator password cannot be updated using the web interface. When undefined, default administrator password is `admin123` and it can be updated using the web interface. | modification |

## Configure logging

Universal Database can be configured to send logs to specific location. By default, logs are sent to the console (stdout or stderr). If you have installed Universal Database on a server, you should consider enabling the logging to help you keep track of the activities or to help you debug problem.

| Option | Description | Example |
| --- | --- | --- |
| log-level | Define the log level. ERROR, WARN, INFO, DEBUG | DEBUG |
| log-file | Define the location of the log file. | /var/log/udb/server.log |
| log-access-file | Define the location of the access log file. | /var/log/udb/access.log |

### Enable Debugging

A specific option is also available if you want to enable the debugging log. We do not recommend to enable this option in production as it may leak information to the user whenever an exception is raised.

| Option | Description |
| --- | --- |
| debug | enable UDB debug mode - change the log level to DEBUG, print exception stack trace to the web interface and show SQL query in logs. |

## Configure database

Universal Database use SQL database to store user preferences. The embedded SQLite database is well suited for small deployment (1-100 users). If you intended to have a large deployment, you must consider using a PostgreSQL database instead.

| Option | Description | Example |
| --- | --- | --- |
| database-uri | Location of the database used for persistence. SQLite and PostgreSQL database are supported officially. To use a SQLite database, you may define the location using a file path or a URI. e.g.: `/srv/udb/file.db` or `sqlite:///srv/udb/file.db`. To use PostgreSQL server, you must provide a URI similar to `postgresql://user:pass@10.255.1.34/dbname` and you must install required dependencies. By default, Universal Database uses a SQLite embedded database located at `/etc/udb/rdw.db`. | postgresql://user:pass@10.255.1.34/dbname |

### SQLite

To use embedded SQLite database, pass the option `database-uri` with a URI similar to `sqlite:///etc/udb/data.db` or `/etc/udb/data.db`.

### PostgreSQL

To use an external PostgreSQL database, pass the option `database-uri` with a URI similar to `postgresql://user:pass@10.255.1.34/dbname`.

You may need to install additional dependencies to connect to PostgreSQL. Step to install dependencies might differ according to the way you installed Universal Database.

**Using Debian repository:**

    apt install python3-psycopg2

**Using Pypi repository:**

    pip install psycopg2-binary

## Configure LDAP Authentication

Universal Database may integrates with LDAP server to support user authentication.

```{toctree}
---
titlesonly: true
---
configuration-ldap
```

## Configure User Session

A user session is a sequence of request and response transactions associated with a single user. The user session is the means to track each authenticated user.

| Option | Description | Example |
| --- | --- | --- |
| session-idle-timeout | This timeout defines the amount of time a session will remain active in case there is no activity in the session. User Session will be revoke after this period of inactivity, unless the user selected "remember me". Default 10 minutes. | 5 |
| session-absolute-timeout | This timeout defines the maximum amount of time a session can be active. After this period, user is forced to (re)authenticate, unless the user selected "remember me". Default 20 minutes. | 30 |
| session-persistent-timeout | This timeout defines the maximum amount of time to remember and trust a user device. This timeout is used when user select "remember me". Default 30 days | 43200 |

## Configure email notifications

You may configure Universal Database to send an email notification to the users for record they follow.

| Option | Description | Example |
| --- | --- | --- |
| smtp-encryption | Type of encryption to be used when establishing communication with SMTP server. Available values: `none`, `ssl` and `starttls` | starttls |
| smtp-server | SMTP server used to send email in the form `host`:`port`. If the port is not provided, default to standard port 25 or 465 is used. | smtp.gmail.com:587 |
| smtp-from | email addres used for the `From:` field when sending email. | Universal Database <example@gmail.com> |
| smtp-username | username used for authentication with the SMTP server. | example@gmail.com |
| smtp-password | password used for authentication with the SMTP server. | CHANGEME |
| notification-catch-all-email | When defined, all notification email will be sent to this email address using Blind carbon copy (Bcc) |

To configure the notification, you need a valid SMTP server. In this example, you are making use of a Gmail account to send emails.

    smtp-server=smtp.gmail.com:587
    smtp-encryption=starttls
    smtp-from=example@gmail.com
    smtp-username=example@gmail.com
    smtp-password=CHANGEME

Note: notifications are not sent if the user doesn't have an email configured in his profile.

## Configure Rate-Limit

Universal Database could be configured to rate-limit access to anonymous to avoid bruteforce
attacks and authenticated users to avoid Denial Of Service attack.

| Option | Description | Example |
| --- | --- | --- |
| rate-limit | maximum number of requests per hour that can be made on sensitive endpoints. When this limit is reached, an HTTP 429 message is returned to the user or the user is logged out. This security measure is used to limit brute force attacks on the login page and the RESTful API. | 20 |
| rate-limit-dir | location where to store rate-limit information. When undefined, data is kept in memory. | /var/lib/udb/session |

## Custom user's password length limits

By default, Universal Database encofrce minimal password score of 2.

Changing the minimum score does not affect existing users' passwords. Existing users are not prompted to reset their passwords to meet the new limits. The new limit only applies when an existing user changes their password.

| Option | Description | Example |
| --- | --- | --- |
| password-score      | Minimum zxcvbn's score for password. Value from 0 to 4. Default value 2. | 4 |

You may want to read more about [zxcvbn](https://github.com/dropbox/zxcvbn) score value.

## Configure default language

By default, the web application uses the HTTP Accept-Language headers to determine the best language to use for display. Users can also manually select a preferred language to use for all communication. The `default-lang` setting is used when the user has not selected a preferred language and none of the Accept-Language headers match a translation.

| Parameter | Description | Example |
| --- | --- | --- |
| --default-lang | default application locale. e.g.: `fr` | es |

## Configure default timezone

By default, the web application uses the browse timezone to display date and time. But when sending email, the server timezone is used by default. It's possible for the administrator to change the default timezone to be used.

It's also possible for users to changed their prefered timezone from the web interface.

| Parameter | Description | Example |
| --- | --- | --- |
| --default-timezone | default application timezone. uses server timezone by default. | America/toronto |
