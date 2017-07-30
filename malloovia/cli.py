#!/usr/bin/env python
"""Command line interface to Malloovia."""
import time
import yaml
from jsonschema import validate
import click
from pulp import COIN

from . import __version__
from .util import (
    get_schema, preprocess_yaml, read_problems_from_yaml,
    solutions_to_yaml
)
from .phases import (
    PhaseI, PhaseII
)

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
@click.option(
    '--verbose', is_flag=True, default=False, show_default=True,
    help='Show the full exception message on failure'
)
@click.argument(
    'filenames', type=click.Path(exists=True), nargs=-1, required=True
)
def validate_multiple_yaml_files(filenames, partial, problems_only, verbose):
    "Validates yaml files"
    if problems_only:
        kind = "problems"
    else:
        kind = None
    for filename in filenames:
        try:
            validate_yaml_file(filename, partial, kind)
        except Exception as excep:
            if not verbose and hasattr(excep, "message"):
                msg = excep.message
            else:
                msg = str(excep)
            click.secho("{} does not validate ({})".format(filename, msg),
                        fg="red")
        else:
            click.secho("{} is correct".format(filename),
                        fg="green")


@cli.command("phase_i")
@click.argument(
    'problems_file', type=click.Path(exists=True), nargs=1)
@click.argument(
    'problem_id', type=str)
@click.argument(
    'output_file', type=click.File("w"), nargs=1)
@click.option(
    '--frac-gap', type=float, default=None,
    help="Use cbc solver with given fracGap"
)
@click.option(
    '--max-seconds', type=float, default=None,
    help="Use cbc solver with given maxSeconds"
)
@click.option(
    '--threads', type=int, default=None,
    help="Use cbc solver with given number of threads"
)
def solve_phase_i(problems_file, problem_id, output_file, frac_gap,
                  max_seconds, threads):
    "Solves phase I of a given problem"

    click.echo("Reading {}...".format(problems_file), nl=False)
    t_ini = time.process_time()
    problem = read_problems_from_yaml(problems_file)[problem_id]
    click.echo("({}s)".format(time.process_time()-t_ini))

    if any(option is not None for option in (frac_gap, max_seconds, threads)):
        solver = COIN(fracGap=frac_gap, maxSeconds=max_seconds, threads=threads)
    else:
        solver = None

    click.echo("Solving phase I...", nl=False)
    t_ini = time.process_time()
    solution = PhaseI(problem).solve(solver=solver)
    click.echo("({}s)".format(time.process_time()-t_ini))

    click.echo("Writing solution in {}...".format(output_file.name), nl=False)
    t_ini = time.process_time()
    output = solutions_to_yaml([solution])
    output_file.write(output)
    click.echo("({}s)".format(time.process_time()-t_ini))

if __name__ == "__main__":
    cli()
