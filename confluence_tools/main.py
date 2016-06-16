import logging
import os
import requests
import suds.client


class ConfluenceProvider:
    """
    Provides access to the Confluence APIs
    """
    def __init__(self, url, user, pwd, logger=None):
        self.url = url
        self.user = user
        self.pwd = pwd
        self.logger = logger or logging.getLogger(__name__)

    def create_page(self, title, space_key, parent, html):
        """Creates a page with the content ``html``"""
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

    def get_space_content_history(self, space_key):
        """Returns the content for a space, including version information"""
        pages = list(self._get_paged("/rest/api/space/{}/content".format(space_key, ""),
                                     {"expand": "version"}))
        for page in pages:
            for result in page["results"]:
                yield {
                    "id": result["id"],
                    "version": result["version"]["number"],
                    "url": result["_links"]["tinyui"],
                    "title": result["title"]
                }

    def get_spaces(self):
        """Returns all spaces in Confluence"""
        # TODO: Paging is probably necessary
        return self._get("/rest/api/space")["results"]

    def get_content_by_id(self, content_id, expand_body=False):
        """Returns the content of the particular page"""
        return self._get("/rest/api/content/{}{}".format(
            content_id, "?expand=body.storage" if expand_body else ""))

    def get_page(self, space_key, title):
        """Returns a page by title"""
        content = self._get("/rest/api/content", {"type": "page", "spaceKey": space_key, "title": title})
        pages = content["results"]
        length = len(pages)
        assert length < 2
        if length == 0:
            return None
        elif length == 1:
            return pages[0]

    def update_page(self, content_id, html):
        """Updates content by content_id"""
        # TODO: unnecessary call to get_content, already did that
        content = self.get_content_by_id(content_id)
        version = int(content["version"]["number"])
        data = {
            "id": content_id,
            "title": content["title"],
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

    def export_space(self, space, local_path=None):
        """Exports a space as pdf"""
        logging.info("Exporting space '{}'".format(space))
        client = self._soap_client("/rpc/soap-axis/pdfexport?wsdl")
        token = client.service.login(self.user, self.pwd)
        logging.debug("Got token from the pdfexport endpoint")

        url = client.service.exportSpace(token, space)
        logging.info("Exported space. URL={}".format(url))

        if not local_path:
            local_path = url.split('/')[-1]
        logging.info("Downloading exported pdf to '{}'".format(local_path))
        self._download_file(url, local_path, self.user, self.pwd)
        logging.info("File successfully downloaded")

    @staticmethod
    def _download_file(url, local_path=None, user=None, pwd=None):
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
            self.logger.debug("Fetching a page...")
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

