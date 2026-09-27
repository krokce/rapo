"""Contains the datasources of the PDI Core file-loading framework.

PDI Core (Pentaho) loads the files waiting in input directories into tables,
configured by two tables that belong to that framework and not to rapo:

    pdi_core_ds_config  one row per datasource: input directories, file mask,
                        scheduler lane (isactive), archive directories, ...
    pdi_core_ds_tables  the tables of a datasource and their partition
                        retention, by sourceid

and logs every file it loads in pdi_core_file_log. They are optional: an
installation without them gets no Datasources page.
"""

from .store import pdi, DatasourceError
from .files import scanner

__all__ = ['pdi', 'scanner', 'DatasourceError']
