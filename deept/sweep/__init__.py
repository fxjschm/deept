import re

from cool_config import CoolConfig

from deept.utils.log import value_to_str
from deept.sweep.sweeper import SearchSweeper, ComparativeSweeper
from deept.sweep.strategies import create_sweep_strategy_from_config
from deept.sweep.parsing import parse_repeat_for_value, parse_sweep_parameters


IDENT_KEY_VALUE_SEPARATOR = '__'
IDENT_PARAM_SEPARATOR = '___'
_IDENT_UNSAFE_CHARS = re.compile(r'[\s/*?\[\]]')
_LEGACY_IDENT_PART = re.compile(r'[A-Za-z]\w*_[^_]+')


def config_to_ident(config):
    """{'seed': 0, 'lambda_clustering': 0.1, 'extraordinary_dwn': [80, 160]} ->
    'extraordinary_dwn__80_160___lambda_clustering__0.10___seed__0000'."""
    str_config = {
        name: str(value_to_str(value, no_precise=False))
        for name, value in sorted(config.items(), key=lambda item: item[0])
    }
    ident = IDENT_PARAM_SEPARATOR.join(
        f'{name}{IDENT_KEY_VALUE_SEPARATOR}{value}' for name, value in str_config.items()
    )

    try:
        round_trips = ident_to_config(ident) == str_config
    except ValueError:
        round_trips = False

    if not round_trips or _IDENT_UNSAFE_CHARS.search(ident):
        raise ValueError(
            f'Cannot encode sweep config {str_config} as run_ident (got "{ident}")! '
            f'It must parse back unchanged (no "{IDENT_KEY_VALUE_SEPARATOR}" in names, no '
            f'"{IDENT_PARAM_SEPARATOR}" anywhere, no leading or trailing "_") and must not '
            f'contain whitespace, "/" or any of "*?[]".'
        )

    return ident

def ident_to_config(ident):
    """Inverse of config_to_ident: 'lambda_clustering__0.10___seed__0000' ->
    {'lambda_clustering': '0.10', 'seed': '0000'}."""
    if not ident:
        return {}

    config = {}

    legacy_parts = ident.split('__')
    if all(_LEGACY_IDENT_PART.fullmatch(part) for part in legacy_parts):
        for part in legacy_parts:
            name, _, value = part.rpartition('_')
            config[name] = value
        return config

    for pair in ident.split(IDENT_PARAM_SEPARATOR):
        name, separator, value = pair.partition(IDENT_KEY_VALUE_SEPARATOR)
        if not separator or not name:
            raise ValueError(f'Malformed run_ident "{ident}": cannot split "{pair}" into name and value!')
        config[name] = value

    return config

def create_sweeper_from_config(config, sweep_fn, sweep_fn_args):
    shared_kwargs = build_shared_sweeper_kwargs(config, sweep_fn, sweep_fn_args)

    if isinstance(shared_kwargs['sweep_parameters'], list):
        return create_comparative_sweeper_from_config(config, shared_kwargs)
    elif isinstance(shared_kwargs['sweep_parameters'], CoolConfig):
        return create_search_sweeper_from_config(config, shared_kwargs)
    else:
        raise ValueError(
            f'Sweep config "parameters" must be either a list or a dict!'
            f'Note that depending on what it is the behavior of the sweeper differs.'
        )

def build_shared_sweeper_kwargs(config, sweep_fn, sweep_fn_args):
    do_multi_sweep, multi_sweep_kwargs = parse_multi_sweep_config(config)

    repeat_for = config['sweep_configuration/repeat_for', None]
    if repeat_for is not None:
        repeat_for = parse_repeat_for_value(config, repeat_for)
    else:
        repeat_for = []

    shared_kwargs = dict(
        normal_config=config,
        function=sweep_fn,
        function_args=sweep_fn_args,
        best_indicator=config['best_checkpoint_indicator'],
        best_goal=config['best_checkpoint_indicator_goal'],
        sweep_name=config[
            'sweep_configuration/sweep_name',
            config['sweep_configuration/multi_sweep/sweep_name', None]
        ],
        output_folder_root=config['output_folder'],
        constraints=config['sweep_configuration/constraints', None],
        sweep_parameters=config['sweep_configuration/parameters'],
        run_dry=config['run_dry', False],
        repeat_for_configs=repeat_for,
        do_multi_sweep=do_multi_sweep,
        **multi_sweep_kwargs
    )

    if shared_kwargs['sweep_name'] is None:
        raise ValueError('Missing sweep_name in sweep config!')

    return shared_kwargs

def parse_multi_sweep_config(config):
    do_multi_sweep = config['sweep_configuration/activate_multi_sweep', False]
    multi_sweep_kwargs = {
        'sweep_folder_root': None,
        'hash_config': None,
        'cleanup_after': None,
        'remove_from_hash': None,
        'restart_error_runs': None,
    }

    if do_multi_sweep:
        multi_sweep_kwargs['sweep_folder_root'] = config['sweep_configuration/multi_sweep/sweep_folder_root']
        multi_sweep_kwargs['hash_config'] = config['sweep_configuration/multi_sweep/hash_config', True]
        multi_sweep_kwargs['cleanup_after'] = config['sweep_configuration/multi_sweep/cleanup_after', 86]
        multi_sweep_kwargs['remove_from_hash'] = config['sweep_configuration/multi_sweep/remove_from_hash', []]
        multi_sweep_kwargs['restart_error_runs'] = config['sweep_configuration/multi_sweep/restart_error_runs', False]

    return do_multi_sweep, multi_sweep_kwargs

def create_comparative_sweeper_from_config(config, shared_kwargs):
    import random
    from copy import deepcopy

    configs_to_compare = deepcopy(shared_kwargs['sweep_parameters'])

    if config['shuffle_parameters_randomly', True]:
        random.Random(0).shuffle(configs_to_compare)

    comparative_kwargs = dict(
        configs_to_compare=configs_to_compare
    )

    return ComparativeSweeper(
        comparative_kwargs,
        **shared_kwargs
    )

def create_search_sweeper_from_config(config, shared_kwargs):
    param_options, num_combinations = parse_sweep_parameters(
        shared_kwargs['sweep_parameters']
    )

    sweep_strat = create_sweep_strategy_from_config(config)

    search_kwargs = dict(
        sweep_strat=sweep_strat,
        param_options=param_options,
        num_combinations=num_combinations,
        max_count=config['sweep_configuration/count'],
    )

    return SearchSweeper(
        search_kwargs,
        **shared_kwargs
    )
