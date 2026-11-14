# Templates for the generated API client

`generate-client.sh` passes this directory to openapi-python-client as
`--custom-template-path`. Each file here replaces the generator's own template
of the same name; everything else is generated as usual.

## Enums that tolerate new values

Playout reads the API with a client generated from the schema pinned in this
repo, and the API moves ahead of it. The generator's enums reject any value
they don't list, and the error sinks the whole object it sits in. On
2026-11-14 the API started listing HLS files, and a file variant playout had
never heard of kept every new programme off air for six hours.

`str_enum.py.jinja` and `int_enum.py.jinja` add a `_missing_` hook, Python's
own way to let an `Enum` accept a value it doesn't list. Such a value comes
back as an extra member named `UNKNOWN` whose `.value` is what the API sent.
Known values are unchanged, so code that compares against the members keeps
working, and an unknown value simply never matches.

Values of the wrong type (a number where a string belongs) still fail: that
is a real change to the API, not a new choice.
