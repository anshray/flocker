# Copyright Hybrid Logic Ltd.  See LICENSE file for details.
"""
A top level flocker command.
"""

import click

from . import __version__

@click.command()
@click.help_option()
@click.version_option(version=__version__)
def flocker():
    click.echo()
