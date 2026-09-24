"""Contains the dependencies between controls reading each other's results.

A control whose datasource is the result table of another control is a
chain-rule: every run of it first runs that upstream control for the same
window, and reads only the records the upstream run saved. The dependency is
never configured, it is the datasource name itself, and this module is the
only place that knows how such a name is recognized.
"""

import json

import sqlalchemy as sa

from ..database import db


RESULT_PREFIXES = ('rapo_rest_', 'rapo_resa_', 'rapo_resb_')


def source_fields(control_type):
    """Get the datasource fields of a control type with the side they feed.

    Returns
    -------
    fields : list
        Pairs of the rapo_config column and the side (None, 'a' or 'b').
    """
    if control_type in ('ANL', 'REP'):
        return [('source_name', None)]
    if control_type in ('REC', 'CMP'):
        return [('source_name_a', 'a'), ('source_name_b', 'b')]
    return []


def written_tables(row):
    """Get the result tables a control of this configuration writes."""
    name = (row.get('control_name') or '').lower()
    control_type = row.get('control_type')
    if control_type in ('ANL', 'CMP', 'REP'):
        return [f'rapo_rest_{name}']
    tables = []
    if control_type == 'REC':
        if row.get('need_a') == 'Y':
            tables.append(f'rapo_resa_{name}')
        if row.get('need_b') == 'Y':
            tables.append(f'rapo_resb_{name}')
    return tables


def upstream_of(source_name, names):
    """Get the name of the control whose result table the datasource is.

    Only a plain name of the own schema counts: an owner-qualified, linked or
    {variable} name is an ordinary datasource.

    Parameters
    ----------
    source_name : str or None
        Datasource name as configured.
    names : iterable
        Names of the existing controls.

    Returns
    -------
    name : str or None
        Control name as it is stored, or None when it is no result table.
    """
    if not source_name or not isinstance(source_name, str):
        return None
    table = source_name.strip().lower()
    if any(char in table for char in '.@{}'):
        return None
    for prefix in RESULT_PREFIXES:
        if table.startswith(prefix):
            rest = table[len(prefix):]
            for name in names:
                if name and name.lower() == rest:
                    return name
    return None


def upstreams(row, names):
    """Get the controls whose result tables a configuration reads.

    Returns
    -------
    upstreams : list
        Dictionaries with the side, the upstream control name and the table.
    """
    items = []
    for field, side in source_fields(row.get('control_type')):
        source_name = row.get(field)
        name = upstream_of(source_name, names)
        if name:
            items.append({'side': side, 'field': field,
                          'control_name': name,
                          'table': source_name.strip().lower()})
    return items


def read_rows():
    """Get the configuration columns the dependencies are built from."""
    config = db.tables.config
    columns = [config.c.control_id, config.c.control_name,
               config.c.control_type, config.c.source_name,
               config.c.source_name_a, config.c.source_name_b,
               config.c.need_a, config.c.need_b, config.c.schedule_config]
    select = sa.select(*columns)
    return db.execute(select, as_table=True)


def read_names():
    """Get the names of all controls."""
    return [row['control_name'] for row in read_rows()]


def dependents(name, rows=None):
    """Get the controls reading a result table of the given control.

    Returns
    -------
    dependents : list
        Dictionaries with the dependent row and its upstream items.
    """
    rows = read_rows() if rows is None else rows
    names = [row['control_name'] for row in rows]
    found = []
    for row in rows:
        items = [item for item in upstreams(row, names)
                 if item['control_name'] == name]
        if items:
            found.append({'row': row, 'items': items})
    return found


def _trigger_id(row):
    schedule_config = row.get('schedule_config')
    if not schedule_config:
        return None
    try:
        if isinstance(schedule_config, str):
            schedule_config = json.loads(schedule_config)
        return schedule_config.get('trigger_id')
    except (ValueError, AttributeError):
        return None


def renamed_source(source_name, new_name):
    """Get a datasource name pointing to the renamed upstream control."""
    stripped = source_name.strip()
    prefix = stripped[:len(RESULT_PREFIXES[0])]
    renamed = f'{prefix}{new_name}'
    return renamed.upper() if stripped.isupper() else renamed.lower()


def validate(row, previous_name=None):
    """Check the dependencies a configuration about to be saved would make.

    Parameters
    ----------
    row : dict
        The rapo_config columns being saved.
    previous_name : str or None
        The stored name of the control when it is saved under a new one.

    Returns
    -------
    renames : list
        Dependent controls whose datasource must follow the rename, as
        dictionaries with the control ID, name and the new column values.

    Raises
    ------
    ValueError
        When the configuration reads its own results, a table its upstream
        does not write, pulls an upstream it is also cascaded from, or
        closes a cycle.
    """
    name = row.get('control_name')
    control_id = row.get('control_id')
    stored = [other for other in read_rows()
              if not (control_id and other['control_id'] == control_id)
              and other['control_name'] != name]

    renames = []
    if previous_name and name and previous_name != name:
        # Matched against the stored name, which no control has any more.
        for dependent in dependents(previous_name, stored+[{
            'control_name': previous_name
        }]):
            other = dependent['row']
            values = {item['field']: renamed_source(other[item['field']],
                                                    name)
                      for item in dependent['items']}
            renames.append({'control_id': other['control_id'],
                            'control_name': other['control_name'],
                            'values': values})
    renamed = {item['control_id']: item['values'] for item in renames}
    stored = [{**other, **renamed.get(other['control_id'], {})}
              for other in stored]

    rows = stored+[row]
    by_name = {other['control_name']: other for other in rows}
    names = list(by_name)

    own_tables = [f'{prefix}{(name or "").lower()}'
                  for prefix in RESULT_PREFIXES]
    for field, _ in source_fields(row.get('control_type')):
        source_name = row.get(field)
        if source_name and source_name.strip().lower() in own_tables:
            raise ValueError(f'Control {name} can not read its own result '
                             f'table {source_name.strip().upper()}.')

    for item in upstreams(row, names):
        upstream = by_name[item['control_name']]
        if item['table'] not in written_tables(upstream):
            raise ValueError(f'Control {item["control_name"]} does not write '
                             f'the table {item["table"].upper()} that '
                             f'{name} reads.')

    trigger_id = _trigger_id(row)
    if trigger_id:
        for upstream_name in all_upstreams(name, rows):
            if by_name[upstream_name].get('control_id') == trigger_id:
                raise ValueError(f'Control {name} runs {upstream_name} first '
                                 'anyway, so it can not also be cascaded '
                                 'from it.')

    for dependent in dependents(name, rows):
        other = dependent['row']
        if other is row:
            continue
        for item in dependent['items']:
            if item['table'] not in written_tables(row):
                raise ValueError(f'Control {other["control_name"]} reads '
                                 f'{item["table"].upper()}, which {name} '
                                 'would no longer write.')

    cycle = find_cycle(name, rows)
    if cycle:
        raise ValueError('Controls would read each other\'s results in a '
                         f'cycle: {" -> ".join(cycle)}.')
    return renames


def all_upstreams(name, rows):
    """Get every control a run of the given one runs first, at any depth."""
    names = [row['control_name'] for row in rows]
    by_name = {row['control_name']: row for row in rows}
    found, pending = [], [name]
    while pending:
        current = pending.pop()
        for item in upstreams(by_name.get(current, {}), names):
            upstream = item['control_name']
            if upstream not in found and upstream != name:
                found.append(upstream)
                pending.append(upstream)
    return found


def find_cycle(name, rows):
    """Get the dependency cycle the given control is part of, if any."""
    names = [row['control_name'] for row in rows]
    graph = {row['control_name']: [item['control_name']
                                   for item in upstreams(row, names)]
             for row in rows}
    path, done = [], set()

    def visit(current):
        if current in path:
            return path[path.index(current):]+[current]
        if current in done:
            return None
        path.append(current)
        for upstream in graph.get(current, []):
            found = visit(upstream)
            if found:
                return found
        path.pop()
        done.add(current)
        return None

    return visit(name)
