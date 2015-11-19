import click
from confluence_tools.main import ConfluenceProvider
from content import ConfluenceContent
import os
import json


@click.command()
@click.option("--space")
@click.option("--config")
@click.option("--url")
@click.option("--user")
@click.option("--pwd")
@click.option("--current", default="1.0.0")
@click.option("--previous")
@click.option("--path", default=".")
def docdiff(space, config, url, user, pwd, current, previous, path):
    """
    Returns all pages in the space that have changed since last released version.

    Expected workflow:
        - During a build, the documentation is built from Confluence (e.g. exporting a PDF)
        - When doing this, the pipeline also calls this program, getting a file
        called 'confluence-<spacekey>-#.#.#.version'
        - This file is saved with that release. It contains a CSV file that lists all pages
        and corresponding versions

        - On the next build, the same process is repeated, except this program is called
         with the --previous flag set (TODO: keep meta files in Confluence)
        - A new meta file is created
        - A human readable diff is created that shows which pages have changed between the releases
        - This file can now be added to Confluence and exported with the the release.
         Readers can now easily see what changed since they last read the documentation
    """
    # TODO: Paging, only works for first 25
    import yaml
    if config:
        with open(config) as f:
            config_obj = yaml.load(f)
            url = url or config_obj["url"]
            user = user or config_obj["user"]
            pwd = pwd or config_obj["pwd"]
            space = space or config_obj["space"]

    if not url or not user or not pwd or not space:
        raise click.UsageError("Missing one of url, user, pwd, space either on cmd line or in config")


    provider = ConfluenceProvider(url, user, pwd)

    """
    version_history_id = "2785691"
    print provider.get_content(version_history_id, True)
    return
    """
    print "Determining the meta file for space={}...".format(space)
    current_diff = list(provider.get_diff_meta_file(space))

    outfile = os.path.join(path, "confluence-{}-{}.version".format(space, current))
    print "Saving diff in '{}'".format(outfile)
    with open(outfile, 'w') as f:
        json.dump(current_diff, f, sort_keys=True, indent=4)

    if previous:
        infile = os.path.join(path, "confluence-{}-{}.version".format(space, previous))
        print "Reading previous data from '{}'".format(infile)
        with open(infile, 'r') as f:
            previous_diff = json.load(f)
            report = provider.get_diff_report(current_diff, previous_diff)
            html = ConfluenceContent.get_diff_report_as_html(previous, current, report, url)
            # TODO: Query for the page containing the version hist
            version_history_id = "2785691"
            provider.update_page(version_history_id, html)
    else:
        print "Previous version not supplied, nothing to diff"

def cli_main():
    docdiff()
