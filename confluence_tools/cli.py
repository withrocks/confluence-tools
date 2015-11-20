import click
from confluence_tools.main import ConfluenceProvider
import os
import json
import yaml
import logging


@click.group()
@click.option('--loglevel')
@click.option('--whatif/--not-whatif', default=False)
@click.option("--config", help="Path to a config file that supplies any of [url, user, pwd, space]")
@click.option("--url", help="URL of your Confluence instance")
@click.option('--user')
@click.option('--pwd')
@click.pass_context
def cli(ctx, loglevel, whatif, config, url, user, pwd):
    if loglevel:
        logging.basicConfig(level=loglevel)

    if config:
        with open(config) as f:
            config_obj = yaml.load(f)
            url = url or config_obj["url"]
            user = user or config_obj["user"]
            pwd = pwd or config_obj["pwd"]

    if not url or not user or not pwd:
        raise click.UsageError("Missing some of url, user, pwd either on cmd line or in config")

    ctx.obj["url"] = url
    ctx.obj["user"] = user
    ctx.obj["pwd"] = pwd
    ctx.obj["whatif"] = whatif

    if whatif:
        print "*** Running in whatif mode. No writes. ***"


@cli.command("space-report",
             help="Generate a metadata file with page versions for a space. Generates a diff report " +
                  "if a previous metadata file is supplied")
@click.argument("current")
@click.argument("space")
@click.option("--previous",
              help="The previous version of the documentation/software. If provided, generates " +
                   "a report of the changes under a page called 'Version History', which needs to exist in the space.")
@click.option("--path", default=".", help="Path where metadata files will be read from/written to")
@click.pass_context
def space_report(ctx, current, space, previous, path):
    """
    Creates a metadata file for the current state of ``space``. If
    ``previous`` is also provided, creates a diff report between current and previous
    and uploads it to Confluence.

    Metadata files exist at ``path``
    """
    whatif = ctx.obj["whatif"]
    provider = ConfluenceProvider(ctx.obj["url"], ctx.obj["user"], ctx.obj["pwd"])
    current_file = os.path.join(path, "confluence-{}-{}.version".format(space, current))
    if os.path.isfile(current_file):
        print "Previous metadata already exists for {} at {}".format(current, current_file)
    else:
        print "Determining the metadata for version={},space={}...".format(current, space)
        current_diff = list(provider.get_diff_meta_file(space))
        print "Saving metadata in '{}'".format(current_file)

        if not whatif:
            with open(current_file, 'w') as f:
                json.dump(current_diff, f, sort_keys=True, indent=4)

    if previous:
        prev_file = os.path.join(path, "confluence-{}-{}.version".format(space, previous))

        print "Generating report in Confluence based on {} and {}...".format(current_file, prev_file)
        provider.generate_report(current, previous, current_file, prev_file, whatif)
    else:
        print "Previous version not supplied, diff report will not be created"


@cli.command("space-export", help="Exports the space as a pdf.")
@click.argument("space")
@click.argument("path")
@click.pass_context
def space_report(ctx, space, path):
    provider = ConfluenceProvider(ctx.obj["url"], ctx.obj["user"], ctx.obj["pwd"])
    print "Exporting {} to '{}'".format(space, path)
    provider.export_space(space, path)


def cli_main():
    cli(obj={})
