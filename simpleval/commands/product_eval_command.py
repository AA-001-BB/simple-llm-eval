from pathlib import Path

import click

from simpleval.utilities.error_handler import handle_exceptions


@click.group(name='product-eval', help='Evaluate and compare structured AI product outputs')
def product_eval():
    pass


@product_eval.command(name='run', help='Run deterministic structured-output evaluation')
@click.option('--dataset', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--outputs', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--out', 'output_dir', required=True, type=click.Path(file_okay=False, path_type=Path))
@handle_exceptions
def run_product_eval(dataset: Path, outputs: Path, output_dir: Path):
    from simpleval.product_eval.runner import run_evaluation

    run = run_evaluation(dataset_path=dataset, outputs_path=outputs, output_dir=output_dir)
    click.echo(
        f'Evaluated {run.summary.total} cases: {run.summary.passed} passed, '
        f'{run.summary.failed} failed, mean score {run.summary.mean_score:.4f}'
    )
    click.echo(f'Artifacts: {output_dir.resolve()}')


@product_eval.command(name='compare', help='Compare two deterministic product-eval runs')
@click.option('--baseline', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--candidate', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--out', 'output_dir', required=True, type=click.Path(file_okay=False, path_type=Path))
@handle_exceptions
def compare_product_eval(baseline: Path, candidate: Path, output_dir: Path):
    from simpleval.product_eval.comparison import compare_evaluation_runs

    comparison = compare_evaluation_runs(baseline_path=baseline, candidate_path=candidate, output_dir=output_dir)
    click.echo(
        f'Compared {comparison.summary.total} cases: {comparison.summary.improved} improved, '
        f'{comparison.summary.regressed} regressed, {comparison.summary.unchanged} unchanged'
    )
    click.echo(f'Artifacts: {output_dir.resolve()}')
    if comparison.summary.regressed:
        raise click.exceptions.Exit(1)
