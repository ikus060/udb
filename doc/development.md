# Development

This section provide details for those who want to contributes to the development.

## Translation

Reference <http://babel.edgewall.org/wiki/Documentation/setup.html>

UDB may be translated using `.po` files. This section describe briefly
how to translate UDB. It's not a complete instruction set, it's merely a reminder.

Extract the strings to be translated:

    tox -e babel_extract

Create a new translation:

    tox -e babel_init --local fr

Update an existing translation:

    tox -e babel_update --local fr

Compile all existing translation:

    tox -e babel_compile

## Running tests

Universal Database is provided with unit tests. To run them, execute a command similar to the following:

    tox -e py3

## Documentation

To generate documentation run `tox -e doc`.

It generates HTML documentation in folder `dist/html`

