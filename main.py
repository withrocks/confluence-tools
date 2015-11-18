#!/usr/bin/env python
import os
import requests
import sys
import click
import json


class ConfluenceProvider:
    def __init__(self, url, user, pwd):
        self.url = url
        self.user = user
        self.pwd = pwd

    def get_diff_meta_file(self, space_key):
        """
        Returns the diff history for a whole space from a particular time.
        This can be used to generate documentation from the space
        including
        """
        return self.get_space_content_history(space_key)

    def get_space_id_from_key(self, key):
        spaces = self.get_spaces()
        res = [result["id"] for result in spaces if result["key"] == key]
        assert len(res) == 1
        return res[0]

    def get_space_content_history(self, space_key):
        page = self._get("/rest/api/space/{}/content{}?expand=version".format(space_key, ""))["page"]
        #print page["start"], page["size"], page["limit"], len(page["results"])  # TODO: paging
        for result in page["results"]:
            yield {
                "id": result["id"],
                "version": result["version"]["number"],
                "url": result["_links"]["tinyui"],
                "title": result["title"]
            }

    def get_spaces(self):
        return self._get("/rest/api/space")["results"]

    def get_diff_report(self, current, previous):
        # TODO: Find built-in for this
        def by_id(dictionary):
            return {item["id"]: item for item in dictionary}

        current_by_id = by_id(current)
        previous_by_id = by_id(previous)

        all_keys = set(current_by_id.keys()) & set(previous_by_id.keys())

        report = dict()
        report["changed"] = [current_by_id[key] for key in all_keys
                             if current_by_id[key]["version"] != previous_by_id[key]["version"]]
        report["new"] = [current_by_id[key] for key in all_keys
                         if key not in previous_by_id]
        report["deleted"] = [previous_by_id[key] for key in all_keys
                             if key not in current_by_id]
        return report

    def _get(self, resource):
        full_url = "{}{}".format(self.url, resource)
        resp = requests.get(full_url, auth=(self.user, self.pwd))
        if resp.status_code == 200:
            return resp.json()
        else:
            raise Exception(resp.text)

@click.command()
@click.argument("space")
@click.option("--url")
@click.option("--user")
@click.option("--pwd")
@click.option("--current", default="1.0.0")
@click.option("--previous")
@click.option("--path", default=".")
def docdiff(space, url, user, pwd, current, previous, path):
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

    provider = ConfluenceProvider(url, user, pwd)
    print "Determining the meta file for space={}...".format(space)
    current_diff = list(provider.get_diff_meta_file(space))

    outfile = os.path.join(path, "confluence-{}-{}.version".format(space, current))
    print "Saving diff in '{}'".format(outfile)
    with open(outfile, 'w') as f:
        json.dump(current_diff, f)

    if previous:
        infile = os.path.join(path, "confluence-{}-{}.version".format(space, previous))
        print "Reading previous data from '{}'".format(infile)
        with open(infile, 'r') as f:
            previous_diff = json.load(f)
            report = provider.get_diff_report(current_diff, previous_diff)
            print "Changed:"
            for item in report["changed"]:
                print item

            print "New"
            for item in report["new"]:
                print item

            print "Deleted"
            for item in report["deleted"]:
                print item
    else:
        print "Previous version not supplied, nothing to diff"


if __name__ == "__main__":
    docdiff()
