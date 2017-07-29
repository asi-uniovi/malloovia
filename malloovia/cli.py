#!/usr/bin/env python
"""Script to validate the syntax of a YAML file"""
import yaml
from jsonschema import (validate, Draft4Validator, exceptions)
from . import __version__
from .util import (
    get_schema, preprocess_yaml
)
import click

def validate_yaml_file(filename, partial=False, kind=None):
    """Validates yaml problem or solution against malloovia schema.

    Args:
        filename: yaml file to validate.
        partial: True if the file contains only part of a problem
            This uses an alternative schema in which all properties
            are optional, and is useful to validate individual properties.
    Returns:
        True if the file passes the validation test.
    Raises:
        TypeError: if some validation fails.
    """
    malloovia_schema = get_schema()
    if partial:
        malloovia_schema.pop("oneOf")
    if kind == "problems":
        malloovia_schema.pop("oneOf")
        malloovia_schema['required'] = (
            "Apps Limiting_sets Instance_classes Performances Workloads Problems".split()
        )
    yaml_content = preprocess_yaml(filename)
    data = yaml.safe_load(yaml_content)
    validate(data, malloovia_schema)



@click.group()
@click.version_option(__version__)
def cli():
    "Mallovia command line interface"
    pass

@cli.command("validate")
@click.option(
    '--partial', is_flag=True, default=False, show_default=True,
    help='The file to test is not complete'
)
@click.option(
    '--problems-only', is_flag=True, default=False, show_default=True,
    help='The file contains only problems'
)
@click.argument(
    'filenames', type=click.Path(exists=True), nargs=-1, required=True
)
def validate_multiple_yaml_files(filenames, partial, problems_only):
    "Validates yaml files"
    if problems_only:
        kind="problems"
    else:
        kind=None
    for filename in filenames:
        try:
            validate_yaml_file(filename, partial, kind)
        except Exception as e:
            if hasattr(e, "message"):
                msg = e.message
            else:
                msg = str(e)
            click.secho("{} does not validate ({})".format(filename, msg),
                        fg="red")
        else:
            click.secho("{} is correct".format(filename),
                        fg="green")


@cli.command("solve")
@click.argument(
    'problems_file', type=click.Path(exists=True), nargs=1)
@click.argument(
    'problem_id', type=str)
@click.option(
    '--phase-i-only', is_flag=True, default=False
)
def solve_problem(problems_file, problem_id, phase_i_only):
    "Solves problems"
    click.echo("Not implemented yet!")






if __name__ == "__main__":
    cli()