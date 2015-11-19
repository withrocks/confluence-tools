#!/usr/bin/env python
import os
import requests
import click
import json
from content import ConfluenceContent


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
        #import logging
        #logging.basicConfig(level=logging.DEBUG)
        pages = list(self._get_paged("/rest/api/space/{}/content".format(space_key, ""), {"expand": "version"}))
        for page in pages:
            for result in page["results"]:
                yield {
                    "id": result["id"],
                    "version": result["version"]["number"],
                    "url": result["_links"]["tinyui"],
                    "title": result["title"]
                }

    def get_spaces(self):
        return self._get("/rest/api/space")["results"]

    @staticmethod
    def get_diff_report(current, previous):
        # TODO: Find built-in for this
        def by_id(dictionary):
            return {item["id"]: item for item in dictionary}

        current_by_id = by_id(current)
        previous_by_id = by_id(previous)

        both = set(current_by_id.keys()) & set(previous_by_id.keys())
        only_in_current = set(current_by_id.keys()) - set(previous_by_id.keys())
        only_in_previous = set(previous_by_id.keys()) - set(current_by_id.keys())

        report = dict()
        report["changed"] = [current_by_id[key] for key in both
                             if current_by_id[key]["version"] != previous_by_id[key]["version"]]
        report["new"] = [current_by_id[key] for key in only_in_current
                         if key not in previous_by_id.keys()]
        report["deleted"] = [previous_by_id[key] for key in only_in_previous
                             if key not in current_by_id.keys()]
        return report


    def get_content(self, content_id, expand_body=False):
        return self._get("/rest/api/content/{}{}".format(content_id, "?expand=body.storage" if expand_body else ""))

    def update_page(self, content_id, html):
        print "Fetching last version of page with id={}...".format(content_id)
        content = self.get_content(content_id)
        version = int(content["version"]["number"])
        print "Current version is {}".format(version)
        data = {
            "id": content_id,
            "type": "page",
            "title": "Version History",
            "body": {
                "storage": {
                    "value": html,
                    "representation": "storage"
                }
            },
            "version": {"number": version + 1}
        }
        self._put("/rest/api/content/{}".format(content_id), data)
        print "Successfully updated page with id={}".format(content_id)

    def _get_paged(self, resource, params):
        while True:
            print "Fetching a page..."
            res = self._get(resource, params)
            if "page" in res:
                page = res["page"]
            else:
                page = res

            yield page

            # Check if there is more:
            if "next" in page["_links"]:
                resource = page["_links"]["next"]
            else:
                break

    def _get(self, resource, params=None):
        full_url = "{}{}".format(self.url, resource)
        resp = requests.get(full_url, auth=(self.user, self.pwd), params=params)
        if resp.status_code == 200:
            return resp.json()
        else:
            raise Exception(resp.text)

    def _put(self, resource, data):
        full_url = "{}{}".format(self.url, resource)
        resp = requests.put(full_url, json=data, auth=(self.user, self.pwd))
        if resp.status_code != 200:
            raise Exception(resp.text)

