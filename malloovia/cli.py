#!/usr/bin/env python
"""Command line interface to Malloovia."""
import time
import traceback
import os.path
import ruamel.yaml  # type: ignore
from jsonschema import validate  # type: ignore
import click
from pulp import COIN  # type: ignore
from progress.bar import ShadyBar  # type: ignore

from . import __version__
from .util import (
    get_schema,
    preprocess_yaml,
    read_problems_from_yaml,
    solutions_to_yaml,
)
from .phases import PhaseI, PhaseII, OmniscientSTWPredictor

yaml = ruamel.yaml.YAML(typ="safe")
yaml.safe_load = yaml.load


class OmniscientProgressSTWPredictor(OmniscientSTWPredictor):
    """Adds a progress bar to an OmniscientSTWPredictor"""

    def __iter__(self):
        progress_bar = ShadyBar(
            "Solving Phase II",
            max=self.timeslots / 10,
            width=60,
            suffix="%(percent).1f%% - ETA: %(eta_td)s",
        )
        count = 0
        for k in OmniscientSTWPredictor.__iter__(self):
            yield k
            count = (count + 1) % 10
            if count == 0:
                progress_bar.next()
        progress_bar.finish()


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
        malloovia_schema[
            "required"
        ] = "Apps Limiting_sets Instance_classes Performances Workloads Problems".split()
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
    "--partial",
    is_flag=True,
    default=False,
    show_default=True,
    help="The file to test is not complete",
)
@click.option(
    "--problems-only",
    is_flag=True,
    default=False,
    show_default=True,
    help="The file contains only problems",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    show_default=True,
    help="Show the full exception message on failure",
)
@click.argument("filenames", type=click.Path(exists=True), nargs=-1, required=True)
def validate_multiple_yaml_files(filenames, partial, problems_only, verbose):
    "Validates yaml files"
    if problems_only:
        kind = "problems"
    else:
        kind = None
    for filename in filenames:
        try:
            validate_yaml_file(filename, partial, kind)
        except Exception as excep:  # pylint:disable=broad-except
            if hasattr(excep, "message"):
                msg = excep.message  # pylint:disable=no-member
            else:
                msg = str(excep)
            if verbose:
                traceback.print_exc()
            else:
                click.secho("{} does not validate ({})".format(filename, msg), fg="red")
        else:
            click.secho("{} is correct".format(filename), fg="green")


@cli.command("solve")
@click.argument(
    # Name of the file containing the infrastructure and problems description
    "problems_file",
    type=click.Path(exists=True),
    nargs=1,
)
@click.option(
    "--phase-i-id",
    "-1",
    type=str,
    nargs=1,
    help="Id of the problem to be solved by Phase I solver",
)
@click.option(
    "--phase-ii-id",
    "-2",
    type=str,
    help=(
        "Id of the problem to be solved by Phase II solver, using reserved "
        "allocation found by Phase I solver"
    ),
)
@click.option(
    "--output-file",
    "-o",
    type=str,
    help=(
        "Name of the output (solutions) file. Defaults to the same name "
        "than problems_file, with -sol suffix."
    ),
)
@click.option(
    "--frac-gap-phase-i",
    type=float,
    default=None,
    help="Use cbc solver with given fracGap, only for phase I",
)
@click.option(
    "--frac-gap-phase-ii",
    type=float,
    default=None,
    help="Use cbc solver with given fracGap, only for phase II",
)
@click.option(
    "--frac-gap",
    type=float,
    default=None,
    help="Use cbc solver with given fracGap, both for phase I and II",
)
@click.option(
    "--max-seconds",
    type=float,
    default=None,
    help="Use cbc solver with given maxSeconds, both for phase I and II",
)
@click.option(
    "--threads",
    type=int,
    default=None,
    help="Use cbc solver with given number of threads, both for phase I and II",
)
def solve(
    problems_file,
    phase_i_id,
    phase_ii_id,
    output_file,
    frac_gap_phase_i,
    frac_gap_phase_ii,
    frac_gap,
    max_seconds,
    threads,
):
    "Solves phase I and optionally phase II of given problems"

    if phase_i_id is None:
        click.echo("--phase-i-id option is required")
        return

    click.echo("Reading {}...".format(problems_file), nl=False)
    t_ini = time.process_time()
    problems = read_problems_from_yaml(problems_file)
    click.echo("({:.3f}s)".format(time.process_time() - t_ini))

    if phase_i_id not in problems:
        click.echo("Problem id '{}' not found".format(phase_i_id))
        return

    prob1 = problems[phase_i_id]

    if phase_ii_id is not None and phase_ii_id not in problems:
        click.echo("Problem id '{}' not found".format(phase_ii_id))
        return
    if phase_ii_id is not None:
        prob2 = problems[phase_ii_id]
    else:
        prob2 = None

    if frac_gap_phase_i is None and frac_gap is not None:
        frac_gap_phase_i = frac_gap
    if frac_gap_phase_ii is None and frac_gap is not None:
        frac_gap_phase_ii = frac_gap
    if any(option is not None for option in (frac_gap_phase_i, max_seconds, threads)):
        solver = COIN(fracGap=frac_gap_phase_i, maxSeconds=max_seconds, threads=threads)
    else:
        solver = None

    click.echo("Solving phase I...", nl=False)
    t_ini = time.process_time()
    solution1 = PhaseI(prob1).solve(solver=solver)
    click.echo("({:.3f}s)".format(time.process_time() - t_ini))
    solutions = [solution1]

    if prob2:
        if any(
            option is not None for option in (frac_gap_phase_ii, max_seconds, threads)
        ):
            solver = COIN(
                fracGap=frac_gap_phase_ii, maxSeconds=max_seconds, threads=threads
            )
        else:
            solver = None
        click.echo("Solving phase II...", nl=False)
        t_ini = time.process_time()
        progress_predictor = OmniscientProgressSTWPredictor(prob2.workloads)
        solution2 = PhaseII(prob2, solution1, solver=solver).solve_period(
            progress_predictor
        )
        click.echo("({:.3f}s)".format(time.process_time() - t_ini))
        solutions.append(solution2)

    if output_file is None:
        root, ext = os.path.splitext(problems_file)
        if ext == ".gz":
            root, ext = os.path.splitext(root)
        output_file = str(root) + "-sol" + str(ext)
    click.echo("Writing solutions in {}...".format(output_file), nl=False)
    t_ini = time.process_time()
    output = solutions_to_yaml(solutions)
    with open(output_file, "w") as out_f:
        out_f.write(output)
    click.echo("({:.3f}s)".format(time.process_time() - t_ini))


if __name__ == "__main__":
    cli()
