# Change Log

## Next Release

* Enforce 'Origin' validation to counter CSRF and XSS
* Add ratelimit protection on sensitive endpoints
* Enforce strong password with zxcvbn
* Enforce field limit in wtform validation
* Implement POST, REDIRECT, GET in user profile
* Update Content-Security-Policy
* Update auth_form
* Remove deprecated auth_basic module
* Define proper proxy settings for best security #67
* Avoid leaking stacktrace when running in production mode #67
* Define default security headers #67
* Redirect user to same page after edit
* Complete datatable changes
* Support VRF Records
* Enabled `cherrypy.tools.proxy` to support reverse proxy #65
* Use datatables library to display tables #48 #66
* Provide default log configuration for debian package
* Change package name
* Update db module plugins
* Cosmetic changes
* Allow Administrators to define or remove user's password #51
* Provide a default page for /api/
* Provide a default configfile #52
* Update db Base class
* Make IP View a custom template
* Ad scalar_subquery to remove sqlalchemy warning
* Redirect user to previous page after editing #22
* Define inherit_cache for cidr
* Fix URL in notifications view
* Define default image to upload deb
* Define a timestamp decorator to handle timezone
* Add a dashboard page #26
* Add related_subnets to IP View #39
* Add logo to login page
* Add `cc` to smtp module
* Avoid editing status using HTTP GET method
* Avoid editing followers using HTTP GET
* Fix open redirect in login page #45
* Add .vscode to gitignore
* Validate PTR Record using DNS Zone #37
* Reffactoring reverse_ip as hybrid_property
* Exclude deleted records from relation to IP #42
* Exclude generated templates from sonar
* Fix to support email-validator v1.2.0
* Move display_name to jinja2 templates
* Add a view to list all subscriptions #40
* Add catch-all email to configuration #44
* Add alt to image logo
* Make email template compliant
* Add aria-describedby to table
* Add aria-hidden="true" to icons
* Fix notification
* Add catch-all email to configuration #44
* Fetch email and fullname attributes from LDAP #43
* Send notification to followers #15
* Update Copyright year
* Replace font awsome by bootstrap-icons #24 #34
* Fix sonar coverage
* Add full text search #28
* Fix test for postgresql database
* Make tables sortable #30
* Run test during Debian Packaging using pytest
* Add DNS Zone / Subnet / Dns Record validation #21
* Validate if subnet creation conflict with other existing subnet #9
* Add isort and black to project
* Configuring setup() using setup.cfg files
* Update sidebar
* Complete user managements
* Implement LDAP authentication #4
* Add new plugins to the project
* Add user managements #27
* Include PTR record ipv4 and ipv6 in IP View
* Make database-uri configurable #25 #33
* Add specific PTR record validation #31
* Add audit log on record creation #29
* Complete IP View changes #7
* Provide a Debian package #14
* Add IP View with related records #7
* Add all the required DNS record type #19
* Add Many-to-Many dnszone and subnet #18
* Add basic favicon #11
* Fix history when owner is updated #13
* Use a single table for messages
* Use a single table for followers
* Adjust CSS Layout
* Fix "Not Assigned" owner #20
* Fix enabled state #17
* Rename application from CMDB to UDB
* Creatre RESTful API for CRUD operation #8
* Working version
* Re-implement navigation using sidebar
* Adding more unit test
* Add more record type with test and validation
* Implement basic view to add,edit record
* Update SQLAlchemy integration
* Complete project skeleton & creating login page #3
* Fix test error and flake8
