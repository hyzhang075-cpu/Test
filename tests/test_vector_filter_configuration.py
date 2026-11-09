"""Command-line and constructor contract for vector direction filtering."""

import argparse
import ast
import inspect
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).parents[1]


def _load_main_argument_helpers():
    tree = ast.parse((ROOT / 'main.py').read_text(encoding='utf-8'))
    wanted = {'_str2bool', 'add_vector_filter_arguments'}
    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    namespace = {'argparse': argparse}
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<main argument helpers>', 'exec'), namespace)
    return namespace


def test_main_vector_filter_defaults_off_and_accepts_explicit_true():
    helpers = _load_main_argument_helpers()
    parser = argparse.ArgumentParser()
    helpers['add_vector_filter_arguments'](parser)

    assert parser.parse_args([]).move_filter_for_vector is False
    assert parser.parse_args(['--move_filter_for_vector', 'True']).move_filter_for_vector is True


def test_reconstructor_vector_filter_constructor_default_is_off():
    tree = ast.parse((ROOT / 'reconstructor.py').read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Reconstructor')
    init = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '__init__')
    cls.body = [init]
    cls.bases = []
    namespace = {}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), '<reconstructor constructor>', 'exec'), namespace)

    default = inspect.signature(namespace['Reconstructor'].__init__).parameters['move_filter_for_vector'].default
    assert default is False


def test_reconstructor_preserves_existing_positional_parameter_order():
    tree = ast.parse((ROOT / 'reconstructor.py').read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Reconstructor')
    init = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '__init__')
    cls.body = [init]
    cls.bases = []
    namespace = {}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), '<reconstructor constructor>', 'exec'), namespace)

    parameters = list(inspect.signature(namespace['Reconstructor'].__init__).parameters)
    assert parameters[-8:] == [
        'move_filter', 'kalman_params', 'curvature_interp',
        'nonnegative_curvature', 'args', 'move_filter_for_vector',
        'multi_region_parameters', 'kwargs',
    ]


def test_main_forwards_explicit_vector_filter_value_to_optimiser(monkeypatch):
    sys.path.insert(0, str(ROOT))
    import main

    received = {}

    class StopAfterOptimiser(Exception):
        pass

    def capture_optimiser(**kwargs):
        received.update(kwargs)
        raise StopAfterOptimiser

    monkeypatch.setattr(main, 'Optimiser', capture_optimiser)
    monkeypatch.setattr(
        sys,
        'argv',
        ['main.py', '--task', 'init', '--move_filter_for_vector', 'True'],
    )
    with pytest.raises(StopAfterOptimiser):
        main.main()

    assert received['move_filter_for_vector'] is True
