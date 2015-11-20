#!/usr/bin/env python
import os
import requests
import json
from content import ConfluenceContent
import suds.client
import logging


class ConfluenceProvider:
    def __init__(self, url, user, pwd, logger=None):
        self.url = url
        self.user = user
        self.pwd = pwd
        self.logger = logger or logging.getLogger(__name__)

    def create_page(self, space_key, parent):
        data = {
                    "type": "page",
                    "title":"new page",
                    "ancestors": [{"id": parent}],
                    "space": {"key": space_key},
                    "body": {
                        "storage": {"value":"<p>This is a new page</p>","representation":"storage"}
                    }
                }


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

    def generate_report(self, current_version, previous_version, current_metadata_path, previous_metadata_path, whatif):
        with open(previous_metadata_path, 'r') as f:
            previous_metadata = json.load(f)

        with open(current_metadata_path, 'r') as f:
            current_metadata = json.load(f)

        print "Generating diff report..."
        report = self.get_diff_report(current_metadata, previous_metadata)

        print "  Changed: {}".format(len(report["changed"]))
        print "  New: {}".format(len(report["new"]))
        print "  Deleted: {}".format(len(report["deleted"]))

        print "Formatting diff report as html..."
        html = ConfluenceContent.get_diff_report_as_html(current_version, previous_version, report, self.url)

        print "Updating Confluence with latest info..."
        # TODO: Query for the page containing the version hist

        if not whatif:
            version_history_id = "2785691"
            self.update_page(version_history_id, html)

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

    def export_space(self, space, local_path=None):
        logging.info("Exporting space '{}'".format(space))
        client = self._soap_client("/rpc/soap-axis/pdfexport?wsdl")
        token = client.service.login(self.user, self.pwd)
        logging.debug("Got token from the pdfexport endpoint")

        url = client.service.exportSpace(token, space)
        logging.info("Exported space. URL={}".format(url))

        if not local_path:
            local_path = url.split('/')[-1]
        logging.info("Downloading exported pdf to '{}'".format(local_path))
        self.download_file(url, local_path, self.user, self.pwd)
        logging.info("File successfully downloaded")

    @staticmethod
    def download_file(url, local_path=None, user=None, pwd=None):
        r = requests.get(url, stream=True, auth=(user, pwd))
        if r.status_code == 403:
            raise Exception("Access denied for '{}': {}".format(url, r.text))
        elif r.status_code != 200:
            raise Exception("Unable to download file. Status code={}: {}".format(r.status_code, r.text))

        if os.path.isfile(local_path):
            raise Exception("Local file already exists: {}".format(local_path))
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

    def _soap_client(self, soap_endpoint):
        return suds.client.Client("{}{}".format(self.url, soap_endpoint))

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

    def _full_url(self, resource):
        return "{}{}".format(self.url, resource)

    def _get(self, resource, params=None):
        resp = requests.get(self._full_url(resource), auth=(self.user, self.pwd), params=params)
        if resp.status_code == 200:
            return resp.json()
        else:
            raise Exception(resp.text)

    def _put(self, resource, data):
        resp = requests.put(self._full_url(resource), json=data, auth=(self.user, self.pwd))
        if resp.status_code != 200:
            raise Exception(resp.text)

    def _post(self, resource, data):
        resp = requests.post(self._full_url(resource), json=data, auth=(self.user, self.pwd))
        if resp.status_code != 200:
            raise Exception(resp.text)

