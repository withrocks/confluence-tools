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

    def create_page(self, title, space_key, parent, html):
        data = {
                    "type": "page",
                    "title": title,
                    "ancestors": [{"id": parent}],
                    "space": {"key": space_key},
                    "body": {
                        "storage": {
                            "value": html,
                            "representation": "storage"}
                    }
                }
        self._post("/rest/api/content/", data)


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

    def get_content_by_id(self, content_id, expand_body=False):
        return self._get("/rest/api/content/{}{}".format(content_id, "?expand=body.storage" if expand_body else ""))

    def _get_version_file_path(self, root, space, version):
        return os.path.join(root, "confluence-{}-{}.version".format(space, version))

    def _load_version_file(self, root, space, version):
        with open(self._get_version_file_path(root, space, version), 'r') as f:
            return json.load(f)

    def generate_report(self, space, path, current, previous, whatif):
        version_history_title = "Version History"
        page = self.get_page(space, version_history_title)
        if not page:
            raise Exception("Missing page with title '{}'".format(version_history_title))
        version_history_id = page["id"]

        prev_metadata = self._load_version_file(path, space, previous)
        curr_metadata = self._load_version_file(path, space, current)

        self.logger.info("Generating diff report...")
        report = self.get_diff_report(curr_metadata, prev_metadata)

        self.logger.info("  Changed: {}".format(len(report["changed"])))
        self.logger.info("  New: {}".format(len(report["new"])))
        self.logger.info("  Deleted: {}".format(len(report["deleted"])))

        self.logger.debug("Formatting diff report as html...")
        html = ConfluenceContent.get_diff_report_as_html(current, previous, report, self.url)

        self.logger.info("Updating Confluence with latest info...")
        if not whatif:
            title = "Version {}".format(current)
            page = self.get_page(space, title)

            if not page:
                self.create_page(title, space, version_history_id, html)
            else:
                page_id = page["id"]
                self.update_page(page_id, html)
        else:
            self.logger.info("Whatif: Not updating page")

    def get_page(self, space_key, title):
        content = self._get("/rest/api/content", {"type": "page", "spaceKey": space_key, "title": title})
        pages = content["results"]
        length = len(pages)
        assert length < 2
        if length == 0:
            return None
        elif length == 1:
            return pages[0]

    def update_page(self, content_id, html):
        print "Fetching last version of page with id={}...".format(content_id)
        # TODO: unecessary call to get_content, already did that
        content = self.get_content_by_id(content_id)
        version = int(content["version"]["number"])
        print "Current version is {}".format(version)
        data = {
            "id": content_id,
            "type": "page",
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

